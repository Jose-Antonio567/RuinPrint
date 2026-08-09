"""Deterministic print irregularities applied after palette mapping."""

import cv2
import numpy as np
from PIL import Image

from effects.palette import get_palette, palette_luminance


def apply_ink(
    image: Image.Image,
    palette_name: str,
    tones: int,
    *,
    ink_bleed: int = 0,
    ink_loss: int = 0,
    paper_grain: int = 0,
    speckles: int = 0,
    print_misalignment: int = 0,
) -> Image.Image:
    """Return a new RGBA image with deterministic print/ink imperfections."""
    parameters = (ink_bleed, ink_loss, paper_grain, speckles, print_misalignment)
    if all(value <= 0 for value in parameters):
        return image.convert("RGBA").copy()

    rgba_image = image.convert("RGBA")
    source_pixels = np.asarray(rgba_image, dtype=np.uint8)
    pixels = source_pixels.astype(np.float32) / 255.0
    rgb = pixels[..., :3].copy()
    alpha = pixels[..., 3]
    active_pixels = alpha > 0.0

    ink_color, paper_color = _ink_and_paper_colors(palette_name, tones)
    ink_amount = _ink_amount(rgb, ink_color, paper_color)

    if ink_bleed > 0:
        rgb = _apply_ink_bleed(rgb, ink_amount, ink_color, ink_bleed, active_pixels)
    if ink_loss > 0:
        rgb = _apply_ink_loss(rgb, ink_amount, paper_color, ink_loss, active_pixels)
    if paper_grain > 0:
        rgb = _apply_paper_grain(
            rgb, ink_amount, ink_color, paper_color, paper_grain, active_pixels
        )
    if speckles > 0:
        rgb = _apply_speckles(
            rgb, ink_amount, ink_color, paper_color, speckles, active_pixels
        )
    if print_misalignment > 0:
        rgb = _apply_misalignment(
            rgb, ink_amount, ink_color, print_misalignment, active_pixels
        )

    output_pixels = np.empty_like(source_pixels)
    output_pixels[..., :3] = np.round(np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8)
    output_pixels[..., 3] = source_pixels[..., 3]
    return Image.fromarray(output_pixels, "RGBA")


def _ink_and_paper_colors(
    palette_name: str, tones: int
) -> tuple[np.ndarray, np.ndarray]:
    colors = get_palette(palette_name, tones)
    color_array = np.asarray(colors, dtype=np.float32) / 255.0
    luminances = palette_luminance(colors)
    return color_array[np.argmin(luminances)], color_array[np.argmax(luminances)]


def _ink_amount(rgb: np.ndarray, ink_color: np.ndarray, paper_color: np.ndarray) -> np.ndarray:
    luminance = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    ink_luminance = float(0.2126 * ink_color[0] + 0.7152 * ink_color[1] + 0.0722 * ink_color[2])
    paper_luminance = float(
        0.2126 * paper_color[0] + 0.7152 * paper_color[1] + 0.0722 * paper_color[2]
    )
    return np.clip(
        (paper_luminance - luminance) / max(paper_luminance - ink_luminance, 0.001),
        0.0,
        1.0,
    )


def _apply_ink_bleed(
    rgb: np.ndarray,
    ink_amount: np.ndarray,
    ink_color: np.ndarray,
    value: int,
    active_pixels: np.ndarray,
) -> np.ndarray:
    strength = np.clip(value, 0, 100) / 100.0
    radius = max(1, int(round(1 + strength * 5)))
    kernel = np.ones((radius * 2 + 1, radius * 2 + 1), dtype=np.uint8)
    expanded_ink = cv2.dilate(ink_amount, kernel)
    blurred_ink = cv2.GaussianBlur(expanded_ink, (0, 0), max(0.4, radius * 0.45))
    bleed_mask = np.maximum(blurred_ink - ink_amount, 0.0) * strength * 0.65
    return _blend_toward(rgb, ink_color, bleed_mask * active_pixels)


