"""Spout backend (Windows), on SpoutGL.

UNTESTED on the Linux development machine: the module imports cleanly everywhere, but
``SpoutGL`` only has Windows wheels, so ``unavailable_reason()`` reports the platform
elsewhere. Code follows SpoutGL's documented send/receive loop and the TextureSharing
Spout backend it was ported from.
"""

from __future__ import annotations

import numpy as np

from .base import Backend, BackendUnavailable, Frame, Receiver, Sender


class SpoutSender(Sender):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._sender = None

    def open(self) -> None:
        import SpoutGL

        self._sender = SpoutGL.SpoutSender()
        self._sender.setSenderName(self.name)

    def send(self, pixels: np.ndarray, frame_rate: float = 30.0) -> None:
        import SpoutGL

        if self._sender is None:
            return
        height, width = pixels.shape[:2]
        data = np.ascontiguousarray(pixels, dtype=np.uint8)
        # invert=False: numpy rows run top to bottom, which is what Spout receivers expect.
        if self._sender.sendImage(data.reshape(-1), width, height, SpoutGL.enums.GL_RGBA, False, 0):
            self._sender.setFrameSync(self.name)

    def close(self) -> None:
        sender, self._sender = self._sender, None
        if sender is not None:
            sender.releaseSender()


class SpoutReceiver(Receiver):
    def __init__(self, source: str) -> None:
        super().__init__(source)
        self._receiver = None
        self._buffer: bytearray | None = None
        self._size = (0, 0)

    def open(self, timeout: float = 5.0) -> None:
        import SpoutGL

        self._receiver = SpoutGL.SpoutReceiver()
        self._receiver.setReceiverName(self.source)

    def poll(self, timeout: float = 0.0) -> Frame | None:
        import SpoutGL

        receiver = self._receiver
        if receiver is None:
            return None
        ok = receiver.receiveImage(self._buffer, SpoutGL.enums.GL_RGBA, False, 0)
        if receiver.isUpdated():  # first connection, or the sender changed size
            self._size = (receiver.getSenderWidth(), receiver.getSenderHeight())
            self._buffer = bytearray(self._size[0] * self._size[1] * 4)
            return None
        if not ok or self._buffer is None or not receiver.isFrameNew():
            return None
        if SpoutGL.helpers.isBufferEmpty(self._buffer):
            return None  # Spout hands out an empty first frame
        width, height = self._size
        return Frame(np.frombuffer(self._buffer, np.uint8).reshape(height, width, 4).copy())

    def close(self) -> None:
        receiver, self._receiver = self._receiver, None
        if receiver is not None:
            receiver.releaseReceiver()


class SpoutBackend(Backend):
    key = "spout"
    label = "Spout"
    platforms = ("win32",)
    channel_order = "rgba"

    @classmethod
    def _check_dependency(cls) -> str | None:
        try:
            import SpoutGL  # noqa: F401
        except ImportError as exc:
            return f"Spout needs the 'SpoutGL' package ({exc})"
        return None

    @classmethod
    def discover(cls, wait: float = 0.0) -> list[str]:
        if (reason := cls.unavailable_reason()) is not None:
            raise BackendUnavailable(reason)
        import SpoutGL

        receiver = SpoutGL.SpoutReceiver()
        try:
            return sorted(receiver.getSenderList())
        finally:
            receiver.releaseReceiver()

    @classmethod
    def create_sender(cls, name: str, *, steady_stream: bool = False) -> Sender:
        if (reason := cls.unavailable_reason()) is not None:
            raise BackendUnavailable(reason)
        return SpoutSender(name)

    @classmethod
    def create_receiver(cls, source: str) -> Receiver:
        if (reason := cls.unavailable_reason()) is not None:
            raise BackendUnavailable(reason)
        return SpoutReceiver(source)
