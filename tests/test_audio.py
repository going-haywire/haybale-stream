"""OMT audio: block conversion, send timestamps, the send FIFO, the nodes, and an OMT loopback."""

import socket
import threading
import time
import uuid

import numpy as np
import pytest
from haybale_audio.value import AudioBlock
from haybale_stream.backends import AudioPacket, AudioSender, BackendUnavailable, get_backend
from haybale_stream.backends.audio_convert import packet_to_block
from haybale_stream.backends.audio_send import AudioSendQueue, timestamp_ticks

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


class _FakeSender(AudioSender):
    def __init__(self, delay: float = 0.0, fail: bool = False):
        super().__init__("fake")
        self.sent: list[tuple[np.ndarray, int, int]] = []
        self.delay, self.fail = delay, fail
        self.closed = False

    def open(self):
        pass

    def send_audio(self, samples, sample_rate, timestamp):
        if self.fail:
            raise OSError("wire down")
        time.sleep(self.delay)
        self.sent.append((samples, sample_rate, timestamp))

    def close(self):
        self.closed = True


def _wait(condition, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.005)
    raise AssertionError("condition not met in time")


def _block(channels=2, frames=256, value=0.5):
    return np.full((channels, frames), value, np.float32)


# --- conversion -------------------------------------------------------------------------


def test_packet_to_block_keeps_rate_and_channels_and_owns_its_bytes():
    samples = _block(3, 480, 0.25)
    block = packet_to_block(AudioPacket(samples, 44100, 123))
    assert (block.channels, block.frames, block.sample_rate) == (3, 480, 44100)
    samples[:] = 0.0  # the backend reusing its buffer must not reach the block
    assert float(block.data[0, 0]) == 0.25
    assert not block.data.flags.writeable


def test_packet_properties():
    packet = AudioPacket(_block(2, 64), 48000)
    assert (packet.channels, packet.frames, packet.timestamp) == (2, 64, None)


# --- timestamps -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("count", "rate", "ticks"),
    [(0, 48000, 0), (48000, 48000, 10_000_000), (256, 48000, 53_333), (44100, 44100, 10_000_000)],
)
def test_timestamp_ticks_from_sample_count(count, rate, ticks):
    assert timestamp_ticks(count, rate) == ticks


def test_queue_stamps_blocks_from_the_sample_count():
    sender = _FakeSender()
    queue = AudioSendQueue(sender)
    queue.start()
    try:
        for _ in range(4):
            queue.put(_block(frames=256), 48000)
        _wait(lambda: len(sender.sent) == 4)
    finally:
        queue.stop()
    assert [t for _, _, t in sender.sent] == [timestamp_ticks(256 * i, 48000) for i in range(4)]
    assert queue.sample_count == 1024


def test_queue_restarts_the_count_when_the_format_changes():
    sender = _FakeSender()
    queue = AudioSendQueue(sender)
    queue.start()
    try:
        queue.put(_block(2, 256), 48000)
        queue.put(_block(2, 256), 48000)
        queue.put(_block(2, 441), 44100)
        queue.put(_block(1, 441), 44100)
        _wait(lambda: len(sender.sent) == 4)
    finally:
        queue.stop()
    assert [t for _, _, t in sender.sent] == [0, timestamp_ticks(256, 48000), 0, 0]


# --- the FIFO ---------------------------------------------------------------------------


def test_queue_copies_the_block_before_queueing():
    sender = _FakeSender(delay=0.05)
    queue = AudioSendQueue(sender)
    source = _block(value=1.0)
    queue.put(source, 48000)
    source[:] = -1.0  # the producer reusing its buffer after put()
    queue.start()
    try:
        _wait(lambda: len(sender.sent) == 1)
    finally:
        queue.stop()
    assert float(sender.sent[0][0][0, 0]) == 1.0


def test_full_fifo_drops_new_blocks_and_counts_them():
    queue = AudioSendQueue(_FakeSender(), capacity=2)  # not started: nothing drains
    assert [queue.put(_block(), 48000) for _ in range(4)] == [True, True, False, False]
    assert (queue.depth, queue.dropped) == (2, 2)


