"""Deterministic old-lens effects applied after Focus Map."""

import cv2
import numpy as np
from PIL import Image

from effects.focus import _compose_rgba
from effects.palette import get_palette, palette_luminance


def apply_uneven_focus(focus_mask: np.ndarray, amount: int) -> np.ndarray:
    """Modulate a focus mask with smooth, deterministic low-frequency variation."""
    strength = float(np.clip(amount, 0, 100)) / 100.0
    if strength == 0.0:
        return focus_mask

    height, width = focus_mask.shape
    random_generator = np.random.default_rng(6101)
    grid = random_generator.random(
        (max(2, int(np.ceil(height / 42))), max(2, int(np.ceil(width / 42)))),
        dtype=np.float32,
    )
    field = cv2.resize(grid, (width, height), interpolation=cv2.INTER_CUBIC)
    field = cv2.GaussianBlur(field, (0, 0), 2.5)
    field = (field - field.mean()) / max(float(field.std()), 1e-6)
    return np.clip(focus_mask + field * strength * 0.09, 0.0, 1.0).astype(np.float32)


def apply_lens(
    image: Image.Image,
    palette_name: str,
    tones: int,
    focus_mask: np.ndarray,
    *,
    lens_smear: int = 0,
    smear_angle: int = 0,
    soft_bleed: int = 0,
) -> Image.Image:
    """Apply directional smear and spatial highlight bleed without changing alpha."""
    if lens_smear <= 0 and soft_bleed <= 0:
        return image.convert("RGBA").copy()

    rgba_image = image.convert("RGBA")
    source_pixels = np.asarray(rgba_image, dtype=np.uint8)
    rgb = source_pixels[..., :3].astype(np.float32) / 255.0
    alpha = source_pixels[..., 3].astype(np.float32) / 255.0
    active_pixels = alpha > 0.0

    if lens_smear > 0:
        smeared_rgb = _alpha_safe_directional_blur(rgb, alpha, lens_smear, smear_angle)
        blend = np.clip(focus_mask, 0.0, 1.0) * (np.clip(lens_smear, 0, 100) / 100.0)
        rgb = rgb * (1.0 - blend[..., np.newaxis]) + smeared_rgb * blend[..., np.newaxis]

    if soft_bleed > 0:
        rgb = _apply_soft_bleed(
            rgb, alpha, palette_name, tones, soft_bleed, active_pixels
        )
    return _compose_rgba(rgb, source_pixels)


def _alpha_safe_directional_blur(
    rgb: np.ndarray, alpha: np.ndarray, strength: int, angle: int
) -> np.ndarray:
    kernel = _directional_kernel(strength, angle)
    premultiplied_rgb = rgb * alpha[..., np.newaxis]
    blurred_rgb = cv2.filter2D(premultiplied_rgb, -1, kernel, borderType=cv2.BORDER_REPLICATE)
    blurred_alpha = cv2.filter2D(alpha, -1, kernel, borderType=cv2.BORDER_REPLICATE)
    return blurred_rgb / np.maximum(blurred_alpha[..., np.newaxis], 1e-6)


def _directional_kernel(strength: int, angle: int) -> np.ndarray:
    size = max(3, int(round(3 + np.clip(strength, 0, 100) / 100.0 * 20)))
    if size % 2 == 0:
        size += 1
    kernel = np.zeros((size, size), dtype=np.float32)
    center = size // 2
    radians = np.deg2rad(np.clip(angle, -90, 90))
    offset_x = int(round(np.cos(radians) * center))
    offset_y = int(round(np.sin(radians) * center))
    cv2.line(kernel, (center - offset_x, center - offset_y), (center + offset_x, center + offset_y), 1.0, 1)
    return kernel / max(float(kernel.sum()), 1.0)


def _apply_soft_bleed(
    rgb: np.ndarray,
    alpha: np.ndarray,
    palette_name: str,
    tones: int,
    value: int,
    active_pixels: np.ndarray,
) -> np.ndarray:
    strength = float(np.clip(value, 0, 100)) / 100.0
    luminance = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    highlights = np.clip((luminance - 0.72) / 0.28, 0.0, 1.0) * alpha
    sigma = 0.5 + strength * 5.0
    blurred_highlights = cv2.GaussianBlur(highlights, (0, 0), sigma)
    paper_color = _paper_color(palette_name, tones)
    blend = np.clip(blurred_highlights * strength * 0.58, 0.0, 1.0) * active_pixels
    return rgb * (1.0 - blend[..., np.newaxis]) + paper_color * blend[..., np.newaxis]


def _paper_color(palette_name: str, tones: int) -> np.ndarray:
    colors = get_palette(palette_name, tones)
    color_array = np.asarray(colors, dtype=np.float32) / 255.0
    return color_array[np.argmax(palette_luminance(colors))]
