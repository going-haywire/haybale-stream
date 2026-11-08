"""Send Frame / Receive Frame: registration, port layout, and an end-to-end loopback."""

import time
import uuid

import numpy as np
import pytest
from haybale_image.value import ChannelOrder, ImageValue, Layout

pytestmark = [pytest.mark.unit]


class _StubWrapper:
    graph = None
    state = None

    def mark_as_structuraly_dirty(self):
        pass


def _build(cls):
    node = cls(node_id="test-node", wrapper=_StubWrapper())
    node.init()
    node._regenerate_promoted_ports()
    node.post_init()
    return node


def _solid(width, height, rgb):
    arr = np.empty((height, width, 3), np.uint8)
    arr[:] = rgb
    return ImageValue.from_array(arr)


def test_library_registers_both_nodes(library_system):
    from haywire.core.node.registry import NodeRegistry

    registry = library_system.injector.get(NodeRegistry)
    for name in ("SendFrameNode", "ReceiveFrameNode"):
        assert registry.get(f"haybale-stream:node:{name}") is not None


def test_port_layout(library_system):
    from haybale_stream.nodes import ReceiveFrameNode, SendFrameNode

    send = _build(SendFrameNode)
    assert set(send.ports) == {"exec", "image", "next"}
    recv = _build(ReceiveFrameNode)
    assert set(recv.ports) == {"exec", "frame", "none", "image"}


def test_send_rejects_empty_image(library_system):
    from haybale_stream.nodes import SendFrameNode

    node = _build(SendFrameNode)
    with pytest.raises(ValueError, match="empty"):
        node.worker(None, ImageValue.empty(Layout.RGB))


def test_unavailable_backend_is_reported_not_crashed(library_system):
    from haybale_stream.backends import get_backend
    from haybale_stream.nodes import SendFrameNode

    if get_backend("spout").is_available():
        pytest.skip("Spout is native here")
    node = _build(SendFrameNode)
    node.stream.backend = "spout"
    with pytest.raises(RuntimeError, match="not available"):
        node.worker(None, _solid(4, 4, (1, 2, 3)))


@pytest.mark.network
@pytest.mark.integration
@pytest.mark.parametrize("backend", ["ndi", "omt"])
def test_send_node_to_receive_node(library_system, backend):
    from haybale_stream.backends import get_backend
    from haybale_stream.nodes import ReceiveFrameNode, SendFrameNode

    if not get_backend(backend).is_available():
        pytest.skip("backend unavailable")
    name = f"hbnode-{uuid.uuid4().hex[:8]}"

    send = _build(SendFrameNode)
    send.stream.backend = backend
    send.stream.name = name
    recv = _build(ReceiveFrameNode)
    recv.stream.backend = backend
    got = {}
    recv.out = lambda port, value: got.__setitem__(port, value)

    image = _solid(48, 32, (220, 40, 10))
    try:
        assert send.worker(None, image) == "next"
        sources = []
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not sources:
            sources = [s for s in get_backend(backend).discover(wait=1.0) if name in s]
        assert sources, "sender never became visible"
        recv.stream.source = sources[0]

        deadline = time.monotonic() + 10
        result = "none"
        while time.monotonic() < deadline and result != "frame":
            send.worker(None, image)
            result = recv.worker(None)
            time.sleep(0.05)
        assert result == "frame"
        out = got["image"]
        assert (out.width, out.height) == (48, 32)
        px = out.array(np.uint8, ChannelOrder.RGB)[16, 24]
        assert px[0] > 170 and px[1] < 90 and px[2] < 60  # red survives the codec, in RGB order
    finally:
        send.on_teardown()
        recv.on_teardown()


def test_receive_without_source_returns_none(library_system):
    from haybale_stream.nodes import ReceiveFrameNode

    node = _build(ReceiveFrameNode)
    node.out = lambda *a: pytest.fail("no frame expected")
    assert node.worker(None) == "none"
