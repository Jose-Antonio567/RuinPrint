"""Spatial growth of dark palette masses before Print/Ink simulation."""

import cv2
import numpy as np
from PIL import Image

from effects.palette import get_palette, palette_luminance


def apply_black_consumption(
    image: Image.Image,
    palette_name: str,
    tones: int,
    *,
    amount: int = 0,
    reach: int = 2,
    detail_swallow: int = 0,
    dither_scale: int = 1,
) -> Image.Image:
    """Expand localized ink masses and fill only small light interruptions."""
    if amount <= 0 and detail_swallow <= 0:
        return image.convert("RGBA").copy()

    rgba_image = image.convert("RGBA")
    source_pixels = np.asarray(rgba_image, dtype=np.uint8)
    active_pixels = source_pixels[..., 3] > 0
    rgb = source_pixels[..., :3].astype(np.float32) / 255.0
    ink_color, ink_amount = _palette_ink_amount(rgb, palette_name, tones)

    if amount > 0:
        rgb = _consume_dark_masses(rgb, ink_amount, ink_color, amount, reach, dither_scale, active_pixels)
    if detail_swallow > 0:
        rgb = _swallow_light_details(
            rgb, ink_amount, ink_color, detail_swallow, dither_scale, active_pixels
        )

    output_pixels = source_pixels.copy()
    output_pixels[..., :3] = np.round(np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8)
    return Image.fromarray(output_pixels, "RGBA")


def _palette_ink_amount(
    rgb: np.ndarray, palette_name: str, tones: int
) -> tuple[np.ndarray, np.ndarray]:
    colors = get_palette(palette_name, tones)
    color_array = np.asarray(colors, dtype=np.float32) / 255.0
    luminances = palette_luminance(colors)
    ink_color = color_array[np.argmin(luminances)]
    paper_luminance = float(np.max(luminances))
    ink_luminance = float(np.min(luminances))
    image_luminance = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    ink_amount = np.clip(
        (paper_luminance - image_luminance) / max(paper_luminance - ink_luminance, 0.001),
        0.0,
        1.0,
    )
    return ink_color, ink_amount.astype(np.float32)


def _consume_dark_masses(
    rgb: np.ndarray,
    ink_amount: np.ndarray,
    ink_color: np.ndarray,
    amount: int,
    reach: int,
    dither_scale: int,
    active_pixels: np.ndarray,
) -> np.ndarray:
    strength = float(np.clip(amount, 0, 100)) / 100.0
    safe_reach = int(np.clip(reach, 1, 8))
    safe_scale = int(np.clip(dither_scale, 1, 8))
    radius = max(1, min(5, int(round(safe_reach * (0.45 + strength * 0.55) / np.sqrt(safe_scale)))))
    kernel = np.ones((radius * 2 + 1, radius * 2 + 1), dtype=np.uint8)
    expanded_ink = cv2.dilate(ink_amount * active_pixels, kernel)
    growth = np.maximum(expanded_ink - ink_amount, 0.0) * strength * 0.78 * active_pixels
    return _blend_toward(rgb, ink_color, growth)


def _swallow_light_details(
    rgb: np.ndarray,
    ink_amount: np.ndarray,
    ink_color: np.ndarray,
    detail_swallow: int,
    dither_scale: int,
    active_pixels: np.ndarray,
) -> np.ndarray:
    strength = float(np.clip(detail_swallow, 0, 100)) / 100.0
    safe_scale = int(np.clip(dither_scale, 1, 8))
    radius = max(1, min(3, int(round((1.0 + strength * 2.5) / np.sqrt(safe_scale)))))
    kernel = np.ones((radius * 2 + 1, radius * 2 + 1), dtype=np.uint8)
    dark_regions = ((ink_amount > 0.58) & active_pixels).astype(np.uint8)
    closed_regions = cv2.morphologyEx(dark_regions, cv2.MORPH_CLOSE, kernel).astype(bool)
    swallowed = closed_regions & ~dark_regions & active_pixels
    return _blend_toward(rgb, ink_color, swallowed.astype(np.float32) * strength * 0.72)


def _blend_toward(rgb: np.ndarray, color: np.ndarray, amount: np.ndarray) -> np.ndarray:
    blend = np.clip(amount, 0.0, 1.0)[..., np.newaxis]
    return rgb * (1.0 - blend) + color * blend
