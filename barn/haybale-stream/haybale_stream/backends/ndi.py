"""NDI backend, on cyndilib (wheels bundle the NDI runtime on Linux, macOS and Windows)."""

from __future__ import annotations

import time
from fractions import Fraction

import numpy as np

from .base import Backend, BackendUnavailable, ClockedSender, Frame, Receiver, Sender


class NDISender(ClockedSender):
    def __init__(self, name: str, steady_stream: bool = False) -> None:
        super().__init__(name, steady_stream)
        self._sender = None
        self._size: tuple[int, int] | None = None
        self._rate: Fraction | None = None

    def _open_native(self) -> None:
        from cyndilib.sender import Sender as NativeSender

        self._sender = NativeSender(self.name)

    def _configure(self, width: int, height: int, frame_rate: float) -> None:
        """(Re)build the video frame; NDI can only swap it while the sender is closed."""
        from cyndilib.video_frame import VideoSendFrame
        from cyndilib.wrapper.ndi_structs import FourCC

        sender = self._sender
        if self._size is not None:
            sender.close()
        frame = VideoSendFrame()
        frame.set_fourcc(FourCC.RGBA)
        frame.set_resolution(width, height)
        rate = Fraction(frame_rate).limit_denominator(1001)
        frame.set_frame_rate(rate)
        sender.set_video_frame(frame)
        sender.open()
        self._size, self._rate = (width, height), rate

    def _write(self, pixels: np.ndarray, frame_rate: float) -> None:
        height, width = pixels.shape[:2]
        rate = Fraction(frame_rate).limit_denominator(1001)
        if self._size != (width, height) or self._rate != rate:
            self._configure(width, height, frame_rate)
        self._sender.write_video(pixels.reshape(-1))

    def _close_native(self) -> None:
        sender, self._sender = self._sender, None
        if sender is not None and self._size is not None:
            sender.close()
        self._size = None


class NDIReceiver(Receiver):
    def __init__(self, source: str) -> None:
        super().__init__(source)
        self._finder = None
        self._receiver = None
        self._video = None
        self._last_ts: float | None = None

    def open(self) -> None:
        from cyndilib.finder import Finder
        from cyndilib.receiver import Receiver as NativeReceiver
        from cyndilib.video_frame import VideoFrameSync
        from cyndilib.wrapper.ndi_recv import RecvBandwidth, RecvColorFormat

        finder = Finder()
        finder.open()
        try:
            deadline = time.monotonic() + 5.0
            found = None
            while found is None and time.monotonic() < deadline:
                finder.wait_for_sources(0.5)
                found = next((s for s in finder if s.name == self.source), None)
            if found is None:
                raise LookupError(f"NDI source {self.source!r} not found")
            receiver = NativeReceiver(color_format=RecvColorFormat.RGBX_RGBA, bandwidth=RecvBandwidth.highest)
            video = VideoFrameSync()
            receiver.frame_sync.set_video_frame(video)
            receiver.set_source(found)
        except BaseException:
            finder.close()
            raise
        self._finder, self._receiver, self._video = finder, receiver, video

    def poll(self, timeout: float = 0.0) -> Frame | None:
        if self._receiver is None:
            return None
        deadline = time.monotonic() + timeout
        while True:
            # frame_sync repeats the last frame; the timestamp tells a new one from a repeat.
            self._receiver.frame_sync.capture_video()
            video = self._video
            if video.get_data_size() > 0:
                ts = video.get_timestamp_posix()
                if ts != self._last_ts:
                    self._last_ts = ts
                    width, height = video.get_resolution()
                    pixels = np.array(video.get_array(), dtype=np.uint8).reshape(height, width, 4)
                    return Frame(pixels, ts)
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.005)

    def close(self) -> None:
        receiver, self._receiver = self._receiver, None
        finder, self._finder = self._finder, None
        if receiver is not None:
            receiver.disconnect()
        if finder is not None:
            finder.close()


class NDIBackend(Backend):
    key = "ndi"
    label = "NDI"
    channel_order = "rgba"
    supports_steady_stream = True

    @classmethod
    def _check_dependency(cls) -> str | None:
        try:
            import cyndilib  # noqa: F401
        except ImportError as exc:
            return f"NDI needs the 'cyndilib' package ({exc})"
        return None

    @classmethod
    def discover(cls, wait: float = 0.0) -> list[str]:
        if (reason := cls.unavailable_reason()) is not None:
            raise BackendUnavailable(reason)
        from cyndilib.finder import Finder

        finder = Finder()
        finder.open()
        try:
            if wait > 0:
                finder.wait_for_sources(wait)
            return sorted(s.name for s in finder)
        finally:
            finder.close()

    @classmethod
    def create_sender(cls, name: str, *, steady_stream: bool = False) -> Sender:
        if (reason := cls.unavailable_reason()) is not None:
            raise BackendUnavailable(reason)
        return NDISender(name, steady_stream)

    @classmethod
    def create_receiver(cls, source: str) -> Receiver:
        if (reason := cls.unavailable_reason()) is not None:
            raise BackendUnavailable(reason)
        return NDIReceiver(source)
