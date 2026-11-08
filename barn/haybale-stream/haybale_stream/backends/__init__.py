"""Frame-sharing backends behind one sender/receiver contract. See ``base``."""

from __future__ import annotations

from .base import Backend, BackendUnavailable, ClockedSender, Frame, Receiver, Sender
from .ndi import NDIBackend
from .omt import OMTBackend
from .spout import SpoutBackend
from .syphon import SyphonBackend

#: Every backend by key, in menu order. Importing this is safe on any platform: native
#: dependencies are imported only when a sender, receiver or discovery is actually used.
BACKENDS: dict[str, type[Backend]] = {
    b.key: b for b in (NDIBackend, OMTBackend, SyphonBackend, SpoutBackend)
}


def get_backend(key: str) -> type[Backend]:
    """Return the backend registered as ``key`` (case-insensitive)."""
    try:
        return BACKENDS[key.lower()]
    except KeyError:
        raise KeyError(f"unknown backend {key!r}; known: {', '.join(BACKENDS)}") from None


def available_backends() -> list[type[Backend]]:
    """The backends that can run on this machine right now."""
    return [b for b in BACKENDS.values() if b.is_available()]


__all__ = [
    "BACKENDS",
    "Backend",
    "BackendUnavailable",
    "ClockedSender",
    "Frame",
    "Receiver",
    "Sender",
    "available_backends",
    "get_backend",
]
