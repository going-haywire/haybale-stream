"""Receive Frame Emit — a receiver thread that pushes every new frame to Image Event nodes."""

import threading
import time

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import bag

from ..backends import get_backend
from ..backends.base import BackendUnavailable
from ..backends.convert import frame_to_image
from .settings import ReceiveSettings

_RETRY_AFTER = 2.0  # seconds between attempts to reach a source that was not there
_POLL_WAIT = 0.1  # seconds the receiver thread waits for a frame before checking for stop


@node(
    label="Receive Frame Emit",
    description="Receives frames from NDI, OMT, Syphon or Spout on its own thread and emits a callback per frame",
    menu="stream/emit",
    search_tags=["stream", "receive", "emit", "callback", "ndi", "omt", "syphon", "spout", "video", "input"],
    node_type=NodeType.CONTROL,
)
class ReceiveFrameEmitNode(BaseNode):
    """Receives frames in the background and hands each new one to the connected Image Event nodes.

    Unlike Receive Frame, nothing has to poll it: send `Start` once and every frame that
    arrives triggers the Image Event nodes wired to `Subscribers`. A source that is not
    there yet is retried every two seconds while the node runs.

    ```text
    Begin Play → Receive Frame Emit ⇢ Image Event → View Image
    ```

    Inputs:
        start: Begin receiving
        stop: Stop receiving
        callbacks: Pooled subscriptions from Image Event nodes

    Outputs:
        started / stopped: Control flow after the receiver starts or stops
    """

    stream = bag(ReceiveSettings)

    def init(self) -> None:
        from haywire.barn.builtin.types import EXEC, STRING
        from haywire.barn.builtin.widgets import SimpleLabelWidget
        from haybale_core.types import PooledType
        from haybale_image.types.callback import CALLBACK_IMAGE

        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))
        self.add(
            PooledType[CALLBACK_IMAGE].as_inlet(
                "callbacks", label="Subscribers", description="Connect to Image Event nodes"
            )
        )
        self.add(STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config()))
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
            self.hb_status(f"Error: {reason}")
            raise RuntimeError(reason)
        with self.hb_lock:
            if self.hb_thread is not None and self.hb_thread.is_alive():
                return "started"
            # One stop event per thread, so a restart never clears the event an exiting thread has not seen.
            self.hb_stop = threading.Event()
            self.hb_thread = threading.Thread(
                target=self.hb_loop,
                args=(context, self.hb_stop, backend_key, str(self.stream.source)),
                name=f"ReceiveFrameEmit-{self.node_id}",
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
        self.hb_status("Stopped")
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

    def hb_subscribers(self) -> list[str]:
        subs = self.value("callbacks") or {}
        return [v.name for v in subs.values() if v is not None and v.name]

    def hb_loop(self, context: ExecutionContext, stop: threading.Event, backend_key: str, source: str) -> None:
        """Receiver thread: connect (retrying), then emit one callback per new frame."""
        backend = get_backend(backend_key)
        receiver = None
        frame_number = 0
        started = time.monotonic()
        try:
            while not stop.is_set():
                if receiver is None:
                    if not source:
                        self.hb_status("No source set")
                        stop.wait(_RETRY_AFTER)
                        continue
                    self.hb_status(f"Connecting to {source}...")
                    candidate = backend.create_receiver(source)
                    try:
                        candidate.open(timeout=0.5)
                    except LookupError:
                        candidate.close()
                        stop.wait(_RETRY_AFTER)
                        continue
                    receiver = candidate
                    self.hb_status(f"Receiving {source}")
                frame = receiver.poll(_POLL_WAIT)
                if frame is None:
                    continue
                frame_number += 1
                subscribers = self.hb_subscribers()
                if not subscribers:
                    continue
                payload = {
                    "image": frame_to_image(frame, backend),
                    "timestamp": time.monotonic() - started,
                    "frame_number": frame_number,
                }
                for name in subscribers:
                    context.emit_callback(event_name=name, payload=payload)
        except BackendUnavailable as exc:
            self.hb_status(f"Error: {exc}")
        except Exception as exc:  # the thread must not die silently
            self.hb_status(f"Receive error: {exc}")
        finally:
            if receiver is not None:
                receiver.close()

    def hb_status(self, status: str) -> None:
        try:
            self.ports["status"].set_value(status)
        except Exception:
            pass
