"""Non-destructive tonal reconstruction for RGBA Pillow images."""

import numpy as np
from PIL import Image


def apply_tone(
    image: Image.Image,
    *,
    contrast: int = 0,
    black_crush: int = 0,
    highlight_burn: int = 0,
    gamma: float = 1.0,
) -> Image.Image:
    """Return a grayscale RGBA image with the requested tonal adjustments.

    The input image is never modified and its alpha channel is copied unchanged.
    """
    rgba_image = image.convert("RGBA")
    pixels = np.asarray(rgba_image, dtype=np.float32) / 255.0

    red, green, blue = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue

    safe_gamma = max(float(gamma), 0.001)
    luminance = np.power(np.clip(luminance, 0.0, 1.0), 1.0 / safe_gamma)

    contrast_value = float(np.clip(contrast, -100, 100)) / 100.0
    luminance = (luminance - 0.5) * (1.0 + contrast_value) + 0.5

    black_point = float(np.clip(black_crush, 0, 100)) / 100.0 * 0.30
    white_point = 1.0 - float(np.clip(highlight_burn, 0, 100)) / 100.0 * 0.30
    white_point = max(white_point, black_point + 0.001)
    luminance = (luminance - black_point) / (white_point - black_point)
    luminance = np.clip(luminance, 0.0, 1.0)

    output_pixels = np.empty_like(pixels)
    output_pixels[..., :3] = luminance[..., np.newaxis]
    output_pixels[..., 3] = pixels[..., 3]
    return Image.fromarray((output_pixels * 255.0).round().astype(np.uint8), "RGBA")