def test_blocks_leave_in_order():
    sender = _FakeSender()
    queue = AudioSendQueue(sender)
    for i in range(10):
        queue.put(_block(value=float(i)), 48000)
    queue.start()
    try:
        _wait(lambda: len(sender.sent) == 10)
    finally:
        queue.stop()
    assert [float(s[0, 0]) for s, _, _ in sender.sent] == [float(i) for i in range(10)]
    assert queue.blocks_sent == 10 and queue.max_wait >= queue.last_wait >= 0.0


def test_stop_joins_the_sender_thread():
    queue = AudioSendQueue(_FakeSender())
    queue.start()
    thread = queue._thread
    assert queue.running
    queue.stop()
    assert not queue.running and thread is not None and not thread.is_alive()
    queue.stop()  # twice is fine


def test_send_failure_is_kept_and_ends_the_thread():
    queue = AudioSendQueue(_FakeSender(fail=True))
    queue.start()
    queue.put(_block(), 48000)
    _wait(lambda: queue.error is not None)
    assert isinstance(queue.error, OSError)
    _wait(lambda: not queue.running)
    queue.stop()


# --- nodes ------------------------------------------------------------------------------


def test_library_registers_audio_nodes(library_system):
    from haywire.core.node.registry import NodeRegistry

    registry = library_system.injector.get(NodeRegistry)
    for name in ("SendAudioNode", "ReceiveAudioEmitNode"):
        assert registry.get(f"haybale-stream:node:{name}") is not None


def test_audio_port_layouts(library_system):
    from haybale_stream.nodes import ReceiveAudioEmitNode, SendAudioNode

    send = _build(SendAudioNode)
    assert {"write", "stop", "audio", "next", "status"} <= set(send.ports)
    emit = _build(ReceiveAudioEmitNode)
    assert {"start", "stop", "callbacks", "started", "stopped", "status"} <= set(emit.ports)


def test_only_omt_carries_audio():
    assert get_backend("omt").supports_audio
    for key in ("ndi", "syphon", "spout"):
        backend = get_backend(key)
        assert not backend.supports_audio
        with pytest.raises(BackendUnavailable, match="does not carry audio"):
            backend.create_audio_sender("x")
        with pytest.raises(BackendUnavailable, match="does not carry audio"):
            backend.create_audio_receiver("x")


def test_send_audio_requires_a_block(library_system):
    from haybale_stream.nodes import SendAudioNode

    node = _build(SendAudioNode)

    class Ctx:
        control_pin = "write"

    with pytest.raises(ValueError, match="audio block"):
        node.worker(Ctx(), None)


def test_send_audio_node_queues_blocks_and_stop_closes(library_system, monkeypatch):
    from haybale_stream.backends.omt import OMTBackend
    from haybale_stream.nodes import SendAudioNode

    sender = _FakeSender()
    monkeypatch.setattr(OMTBackend, "create_audio_sender", classmethod(lambda cls, name: sender))
    node = _build(SendAudioNode)

    class Ctx:
        control_pin = "write"

    for _ in range(3):
        assert node.worker(Ctx(), AudioBlock(_block(), 48000)) == "next"
    _wait(lambda: len(sender.sent) == 3)
    thread = node.hb_queue._thread
    Ctx.control_pin = "stop"
    node.worker(Ctx(), None)
    assert sender.closed and not thread.is_alive() and node.hb_queue is None
    node.on_teardown()


class _FakeReceiver:
    def __init__(self, packets):
        self.packets = list(packets)
        self.closed = False

    def open(self, timeout=5.0):
        pass

    def receive_audio(self, timeout=0.0):
        if self.packets:
            return self.packets.pop(0)
        time.sleep(min(timeout, 0.01))
        return None

    def close(self):
        self.closed = True


