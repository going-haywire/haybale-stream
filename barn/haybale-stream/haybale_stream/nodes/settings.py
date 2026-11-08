"""Settings shared by the stream nodes."""

from haywire.barn.builtin.types import BOOL, CHOICES, FLOAT, STRING
from haywire.barn.builtin.widgets import SelectWidget
from haywire.core.settings import NodeSettings, setting

from ..backends import BACKENDS, available_backends
from ..backends.sources import all_cached_sources


def backend_options() -> list[str]:
    """Backend keys that can run on this machine (NDI is always among them)."""
    return [b.key for b in available_backends()] or ["ndi"]


class SendSettings(NodeSettings):
    """Where the frames go."""

    backend = setting[CHOICES](
        "ndi",
        label="Backend",
        category="Stream",
        description="Transport to publish on: " + ", ".join(b.label for b in BACKENDS.values()),
        widget_config={"options": backend_options()},
    )
    name = setting[STRING](
        "haywire",
        label="Name",
        category="Stream",
        description="Name other applications see for this sender",
    )
    frame_rate = setting[FLOAT](
        30.0,
        min=1.0,
        max=240.0,
        label="Frame rate",
        category="Stream",
        description="Frame rate announced to receivers (NDI and OMT pace sending to it)",
    )
    steady_stream = setting[BOOL](
        True,
        label="Steady stream",
        category="Stream",
        description="Keep resending the last frame while no new one arrives (NDI, OMT)",
    )


class ReceiveSettings(NodeSettings):
    """What to listen to."""

    backend = setting[CHOICES](
        "ndi",
        label="Backend",
        category="Stream",
        description="Transport to receive from",
        widget_config={"options": backend_options()},
    )
    source = setting[STRING](
        "",
        label="Source",
        category="Stream",
        description="Name of the sender to receive from; pick a discovered one or type it",
        widget=SelectWidget.config(
            properties={"options": all_cached_sources, "new_value_mode": "add-unique"}
        ),
    )
