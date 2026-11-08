"""Spout and Syphon code paths, driven through fake native modules.

The real packages exist only on Windows / macOS. These tests pin our side of the calls
(argument order, sizes, flipping, buffer reuse); they do not prove the native libraries
agree - that needs a Windows / macOS run.
"""

import sys
import types
from typing import ClassVar

import numpy as np
import pytest
from haybale_stream.backends import get_backend
from haybale_stream.backends.base import BackendUnavailable

pytestmark = [pytest.mark.unit]


def _fake_spout(monkeypatch):
    calls: dict = {"sent": [], "released": 0}
    mod = types.ModuleType("SpoutGL")
    mod.enums = types.SimpleNamespace(GL_RGBA=0x1908)
    mod.helpers = types.SimpleNamespace(isBufferEmpty=lambda buf: not any(buf))

    class SpoutSender:
        def setSenderName(self, name):
            calls["name"] = name

        def sendImage(self, data, w, h, fmt, invert, host_fbo):
            calls["sent"].append((data.copy(), w, h, fmt, invert))
            return True

        def setFrameSync(self, name):
            calls["sync"] = name

        def releaseSender(self):
            calls["released"] += 1

    class SpoutReceiver:
        def __init__(self):
            self.stage = 0

        def setReceiverName(self, name):
            calls["recv_name"] = name

        def receiveImage(self, buffer, fmt, invert, fbo):
            if buffer is not None:
                buffer[:] = bytes([1, 2, 3, 4]) * (len(buffer) // 4)
            return True

        def isUpdated(self):
            self.stage += 1
            return self.stage == 1

        def getSenderWidth(self):
            return 3

        def getSenderHeight(self):
            return 2

        def isFrameNew(self):
            return True

        def getSenderList(self):
            return ["B", "A"]

        def releaseReceiver(self):
            calls["released"] += 1

    mod.SpoutSender, mod.SpoutReceiver = SpoutSender, SpoutReceiver
    monkeypatch.setitem(sys.modules, "SpoutGL", mod)
    monkeypatch.setattr(get_backend("spout"), "platforms", ("linux", "win32"))
    return calls


def test_spout_send_and_receive_with_fake_native(monkeypatch):
    calls = _fake_spout(monkeypatch)
    backend = get_backend("spout")
    assert backend.is_available()
    assert backend.discover() == ["A", "B"]

    pixels = np.arange(2 * 3 * 4, dtype=np.uint8).reshape(2, 3, 4)
    pixels.flags.writeable = False
    with backend.create_sender("out") as sender:
        sender.send(pixels)
    data, w, h, fmt, invert = calls["sent"][0]
    assert (w, h, fmt, invert) == (3, 2, 0x1908, False)
    assert np.array_equal(data, pixels.reshape(-1))
    assert calls["sync"] == "out"

    with backend.create_receiver("out") as receiver:
        assert receiver.poll() is None  # first call only learns the sender's size
        frame = receiver.poll()
    assert (frame.width, frame.height) == (3, 2)
    assert tuple(frame.pixels[0, 0]) == (1, 2, 3, 4)
    assert calls["released"] == 3  # discover, sender, receiver


def _fake_syphon(monkeypatch):
    calls: dict = {"published": []}
    syphon = types.ModuleType("syphon")

    class Texture:
        def __init__(self, w, h):
            self._w, self._h = w, h

        def width(self):
            return self._w

        def height(self):
            return self._h

    class Server:
        device = object()

        def __init__(self, name):
            calls["server"] = name

        def publish_frame_texture(self, tex, size=None, is_flipped=False):
            calls["published"].append((tex.width(), tex.height(), size, is_flipped))

        def stop(self):
            calls["stopped"] = True

    class Directory:
        servers: ClassVar = [
            types.SimpleNamespace(app_name="App", name="Out"),
            types.SimpleNamespace(app_name="Solo", name=""),
        ]

        def update_run_loop(self):
            calls["pumped"] = calls.get("pumped", 0) + 1

        def stop(self):
            pass

    syphon.SyphonMetalServer, syphon.SyphonServerDirectory = Server, Directory
    utils = types.ModuleType("syphon.utils")
    np_mod = types.ModuleType("syphon.utils.numpy")
    np_mod.copy_image_to_mtl_texture = lambda image, tex: calls.setdefault("copied", image.shape)
    raw = types.ModuleType("syphon.utils.raw")
    raw.create_mtl_texture = lambda device, w, h: Texture(w, h)
    for name, m in (
        ("syphon", syphon),
        ("syphon.utils", utils),
        ("syphon.utils.numpy", np_mod),
        ("syphon.utils.raw", raw),
    ):
        monkeypatch.setitem(sys.modules, name, m)
    monkeypatch.setattr(get_backend("syphon"), "platforms", ("linux", "darwin"))
    return calls


def test_syphon_send_and_discover_with_fake_native(monkeypatch):
    calls = _fake_syphon(monkeypatch)
    backend = get_backend("syphon")
    assert backend.discover() == ["App | Out", "Solo"]
    with backend.create_sender("pub") as sender:
        sender.send(np.zeros((4, 6, 4), np.uint8))
        sender.send(np.zeros((4, 6, 4), np.uint8))
    assert calls["server"] == "pub"
    assert calls["copied"] == (4, 6, 4)
    assert calls["published"][0] == (6, 4, [6, 4], True)
    assert calls["stopped"] and calls["pumped"] >= 2


def test_gated_factories_raise_when_dependency_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "SpoutGL", None)  # import -> ImportError
    monkeypatch.setattr(get_backend("spout"), "platforms", ("linux", "win32"))
    with pytest.raises(BackendUnavailable, match="SpoutGL"):
        get_backend("spout").create_sender("x")
