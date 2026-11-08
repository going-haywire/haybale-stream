"""Frame Event — runs its flow for each frame a Receive Frame Emit node delivers."""

from haywire.barn.builtin.types import CHOICES, INT
from haywire.core.execution import QueueMode
from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, Promotable, bag, setting

from ..backends import get_backend
from ..backends.convert import frame_to_image

_QUEUE_MODES = {"Drop (realtime)": QueueMode.DROP, "Block (every frame)": QueueMode.BLOCK}


class DispatchSettings(NodeSettings):
    """How incoming frame callbacks queue. Applies on the next start."""

    queue_mode = setting[CHOICES](
        "Drop (realtime)",
        label="Queue Mode",
        category="Dispatch",
        description=(
            "Drop keeps only the newest frame (live preview). Block queues every frame "
            "and back-pressures the receiver."
        ),
        widget_config={"options": list(_QUEUE_MODES)},
        promotable=Promotable.CONFIG,
    )
    max_queue_size = setting[INT](
        1,
        min=1,
        max=256,
        label="Max Queue Size",
        category="Dispatch",
        description="How many pending frames to hold. Drop mode needs 1 to guarantee newest-wins.",
        promotable=Promotable.CONFIG,
    )


@node(
    label="Frame Event",
    description="Triggered for each frame a Receive Frame Emit node delivers",
    menu="stream/event",
    search_tags=["stream", "frame", "event", "receive", "ndi", "omt", "syphon", "spout", "image"],
    node_type=NodeType.EVENT,
)
class FrameEventNode(BaseNode):
    """Runs its flow once per frame from the Receive Frame Emit node it is wired to.

    Connect `Listen` to the `Subscribers` inlet of a Receive Frame Emit.

    Outputs:
        frame_ready: Control flow when a frame arrives
        image: The frame
        frame_number / timestamp: Count and seconds since the emitter started
    """

    dispatch = bag(DispatchSettings)

    def init(self) -> None:
        from haybale_image.types.image import IMAGE_RGBA
        from haywire.barn.builtin.types import CALLBACK, EXEC, FLOAT

        self.add(CALLBACK.as_outlet("listen_callback", label="Listen", default=self.node_id))
        self.add(EXEC.as_outlet("frame_ready", label="Frame Ready"))
        self.add(IMAGE_RGBA.as_outlet("image", label="Image"))
        self.add(FLOAT.as_outlet("timestamp", label="Timestamp (s)"))
        self.add(INT.as_outlet("frame_number", label="Frame Number"))

    def post_init(self) -> None:
        # A copy or a loaded graph restores the saved id; the listener publishes the id it listens on.
        self.ports["listen_callback"].set_value(self.node_id)
        self.event_subscription = CallbackEvent(
            event_name=self.node_id,
            queue_mode=_QUEUE_MODES.get(str(self.dispatch.queue_mode), QueueMode.DROP),
            max_queue_size=int(self.dispatch.max_queue_size),
        )

    def worker(self, context: ExecutionContext) -> str | None:
        payload = context.trigger.payload if context.trigger else None
        if not isinstance(payload, dict) or payload.get("frame") is None:
            return None
        backend = get_backend(str(payload["backend"]))
        self.out("image", frame_to_image(payload["frame"], backend))
        self.out("timestamp", payload.get("timestamp", 0.0))
        self.out("frame_number", payload.get("frame_number", 0))
        return "frame_ready"