def test_receive_emit_delivers_one_block_per_packet_and_joins_on_stop(library_system, monkeypatch):
    from haybale_stream.backends.omt import OMTBackend
    from haybale_stream.nodes import ReceiveAudioEmitNode

    ticks = 10_000_000 // 100  # 10 ms
    packets = [AudioPacket(_block(2, 480, float(i)), 48000, 5_000 + i * ticks) for i in range(3)]
    packets.append(AudioPacket(_block(1, 441, 9.0), 44100, None))
    receiver = _FakeReceiver(packets)
    monkeypatch.setattr(OMTBackend, "create_audio_receiver", classmethod(lambda cls, source: receiver))

    emitted: list[tuple[str, dict]] = []

    class Ctx:
        control_pin = "start"

        def emit_callback(self, event_name, payload):
            emitted.append((event_name, payload))

    class Sub:
        name = "listener"

    node = _build(ReceiveAudioEmitNode)
    node.stream.source = "somewhere"
    node.value = lambda port: {"a": Sub()} if port == "callbacks" else None
    assert (
        node.worker(
            Ctx(),
        )
        == "started"
    )
    _wait(lambda: len(emitted) == 4)
    thread = node.hb_thread
    Ctx.control_pin = "stop"
    assert node.worker(Ctx()) == "stopped"
    assert thread is not None and not thread.is_alive() and receiver.closed

    payloads = [p for _, p in emitted]
    assert {name for name, _ in emitted} == {"listener"}
    assert [p["block_number"] for p in payloads] == [0, 1, 2, 3]
    assert [p["audio"].frames for p in payloads] == [480, 480, 480, 441]
    assert [round(p["timestamp"], 4) for p in payloads[:3]] == [
        0.0,
        0.01,
        0.02,
    ]  # relative to the first frame
    assert payloads[3]["audio"].sample_rate == 44100 and payloads[3]["audio"].channels == 1


# --- loopback ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture
def omt_pair():
    """An OMT audio sender and receiver on this machine, one process, fixed local port."""
    backend = get_backend("omt")
    if not backend.is_available():
        pytest.skip(backend.unavailable_reason())
    import cyomtlib as omt

    port = _free_port()
    omt.settings.set_integer("NetworkPortStart", port)
    omt.settings.set_integer("NetworkPortEnd", port)
    sender = backend.create_audio_sender(f"hbaudio-{uuid.uuid4().hex[:8]}")
    sender.open()
    receiver = backend.create_audio_receiver(f"omt://127.0.0.1:{port}")
    receiver.open()
    deadline = time.monotonic() + 10
    while sender._sender.connections < 1 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert sender._sender.connections >= 1, "receiver did not connect"
    yield sender, receiver
    receiver.close()
    sender.close()


def _seq_block(seq: int, frames: int = 256, channels: int = 2) -> np.ndarray:
    block = np.full((channels, frames), 0.01, np.float32)
    block[0, 0] = seq  # exact for seq < 2**24
    return block


@pytest.mark.network
@pytest.mark.integration
def test_loopback_256_frame_blocks_lose_nothing_with_low_latency(omt_pair):
    sender, receiver = omt_pair
    rate, frames, count = 48000, 256, 400
    period = frames / rate
    sent_at: dict[int, int] = {}
    got: list[tuple[int, int, AudioPacket]] = []
    stop = threading.Event()

    def rx():
        while not stop.is_set():
            packet = receiver.receive_audio(0.05)
            if packet is not None:
                got.append((int(round(float(packet.samples[0, 0]))), time.perf_counter_ns(), packet))

    thread = threading.Thread(target=rx, daemon=True)
    thread.start()
    queue = AudioSendQueue(sender)
    queue.start()
    try:
        t0 = time.perf_counter()
        for i in range(count):
            wait = t0 + i * period - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            sent_at[i] = time.perf_counter_ns()
            queue.put(_seq_block(i, frames), rate)
        _wait(lambda: len({s for s, _, _ in got}) >= count, seconds=5.0)
    finally:
        queue.stop()
        stop.set()
        thread.join(2)

    seqs = [s for s, _, _ in got]
    assert sorted(set(seqs)) == list(range(count)), "blocks were lost"
    assert seqs == sorted(seqs)
    assert all((p.channels, p.frames, p.sample_rate) == (2, frames, rate) for _, _, p in got)
    assert queue.dropped == 0
    stamps = [p.timestamp for _, _, p in got]
    assert stamps[1] - stamps[0] == timestamp_ticks(frames, rate)
    median_ms = float(np.median([(t - sent_at[s]) / 1e6 for s, t, _ in got]))
    assert median_ms < 2.0, f"median latency {median_ms:.2f} ms"
    assert queue.max_wait < 0.05
