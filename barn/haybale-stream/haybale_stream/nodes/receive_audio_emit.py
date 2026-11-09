"""Receive Audio Emit — a receiver thread that pushes every received audio block to Audio Event nodes."""

import threading
import time

from haybale_audio.emitter import deliver_to_subscribers, set_status
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import bag

from ..backends import get_backend
from ..backends.audio_convert import packet_to_block
from ..backends.audio_send import TICKS_PER_SECOND
from ..backends.base import BackendUnavailable
from .settings import AudioReceiveSettings

_RETRY_AFTER = 2.0  # seconds between attempts to reach a source that was not there
_POLL_WAIT = 0.05  # seconds the receiver thread waits for a block before checking for stop


@node(
    label="Receive Audio Emit",
    description="Receives audio from an OMT source on its own thread and emits a callback per block",
    menu="stream/emit",
    search_tags=["stream", "receive", "emit", "callback", "omt", "audio", "sound", "input"],
    node_type=NodeType.CONTROL,
)
class ReceiveAudioEmitNode(BaseNode):
    """Receives audio in the background and hands each block to the connected Audio Event nodes.

    Send `Start` once and every block that arrives triggers the Audio Event nodes wired to
    `Subscribers`. The remote sender owns the clock: each OMT frame becomes one block at the
    frame's own sample rate and channel count, so a node that needs another format converts it
    (Reblock/Resample). A source that is not there yet is retried every two seconds.

    ```text
    Begin Play → Receive Audio Emit ⇢ Audio Event → Device Out
    ```

    Inputs:
        start: Begin receiving
        stop: Stop receiving
        callbacks: Pooled CALLBACK_AUDIO subscriptions from Audio Event nodes

    Outputs:
        started / stopped: Control flow after the receiver starts or stops
    """

    stream = bag(AudioReceiveSettings)

    def init(self) -> None:
        from haybale_audio.types.callback import CALLBACK_AUDIO
        from haybale_core.types import PooledType
        from haywire.barn.builtin.types import EXEC, STRING
        from haywire.barn.builtin.widgets import SimpleLabelWidget

        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))
        self.add(
            PooledType[CALLBACK_AUDIO].as_inlet(
                "callbacks", label="Subscribers", description="Connect to Audio Event nodes"
            )
        )
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
        )
        self.add(EXEC.as_outlet("started", label="Started"))
        self.add(EXEC.as_outlet("stopped", label="Stopped"))

    def post_init(self) -> None:
        self.hb_thread: threading.Thread | None = None
        self.hb_stop = threading.Event()
        self.hb_lock = threading.Lock()

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_stop_receiving()

    def on_teardown(self) -> None:
        self.hb_stop_receiving()

    def worker(self, context: ExecutionContext) -> str | None:
        if context.control_pin == "start":
            return self.hb_start(context)
        if context.control_pin == "stop":
            return self.hb_stop_and_report()
        return None

    def hb_start(self, context: ExecutionContext) -> str | None:
        backend_key = str(self.stream.backend)
        reason = get_backend(backend_key).unavailable_reason()
        if reason is not None:
            set_status(self, f"Error: {reason}")
            raise RuntimeError(reason)
        with self.hb_lock:
            if self.hb_thread is not None and self.hb_thread.is_alive():
                return "started"
            # One stop event per thread, so a restart never clears the event an exiting thread has not seen.
            self.hb_stop = threading.Event()
            self.hb_thread = threading.Thread(
                target=self.hb_loop,
                args=(context, self.hb_stop, backend_key, str(self.stream.source)),
                name=f"ReceiveAudioEmit-{self.node_id}",
                daemon=True,
            )
            self.hb_thread.start()
        return "started"

    def hb_stop_and_report(self) -> str | None:
        with self.hb_lock:
            running = self.hb_thread is not None
        if not running:
            return None
        self.hb_stop_receiving()
        set_status(self, "Stopped")
        return "stopped"

    def hb_stop_receiving(self) -> None:
        # post_init() may never have run (init() failed during a reset), so the attributes may be absent.
        lock = getattr(self, "hb_lock", None)
        if lock is None:
            return
        with lock:
            thread, self.hb_thread = self.hb_thread, None
            self.hb_stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5.0)

    def hb_loop(
        self, context: ExecutionContext, stop: threading.Event, backend_key: str, source: str
    ) -> None:
        """Receiver thread: connect (retrying), then emit one callback per received block."""
        backend = get_backend(backend_key)
        receiver = None
        number = 0
        first_ticks: int | None = None
        started = time.monotonic()
        try:
            while not stop.is_set():
                if receiver is None:
                    if not source:
                        set_status(self, "No source set")
                        stop.wait(_RETRY_AFTER)
                        continue
                    set_status(self, f"Connecting to {source}...")
                    candidate = backend.create_audio_receiver(source)
                    try:
                        candidate.open(timeout=0.5)
                    except LookupError:
                        candidate.close()
                        stop.wait(_RETRY_AFTER)
                        continue
                    receiver = candidate
                    set_status(self, f"Receiving {source}")
                packet = receiver.receive_audio(_POLL_WAIT)
                if packet is None:
                    continue
                if packet.timestamp is None:
                    seconds = time.monotonic() - started
                else:
                    if first_ticks is None:
                        first_ticks = packet.timestamp
                    seconds = (packet.timestamp - first_ticks) / TICKS_PER_SECOND
                deliver_to_subscribers(
                    context, self.value("callbacks"), packet_to_block(packet), number, seconds
                )
                number += 1
        except BackendUnavailable as exc:
            set_status(self, f"Error: {exc}")
        except Exception as exc:  # the thread must not die silently
            set_status(self, f"Receive error: {exc}")
        finally:
            if receiver is not None:
                receiver.close()
