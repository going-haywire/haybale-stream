"""OMT (Open Media Transport) backend, on cyomtlib (wheels bundle libomt)."""

from __future__ import annotations

import numpy as np

from .base import Backend, BackendUnavailable, ClockedSender, Frame, Receiver, Sender


class OMTSender(ClockedSender):
    def __init__(self, name: str, steady_stream: bool = False) -> None:
        super().__init__(name, steady_stream)
        self._sender = None

    def _open_native(self) -> None:
        import cyomtlib as omt

        self._sender = omt.Sender(self.name)

    @property
    def address(self) -> str | None:
        """The name receivers see (OMT prefixes the host name)."""
        return None if self._sender is None else self._sender.address

    def _write(self, pixels: np.ndarray, frame_rate: float) -> None:
        import cyomtlib as omt

        self._sender.send_video(pixels, omt.Codec.BGRA, frame_rate=frame_rate, flags=omt.VideoFlags.ALPHA)

    def _close_native(self) -> None:
        sender, self._sender = self._sender, None
        if sender is not None:
            sender.close()


class OMTReceiver(Receiver):
    def __init__(self, source: str) -> None:
        super().__init__(source)
        self._receiver = None

    def open(self) -> None:
        import cyomtlib as omt

        self._receiver = omt.Receiver(
            self.source, frame_types=omt.FrameType.VIDEO, video_format=omt.PreferredVideoFormat.BGRA
        )

    def poll(self, timeout: float = 0.0) -> Frame | None:
        import cyomtlib as omt

        if self._receiver is None:
            return None
        frame = self._receiver.receive(omt.FrameType.VIDEO, timeout_ms=int(timeout * 1000))
        if not isinstance(frame, omt.VideoFrame):
            return None
        # packed() views libomt's buffer, valid until the next receive: take a copy.
        return Frame(np.array(frame.packed(), dtype=np.uint8))

    def close(self) -> None:
        receiver, self._receiver = self._receiver, None
        if receiver is not None:
            receiver.close()


class OMTBackend(Backend):
    key = "omt"
    label = "OMT"
    channel_order = "bgra"
    supports_steady_stream = True

    @classmethod
    def _check_dependency(cls) -> str | None:
        try:
            import cyomtlib  # noqa: F401
        except ImportError as exc:
            return f"OMT needs the 'cyomtlib' package ({exc})"
        return None

    @classmethod
    def discover(cls, wait: float = 0.0) -> list[str]:
        if (reason := cls.unavailable_reason()) is not None:
            raise BackendUnavailable(reason)
        import cyomtlib as omt

        return sorted(omt.discover(wait=wait))

    @classmethod
    def create_sender(cls, name: str, *, steady_stream: bool = False) -> Sender:
        if (reason := cls.unavailable_reason()) is not None:
            raise BackendUnavailable(reason)
        return OMTSender(name, steady_stream)

    @classmethod
    def create_receiver(cls, source: str) -> Receiver:
        if (reason := cls.unavailable_reason()) is not None:
            raise BackendUnavailable(reason)
        return OMTReceiver(source)
