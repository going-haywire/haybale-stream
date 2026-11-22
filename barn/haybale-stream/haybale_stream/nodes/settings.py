"""Settings shared by the stream nodes."""

from haywire.api import BOOL, CHOICES, FLOAT, INT, STRING, MenuWidget, NodeSettings, setting

from ..backends import BACKENDS, audio_backends, available_backends
from ..backends.sources import all_known_sources, find_sources, known_sources
from .run_loop import ensure_main_run_loop


def source_options(bag: "ReceiveSettings | None" = None) -> list[str]:
    """Senders the last refresh found on the bag's backend; on every backend without a bag.

    The default keeps this working with a framework that calls options without the bag.
    """
    return all_known_sources() if bag is None else known_sources(str(bag.backend))


def find_source_options(bag: "ReceiveSettings | None" = None) -> list[str]:
    """Query the bag's backend for senders now (the Source dropdown's refresh button)."""
    key = "ndi" if bag is None else str(bag.backend)
    ensure_main_run_loop(key)
    return find_sources(key)


def audio_source_options(bag: "AudioReceiveSettings | None" = None) -> list[str]:
    """Audio senders the last refresh found on the bag's backend (OMT without a bag)."""
    return known_sources("omt" if bag is None else str(bag.backend))


def find_audio_source_options(bag: "AudioReceiveSettings | None" = None) -> list[str]:
    """Query the bag's backend for audio senders now (the Source dropdown's refresh button)."""
    return find_sources("omt" if bag is None else str(bag.backend))


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
    flip = setting[BOOL](
        False,
        label="Flip vertically",
        category="Stream",
        description="Send the image upside down, for receivers that show it the wrong way up",
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
        description="Name of the sender to receive from; refresh to look for senders, or type it",
        widget=MenuWidget.config(
            properties={
                "options": source_options,
                "refresh": find_source_options,
                "new_value_mode": "add-unique",
            }
        ),
    )
    flip = setting[BOOL](
        False,
        label="Flip vertically",
        category="Stream",
        description="Turn received frames upside down, for senders that send them the wrong way up",
    )


def audio_backend_options() -> list[str]:
    """Backend keys that carry audio and can run on this machine (OMT is always among them)."""
    return [b.key for b in audio_backends()] or ["omt"]


class AudioSendSettings(NodeSettings):
    """Where the audio goes."""

    backend = setting[CHOICES](
        "omt",
        label="Backend",
        category="Stream",
        description="Transport to publish audio on",
        widget_config={"options": audio_backend_options()},
    )
    name = setting[STRING](
        "haywire-audio",
        label="Name",
        category="Stream",
        description="Name other applications see for this sender",
    )
    fifo_blocks = setting[INT](
        64,
        min=2,
        max=1024,
        label="FIFO blocks",
        category="Stream",
        description="Blocks queued between the flow and the network; a full FIFO drops new blocks",
    )


class AudioReceiveSettings(NodeSettings):
    """What audio to listen to."""

    backend = setting[CHOICES](
        "omt",
        label="Backend",
        category="Stream",
        description="Transport to receive from",
        widget_config={"options": audio_backend_options()},
    )
    source = setting[STRING](
        "",
        label="Source",
        category="Stream",
        description="Name of the sender to receive from; refresh to look for senders, or type it",
        widget=MenuWidget.config(
            properties={
                "options": audio_source_options,
                "refresh": find_audio_source_options,
                "new_value_mode": "add-unique",
            }
        ),
    )