def _apply_ink_loss(
    rgb: np.ndarray,
    ink_amount: np.ndarray,
    paper_color: np.ndarray,
    value: int,
    active_pixels: np.ndarray,
) -> np.ndarray:
    strength = np.clip(value, 0, 100) / 100.0
    field = _mixed_noise(ink_amount.shape, seed=1103)
    threshold = 0.86 - strength * 0.50
    loss_pattern = np.clip((field - threshold) / max(1.0 - threshold, 0.001), 0.0, 1.0)
    loss_mask = loss_pattern * ink_amount * strength * 0.85 * active_pixels
    return _blend_toward(rgb, paper_color, loss_mask)


def _apply_paper_grain(
    rgb: np.ndarray,
    ink_amount: np.ndarray,
    ink_color: np.ndarray,
    paper_color: np.ndarray,
    value: int,
    active_pixels: np.ndarray,
) -> np.ndarray:
    strength = np.clip(value, 0, 100) / 100.0
    field = _mixed_noise(ink_amount.shape, seed=2207) - 0.5
    variation = field * strength * 0.18 * (0.25 + 0.75 * ink_amount) * active_pixels
    darker_mask = np.clip(variation, 0.0, 1.0)
    lighter_mask = np.clip(-variation, 0.0, 1.0)
    rgb = _blend_toward(rgb, ink_color, darker_mask)
    return _blend_toward(rgb, paper_color, lighter_mask)


def _apply_speckles(
    rgb: np.ndarray,
    ink_amount: np.ndarray,
    ink_color: np.ndarray,
    paper_color: np.ndarray,
    value: int,
    active_pixels: np.ndarray,
) -> np.ndarray:
    strength = np.clip(value, 0, 100) / 100.0
    random_generator = np.random.default_rng(3301)
    density = 0.0002 + strength * 0.012
    random_values = random_generator.random(ink_amount.shape)
    loss_marks = (random_values < density) * ink_amount * strength * active_pixels
    ink_marks = (
        (random_values >= density) & (random_values < density * 1.20)
    ) * (1.0 - ink_amount) * strength * 0.45 * active_pixels
    rgb = _blend_toward(rgb, paper_color, loss_marks)
    return _blend_toward(rgb, ink_color, ink_marks)


def _apply_misalignment(
    rgb: np.ndarray,
    ink_amount: np.ndarray,
    ink_color: np.ndarray,
    value: int,
    active_pixels: np.ndarray,
) -> np.ndarray:
    strength = np.clip(value, 0, 100) / 100.0
    offset_x = int(round(strength * 6))
    offset_y = int(round(strength * 3))
    if offset_x == 0 and offset_y == 0:
        return rgb

    shifted_ink = _shift_without_wrap(ink_amount, offset_x, offset_y)
    second_print = shifted_ink * strength * 0.38 * active_pixels
    return _blend_toward(rgb, ink_color, second_print)


def _mixed_noise(shape: tuple[int, int], seed: int) -> np.ndarray:
    random_generator = np.random.default_rng(seed)
    fine_noise = random_generator.random(shape, dtype=np.float32)
    smooth_noise = cv2.GaussianBlur(fine_noise, (0, 0), 1.2)
    return fine_noise * 0.65 + smooth_noise * 0.35


def _blend_toward(rgb: np.ndarray, color: np.ndarray, amount: np.ndarray) -> np.ndarray:
    blend_amount = np.clip(amount, 0.0, 1.0)[..., np.newaxis]
    return rgb * (1.0 - blend_amount) + color * blend_amount


def _shift_without_wrap(source: np.ndarray, offset_x: int, offset_y: int) -> np.ndarray:
    shifted = np.zeros_like(source)
    height, width = source.shape
    source_x_start, source_x_end = max(0, -offset_x), min(width, width - offset_x)
    source_y_start, source_y_end = max(0, -offset_y), min(height, height - offset_y)
    target_x_start, target_x_end = max(0, offset_x), min(width, width + offset_x)
    target_y_start, target_y_end = max(0, offset_y), min(height, height + offset_y)
    shifted[target_y_start:target_y_end, target_x_start:target_x_end] = source[
        source_y_start:source_y_end, source_x_start:source_x_end
    ]
    return shifted
