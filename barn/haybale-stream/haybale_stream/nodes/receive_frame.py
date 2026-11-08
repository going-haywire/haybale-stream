"""Receive Frame — pull the newest image from an NDI, OMT, Syphon or Spout source."""

import time

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import bag

from ..backends import Receiver, get_backend
from ..backends.base import BackendUnavailable
from ..backends.convert import frame_to_image
from .settings import ReceiveSettings

_RETRY_AFTER = 2.0  # seconds between attempts to reach a source that was not there


@node(
    label="Receive Frame",
    description="Receives the newest image from another application over NDI, OMT, Syphon or Spout",
    menu="stream",
    search_tags=["stream", "receive", "ndi", "omt", "syphon", "spout", "video", "input", "texture sharing"],
    node_type=NodeType.CONTROL,
)
class ReceiveFrameNode(BaseNode):
    """Fetches the newest frame from `Source` each time it runs and passes it on as `Image`.

    Control continues through `Frame` when a frame newer than the last one arrived, and
    through `No frame` otherwise (no sender, or nothing new yet). `Image` then keeps the
    last frame received, so a downstream node never sees an empty image after the first.

    - `Backend`: NDI and OMT run on every platform; Syphon only on macOS, Spout only
      on Windows.
    - `Source`: pick a discovered sender or type its name. A source that is not there
      yet is retried every two seconds while the node runs.

    ```text
    Receive Frame → View Image
    ```
    """

    stream = bag(ReceiveSettings)

    def init(self) -> None:
        from haybale_image.types.image import IMAGE_RGBA
        from haywire.barn.builtin.types import EXEC

        self.add(EXEC.as_inlet("exec", label="Execute", description="Fetches the newest frame"))
        self.add(EXEC.as_outlet("frame", label="Frame", description="A new frame arrived"))
        self.add(EXEC.as_outlet("none", label="No frame", description="No new frame"))
        self.add(IMAGE_RGBA.as_outlet("image", label="Image", description="The newest frame received"))

    def post_init(self) -> None:
        self.hb_receiver: Receiver | None = None
        self.hb_receiver_key: tuple[str, str] | None = None
        self.hb_retry_at = 0.0

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_close()

    def on_teardown(self) -> None:
        self.hb_close()

    def hb_close(self) -> None:
        receiver, self.hb_receiver, self.hb_receiver_key = getattr(self, "hb_receiver", None), None, None
        if receiver is not None:
            receiver.close()

    def hb_ensure_receiver(self) -> Receiver | None:
        """The connected receiver, or ``None`` while the source is missing (retried, not raised)."""
        key = (str(self.stream.backend), str(self.stream.source))
        if self.hb_receiver is not None and self.hb_receiver_key == key:
            return self.hb_receiver
        self.hb_close()
        if not key[1] or time.monotonic() < self.hb_retry_at:
            return None
        receiver = get_backend(key[0]).create_receiver(key[1])
        try:
            receiver.open(timeout=0.5)
        except LookupError:
            self.hb_retry_at = time.monotonic() + _RETRY_AFTER
            return None
        self.hb_receiver, self.hb_receiver_key = receiver, key
        return receiver

    def worker(self, context: ExecutionContext) -> str:
        backend = get_backend(str(self.stream.backend))
        try:
            receiver = self.hb_ensure_receiver()
        except BackendUnavailable as exc:
            raise RuntimeError(str(exc)) from exc
        frame = None if receiver is None else receiver.poll()
        if frame is None:
            return "none"
        self.out("image", frame_to_image(frame, backend))
        return "frame"
