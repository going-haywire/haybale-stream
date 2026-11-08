"""Backend contract: platform gating, and real NDI/OMT loopback on this machine."""

import time
import uuid

import numpy as np
import pytest

from haybale_stream.backends import BACKENDS, BackendUnavailable, available_backends, get_backend

pytestmark = [pytest.mark.unit]


def _frame(backend, width: int, height: int, rgba: tuple[int, int, int, int]) -> np.ndarray:
    """A solid frame, written in the backend's own channel order."""
    r, g, b, a = rgba
    out = np.empty((height, width, 4), np.uint8)
    out[:] = (r, g, b, a) if backend.channel_order == "rgba" else (b, g, r, a)
    return out


def test_registry_lists_all_four_backends():
    assert list(BACKENDS) == ["ndi", "omt", "syphon", "spout"]
    assert get_backend("NDI") is BACKENDS["ndi"]
    with pytest.raises(KeyError):
        get_backend("nope")


@pytest.mark.parametrize("key", ["syphon", "spout"])
def test_platform_backends_are_gated_off_the_wrong_platform(key):
    backend = get_backend(key)
    if backend.supported_here():
        pytest.skip(f"{key} is native here")
    assert not backend.is_available()
    assert "not available on this platform" in backend.unavailable_reason()
    with pytest.raises(BackendUnavailable):
        backend.discover()
    with pytest.raises(BackendUnavailable):
        backend.create_sender("x")
    with pytest.raises(BackendUnavailable):
        backend.create_receiver("x")


def test_available_backends_only_contains_runnable_ones():
    assert all(b.is_available() for b in available_backends())


def _wait_for(backend, needle: str, seconds: float = 10.0) -> str:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        found = [s for s in backend.discover(wait=1.0) if needle in s]
        if found:
            return found[0]
    raise AssertionError(f"{backend.label} source {needle!r} never appeared")


def _poll(receiver, seconds: float = 10.0, want=None):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        frame = receiver.poll(timeout=0.2)
        if frame is not None and (want is None or want(frame)):
            return frame
    raise AssertionError("no matching frame arrived")


@pytest.mark.network
@pytest.mark.integration
@pytest.mark.parametrize("key", ["ndi", "omt"])
def test_loopback_roundtrip_and_resize(key):
    backend = get_backend(key)
    if not backend.is_available():
        pytest.skip(backend.unavailable_reason())
    name = f"hbtest-{uuid.uuid4().hex[:8]}"
    with backend.create_sender(name, steady_stream=True) as sender:
        sender.send(_frame(backend, 64, 48, (200, 20, 20, 255)), 30.0)
        source = _wait_for(backend, name)
        with backend.create_receiver(source) as receiver:
            frame = _poll(receiver)
            assert (frame.width, frame.height) == (64, 48)
            px = frame.pixels[24, 32].astype(int)
            # Both codecs are lossy; channel order is what matters here.
            red, green, blue = (
                (px[0], px[1], px[2]) if backend.channel_order == "rgba" else (px[2], px[1], px[0])
            )
            assert red > 150 and green < 80 and blue < 80

            # a size change mid-stream must reach the receiver
            sender.send(_frame(backend, 32, 24, (20, 20, 200, 255)), 30.0)
            frame = _poll(receiver, want=lambda f: (f.width, f.height) == (32, 24))
            px = frame.pixels[12, 16].astype(int)
            blue = px[2] if backend.channel_order == "rgba" else px[0]
            assert blue > 150
