"""Send Audio — publish the audio blocks of a flow over OMT."""

import time

from haybale_audio.emitter import set_status
from haybale_audio.value import AudioBlock
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import bag

from ..backends import get_backend
from ..backends.audio_send import AudioSendQueue
from ..backends.base import AudioSender, BackendUnavailable
from .settings import AudioSendSettings

#: Seconds between status updates; one per block would flood the UI.
STATUS_INTERVAL = 0.5
#: Blocks below this many frames make the receiver drop some (0.03 to 0.3% at 64 frames).
MIN_GOOD_FRAMES = 256


@node(
    label="Send Audio",
    description="Publishes the audio blocks of a flow to other applications over OMT",
    menu="stream",
    search_tags=["stream", "send", "omt", "audio", "sound", "output"],
    node_type=NodeType.CONTROL,
)
class SendAudioNode(BaseNode):
    """Queues each block in a FIFO; a sender thread stamps it from the frames sent so far and publishes it.

    The stamps follow the sample count, never the arrival time, so the receiver sees a steady clock.
    The flow in front paces the blocks (File Player, Mixer, Device In). Use blocks of 256 frames or
    more: smaller ones make the receiver drop some. The status shows the FIFO depth and the blocks
    dropped when it was full.

    The sender opens with the first block and reopens if `Backend` or `Name` change.

    ```text
    Audio Event → Send Audio
    ```

    Inputs:
        write: Queue the block on `audio` (wire it to an Audio Event's Block Ready)
        stop: Close the sender; the next `write` opens it again
        audio: The block to publish

    Outputs:
        next: Control flow after a block is queued
    """

    stream = bag(AudioSendSettings)

    def init(self) -> None:
        from haybale_audio.types.audio import AUDIO
        from haywire.barn.builtin.types import EXEC, STRING
        from haywire.barn.builtin.widgets import SimpleLabelWidget

        self.add(EXEC.as_inlet("write", label="Write"))
        self.add(EXEC.as_inlet("stop", label="Stop"))
        self.add(AUDIO.as_inlet("audio", label="Audio", description="Block to publish"))
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
        )
        self.add(EXEC.as_outlet("next", label="Next", description="Runs after the block is queued"))

    def post_init(self) -> None:
        self.hb_sender: AudioSender | None = None
        self.hb_queue: AudioSendQueue | None = None
        self.hb_key: tuple[str, str, int] | None = None
        self.hb_status_at = 0.0

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_close()

    def on_teardown(self) -> None:
        self.hb_close()

    def hb_close(self) -> None:
        # post_init() may never have run (init() failed during a reset or reload).
        queue = getattr(self, "hb_queue", None)
        sender = getattr(self, "hb_sender", None)
        self.hb_queue = self.hb_sender = self.hb_key = None
        if queue is not None:
            queue.stop()
        if sender is not None:
            sender.close()

    def hb_ensure_queue(self) -> AudioSendQueue:
        key = (str(self.stream.backend), str(self.stream.name), int(self.stream.fifo_blocks))
        if self.hb_queue is not None and self.hb_key == key:
            return self.hb_queue
        self.hb_close()
        backend_key, name, capacity = key
        sender = get_backend(backend_key).create_audio_sender(name)
        sender.open()
        queue = AudioSendQueue(sender, capacity)
        queue.start()
        self.hb_sender, self.hb_queue, self.hb_key = sender, queue, key
        return queue

    def worker(self, context: ExecutionContext, audio: AudioBlock | None = None) -> str | None:
        if context.control_pin == "stop":
            self.hb_close()
            set_status(self, "Stopped")
            return None
        if audio is None:
            raise ValueError("write needs an audio block")
        try:
            queue = self.hb_ensure_queue()
        except BackendUnavailable as exc:
            raise RuntimeError(str(exc)) from exc
        if queue.error is not None:
            error = queue.error
            self.hb_close()
            raise RuntimeError(f"the audio send failed: {error}") from error
        queue.put(audio.data, audio.sample_rate)
        now = time.monotonic()
        if now - self.hb_status_at >= STATUS_INTERVAL:
            self.hb_status_at = now
            status = (
                f"Sending {audio.channels} ch at {audio.sample_rate} Hz, "
                f"queued {queue.depth}, dropped {queue.dropped}"
            )
            if audio.frames < MIN_GOOD_FRAMES:
                status += f", blocks under {MIN_GOOD_FRAMES} frames lose audio"
            set_status(self, status)
        return "next"
