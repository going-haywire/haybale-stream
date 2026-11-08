"""Bridge between ``ImageValue`` and the packed 4-channel frames backends move."""

from __future__ import annotations

import numpy as np
from haybale_image.value import ChannelOrder, ImageValue, Layout, convert_layout

from .base import Backend, Frame


def image_to_pixels(image: ImageValue, order: str) -> np.ndarray:
    """Return ``image`` as a C-contiguous ``H×W×4`` uint8 array in ``order`` (``"rgba"`` / ``"bgra"``).

    Gray and RGB images get an opaque alpha. The array may be shared with ``image``'s
    cache and is read-only: copy before writing.
    """
    rgba = convert_layout(image, Layout.RGBA)
    channel = ChannelOrder.BGR if order == "bgra" else ChannelOrder.RGB
    return np.ascontiguousarray(rgba.array(np.uint8, channel))


def pixels_to_image(pixels: np.ndarray, order: str) -> ImageValue:
    """Wrap an ``H×W×4`` uint8 frame in ``order`` as an RGBA ``ImageValue`` (no copy)."""
    if pixels.ndim != 3 or pixels.shape[2] != 4 or pixels.dtype != np.uint8:
        raise ValueError(f"expected an H×W×4 uint8 frame, got {pixels.dtype} {pixels.shape}")
    channel = ChannelOrder.BGR if order == "bgra" else ChannelOrder.RGB
    return ImageValue.from_array(pixels, order=channel)


def frame_to_image(frame: Frame, backend: type[Backend]) -> ImageValue:
    return pixels_to_image(frame.pixels, backend.channel_order)
