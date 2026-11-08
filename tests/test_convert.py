"""ImageValue <-> packed-frame conversion."""

import numpy as np
import pytest
from haybale_image.value import ChannelOrder, ImageValue
from haybale_stream.backends.convert import image_to_pixels, pixels_to_image

pytestmark = [pytest.mark.unit]


def test_rgb_gets_opaque_alpha_and_backend_order():
    img = ImageValue.from_array(np.full((2, 3, 3), (10, 20, 30), np.uint8))
    rgba = image_to_pixels(img, "rgba")
    bgra = image_to_pixels(img, "bgra")
    assert rgba.shape == (2, 3, 4) and rgba.flags.c_contiguous
    assert tuple(rgba[0, 0]) == (10, 20, 30, 255)
    assert tuple(bgra[0, 0]) == (30, 20, 10, 255)


def test_gray_is_replicated():
    img = ImageValue.from_array(np.full((2, 2), 77, np.uint8))
    assert tuple(image_to_pixels(img, "rgba")[1, 1]) == (77, 77, 77, 255)


def test_float_image_scales_to_bytes():
    img = ImageValue.from_array(np.full((1, 1, 4), (1.0, 0.0, 0.5, 1.0), np.float32))
    assert tuple(image_to_pixels(img, "rgba")[0, 0])[:2] == (255, 0)


def test_roundtrip_through_bgra():
    src = np.random.default_rng(0).integers(0, 256, (4, 5, 4), dtype=np.uint8)
    back = pixels_to_image(image_to_pixels(pixels_to_image(src, "rgba"), "bgra"), "bgra")
    assert np.array_equal(back.array(np.uint8, ChannelOrder.RGB), src)


def test_pixels_to_image_rejects_wrong_shape():
    with pytest.raises(ValueError):
        pixels_to_image(np.zeros((2, 2, 3), np.uint8), "rgba")
