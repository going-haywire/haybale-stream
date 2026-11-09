"""Bridge between ``AudioBlock`` and the packets audio backends move."""

from __future__ import annotations

import numpy as np
from haybale_audio.value import AudioBlock

from .base import AudioPacket


def packet_to_block(packet: AudioPacket) -> AudioBlock:
    """Wrap a received packet as an ``AudioBlock`` at the packet's own rate and channel count.

    The block owns a copy: a backend may reuse the buffer behind the packet.
    """
    return AudioBlock(np.array(packet.samples, dtype=np.float32, order="C"), packet.sample_rate)
