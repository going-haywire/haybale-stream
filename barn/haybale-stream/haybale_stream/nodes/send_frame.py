"""Send Frame — publish an image on NDI, OMT, Syphon or Spout."""

from haybale_image.value import ImageValue
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import bag

from ..backends import Sender, get_backend
from ..backends.base import BackendUnavailable
from ..backends.convert import image_to_pixels
from .settings import SendSettings


@node(
    label="Send Frame",
    description="Publishes an image to other applications over NDI, OMT, Syphon or Spout",
    menu="stream",
    search_tags=["stream", "send", "ndi", "omt", "syphon", "spout", "video", "output", "texture sharing"],
    node_type=NodeType.CONTROL,
)
class SendFrameNode(BaseNode):
    """Publishes `Image` under `Name` on the chosen `Backend` each time it runs.

    - `Backend`: NDI and OMT run on every platform; Syphon only on macOS, Spout only
      on Windows. A backend that cannot run here makes the node report an error.
    - `Steady stream`: keeps resending the last frame so receivers do not show
      "no signal" while the graph is idle (NDI, OMT).

    The sender opens with the first frame and reopens if `Backend` or `Name` change.
    Gray and RGB images are sent with an opaque alpha channel.

    ```text
    Load Image → Send Frame
    ```
    """

    stream = bag(SendSettings)

    def init(self) -> None:
        from haybale_image.types.image import IMAGE
        from haywire.barn.builtin.types import EXEC

        self.add(EXEC.as_inlet("exec", label="Execute", description="Sends the image"))
        self.add(IMAGE.as_inlet("image", label="Image", description="Image to publish"))
        self.add(EXEC.as_outlet("next", label="Next", description="Runs after sending"))

    def post_init(self) -> None:
        self.hb_sender: Sender | None = None
        self.hb_sender_key: tuple[str, str, bool] | None = None

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_close()

    def on_teardown(self) -> None:
        self.hb_close()

    def hb_close(self) -> None:
        sender, self.hb_sender, self.hb_sender_key = getattr(self, "hb_sender", None), None, None
        if sender is not None:
            sender.close()

    def hb_ensure_sender(self) -> Sender:
        key = (str(self.stream.backend), str(self.stream.name), bool(self.stream.steady_stream))
        if self.hb_sender is not None and self.hb_sender_key == key:
            return self.hb_sender
        self.hb_close()
        backend_key, name, steady = key
        sender = get_backend(backend_key).create_sender(name, steady_stream=steady)
        sender.open()
        self.hb_sender, self.hb_sender_key = sender, key
        return sender

    def worker(self, context: ExecutionContext, image: ImageValue) -> str:
        if image.is_empty:
            raise ValueError("image is empty")
        backend = get_backend(str(self.stream.backend))
        try:
            sender = self.hb_ensure_sender()
        except BackendUnavailable as exc:
            raise RuntimeError(str(exc)) from exc
        sender.send(image_to_pixels(image, backend.channel_order), float(self.stream.frame_rate))
        return "next"
