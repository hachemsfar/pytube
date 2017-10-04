# -*- coding: utf-8 -*-
"""
pytube.__main__
~~~~~~~~~~~~~~~

This module implements the core developer interface for pytube.

"""
import json

from pytube import extract
from pytube import mixins
from pytube import request
from pytube import Stream
from pytube import StreamQuery


class YouTube:
    def __init__(
        self, url=None, defer_init=False, on_progress_callback=None,
        on_complete_callback=None,
    ):
        """Constructs a :class:`YouTube <YouTube>`.

        :param str url:
            A valid YouTube watch URL.
        :param bool defer_init:
            Defers executing any network requests.
        :param func on_progress_callback:
            (Optional) User defined callback function for stream download
            progress events.
        :param func on_complete_callback:
            (Optional) User defined callback function for stream download
            complete events.
        """
        self.js = None      # js fetched by js_url
        self.js_url = None  # the url to the js, parsed from watch html

        # note: vid_info can possibly be removed, the fmt stream data contained
        # in here doesn't compute a usable signature and the rest of the data
        # may be redundant.

        self.vid_info = None      # content fetched by vid_info_url
        self.vid_info_url = None  # the url to vid info, parsed from watch html

        self.watch_html = None     # the html of /watch?v=<video_id>
        self.player_config = None  # inline js in the html containing streams

        self.fmt_streams = []  # list of :class:`Stream <Stream>` instances

        # video_id part of /watch?v=<video_id>
        self.video_id = extract.video_id(url)

        # https://www.youtube.com/watch?v=<video_id>
        self.watch_url = extract.watch_url(self.video_id)

        # A dictionary shared between all instances of :class:`Stream <Stream>`
        # (Borg pattern).
        self.stream_monostate = {
            # user defined callback functions
            'on_progress': on_progress_callback,
            'on_complete': on_complete_callback,
        }

        if url and not defer_init:
            self.init()

    def init(self):
        self.prefetch()
        self.vid_info = extract.decode_video_info(self.vid_info)

        trad_fmts = 'url_encoded_fmt_stream_map'
        dash_fmts = 'adaptive_fmts'
        mixins.apply_fmt_decoder(self.vid_info, trad_fmts)
        mixins.apply_fmt_decoder(self.vid_info, dash_fmts)
        mixins.apply_fmt_decoder(self.player_config['args'], trad_fmts)
        mixins.apply_fmt_decoder(self.player_config['args'], dash_fmts)
        mixins.apply_cipher(self.player_config['args'], trad_fmts, self.js)
        mixins.apply_cipher(self.player_config['args'], dash_fmts, self.js)
        mixins.apply(self.player_config['args'], 'player_response', json.loads)
        self.build_stream_objects(trad_fmts)
        self.build_stream_objects(dash_fmts)

    def prefetch(self):
        self.watch_html = request.get(url=self.watch_url)
        self.vid_info_url = extract.video_info_url(
            video_id=self.video_id,
            watch_url=self.watch_url,
            watch_html=self.watch_html,
        )
        self.js_url = extract.js_url(self.watch_html)
        self.js = request.get(url=self.js_url)
        self.vid_info = request.get(url=self.vid_info_url)
        self.player_config = extract.get_ytplayer_config(self.watch_html)

    def build_stream_objects(self, fmt):
        streams = self.player_config['args'][fmt]
        for stream in streams:
            video = Stream(
                stream=stream,
                player_config=self.player_config,
                monostate=self.stream_monostate,
            )
            self.fmt_streams.append(video)

    @property
    def streams(self):
        """Interface to query non-dash streams."""
        return StreamQuery([s for s in self.fmt_streams if not s.is_dash])

    @property
    def dash_streams(self):
        """Interface to query dash streams."""
        return StreamQuery([s for s in self.fmt_streams if s.is_dash])

    def register_on_progress_callback(self, fn):
        """Registers an on download progess callback function after object
        initialization.

        :param func fn:
            A callback function that takes ``stream``, ``chunk``,
            ``file_handle``, ``bytes_remaining`` as parameters.
        """
        self._monostate['on_progress'] = fn

    def register_on_complete_callback(self, fn):
        """Registers an on download complete callback function after object
        initialization.

        :param func fn:
            A callback function that takes ``stream`` and  ``file_handle``.
        """
        self._monostate['on_complete'] = fn
