"""The backend-neutral sender/receiver contract.

A backend moves **packed 8-bit 4-channel frames** (``H×W×4`` uint8) between processes.
It knows nothing about haywire or ``ImageValue``: ``convert.py`` bridges the two, so a
backend module imports only its own native dependency, and only when it is used.

Channel order is a property of the backend (``Backend.channel_order``): NDI and Spout
take RGBA, OMT and Syphon's raw readback are BGRA. The bridge converts once, on the
way in or out, so a backend never swaps channels itself.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Self

import numpy as np

log = logging.getLogger(__name__)


class BackendUnavailable(RuntimeError):
    """The backend cannot run here: wrong platform, or its native dependency is missing."""


@dataclass(frozen=True)
class Frame:
    """One received frame: ``pixels`` is ``H×W×4`` uint8 in the backend's channel order."""

    pixels: np.ndarray
    timestamp: float | None = None

    @property
    def width(self) -> int:
        return int(self.pixels.shape[1])

    @property
    def height(self) -> int:
        return int(self.pixels.shape[0])


class Sender(ABC):
    """Publishes frames under a name that receivers discover."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def open(self) -> None:
        """Start publishing. Raises ``BackendUnavailable`` if the backend cannot run."""

    @abstractmethod
    def send(self, pixels: np.ndarray, frame_rate: float = 30.0) -> None:
        """Publish one ``H×W×4`` uint8 frame. May return before the frame is on the wire."""

    @abstractmethod
    def close(self) -> None:
        """Stop publishing and release native resources. Safe to call twice."""

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class ClockedSender(Sender):
    """A sender whose native send call blocks for one frame period (NDI, OMT).

    The caller's thread must not block on the network clock, so ``send`` only stores the
    newest frame; a worker thread writes it. Frames sent faster than the clock are
    dropped (latest wins). With ``steady_stream`` the last frame is resent while the
    caller is idle, which keeps receivers from showing "no signal" on a still image.
    """

    def __init__(self, name: str, steady_stream: bool = False) -> None:
        super().__init__(name)
        self.steady_stream = steady_stream
        self._latest: tuple[np.ndarray, float] | None = None
        self._lock = threading.Lock()
        self._new = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.frames_written = 0

    @abstractmethod
    def _open_native(self) -> None: ...

    @abstractmethod
    def _write(self, pixels: np.ndarray, frame_rate: float) -> None:
        """Blocking native write; runs on the worker thread only."""

    @abstractmethod
    def _close_native(self) -> None: ...

    def open(self) -> None:
        self._open_native()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name=f"{type(self).__name__}-{self.name}", daemon=True
        )
        self._thread.start()

    def send(self, pixels: np.ndarray, frame_rate: float = 30.0) -> None:
        # Own the bytes: the caller's array may be a read-only view of an image other nodes
        # still read, and native writers want a writable buffer. np.array always copies.
        frame = np.array(pixels, dtype=np.uint8, order="C")
        with self._lock:
            self._latest = (frame, frame_rate)
        self._new.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            if (not self.steady_stream or self._latest is None) and not self._new.wait(0.1):
                continue
            self._new.clear()
            with self._lock:
                latest = self._latest
            if latest is None or self._stop.is_set():
                continue
            try:
                self._write(*latest)
                self.frames_written += 1
            except Exception:
                log.exception("%s send failed", type(self).__name__)
                self._stop.wait(0.1)

    def close(self) -> None:
        self._stop.set()
        self._new.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=5.0)
        self._close_native()


class Receiver(ABC):
    """Receives frames from one named source."""

    def __init__(self, source: str) -> None:
        self.source = source

    @abstractmethod
    def open(self, timeout: float = 5.0) -> None:
        """Connect, waiting up to ``timeout`` s for the source to appear.

        Raises ``BackendUnavailable`` or ``LookupError`` (source not found).
        """

    @abstractmethod
    def poll(self, timeout: float = 0.0) -> Frame | None:
        """Return the newest frame not yet returned, or ``None`` if there is none (waits up to ``timeout`` s)."""

    @abstractmethod
    def close(self) -> None:
        """Disconnect and release native resources. Safe to call twice."""

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class Backend(ABC):
    """One transport: knows whether it can run here, lists sources, builds senders and receivers."""

    key: ClassVar[str]
    label: ClassVar[str]
    #: ``sys.platform`` prefixes the backend runs on.
    platforms: ClassVar[tuple[str, ...]] = ("linux", "darwin", "win32")
    #: Channel order of the frames this backend sends and receives: ``"rgba"`` or ``"bgra"``.
    channel_order: ClassVar[str] = "rgba"
    #: Whether a sender can be told to resend its last frame (see ``ClockedSender``).
    supports_steady_stream: ClassVar[bool] = False

    @classmethod
    def supported_here(cls) -> bool:
        import sys

        return sys.platform.startswith(cls.platforms)

    @classmethod
    def unavailable_reason(cls) -> str | None:
        """Why this backend cannot run here, or ``None`` when it can."""
        if not cls.supported_here():
            return f"{cls.label} is not available on this platform (needs {'/'.join(cls.platforms)})"
        return cls._check_dependency()

    @classmethod
    def is_available(cls) -> bool:
        return cls.unavailable_reason() is None

    @classmethod
    @abstractmethod
    def _check_dependency(cls) -> str | None:
        """Import the native dependency; return a message if it is missing, else ``None``."""

    @classmethod
    @abstractmethod
    def discover(cls, wait: float = 0.0) -> list[str]:
        """Names of the sources currently visible. ``wait`` seconds to let discovery settle."""

    @classmethod
    @abstractmethod
    def create_sender(cls, name: str, *, steady_stream: bool = False) -> Sender: ...

    @classmethod
    @abstractmethod
    def create_receiver(cls, source: str) -> Receiver: ...
