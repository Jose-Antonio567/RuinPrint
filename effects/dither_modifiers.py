"""Deterministic structural modifiers for palette-mapped dithering."""

import cv2
import numpy as np
from PIL import Image

from effects.palette import get_palette, nearest_palette_indexes, palette_luminance


def distorted_thresholds(
    threshold_matrix: np.ndarray, height: int, width: int, amount: int
) -> np.ndarray:
    """Tile an ordered pattern with deterministic local phase offsets."""
    matrix_height, matrix_width = threshold_matrix.shape
    base_pattern = np.tile(
        threshold_matrix,
        (int(np.ceil(height / matrix_height)), int(np.ceil(width / matrix_width))),
    )[:height, :width]
    strength = float(np.clip(amount, 0, 100)) / 100.0
    if strength == 0.0:
        return base_pattern

    offset_limit = max(1, int(round(strength * 3)))
    field_height = max(1, int(np.ceil(height / 24)))
    field_width = max(1, int(np.ceil(width / 24)))
    random_generator = np.random.default_rng(4417)
    active_blocks = random_generator.random((field_height, field_width)) < strength
    offset_x = random_generator.integers(-offset_limit, offset_limit + 1, (field_height, field_width))
    offset_y = random_generator.integers(-offset_limit, offset_limit + 1, (field_height, field_width))
    offset_x *= active_blocks
    offset_y *= active_blocks
    offset_x = cv2.resize(offset_x.astype(np.float32), (width, height), interpolation=cv2.INTER_NEAREST).astype(np.intp)
    offset_y = cv2.resize(offset_y.astype(np.float32), (width, height), interpolation=cv2.INTER_NEAREST).astype(np.intp)

    y_coordinates, x_coordinates = np.indices((height, width))
    return threshold_matrix[
        (y_coordinates + offset_y) % matrix_height,
        (x_coordinates + offset_x) % matrix_width,
    ]


def modulate_luminance(luminance: np.ndarray, amount: int) -> np.ndarray:
    """Apply a subtle deterministic modulation for non-ordered dither modes."""
    strength = float(np.clip(amount, 0, 100)) / 100.0
    if strength == 0.0:
        return luminance

    height, width = luminance.shape
    random_generator = np.random.default_rng(4519)
    field_size = (max(1, int(np.ceil(width / 28))), max(1, int(np.ceil(height / 28))))
    field = random_generator.random(field_size, dtype=np.float32)
    field = cv2.resize(field, (width, height), interpolation=cv2.INTER_CUBIC) - 0.5
    return np.clip(luminance + field * strength * 0.05, 0.0, 1.0)


def apply_dither_destruction(
    image: Image.Image,
    palette_name: str,
    tones: int,
    *,
    dither_loss: int = 0,
    dither_spread: int = 0,
    scale: int = 1,
    aged_ivory_hue: int = 0,
    aged_ivory_influence: int = 0,
) -> Image.Image:
    """Apply Dither Loss then Dither Spread without changing alpha or geometry."""
    if dither_loss <= 0 and dither_spread <= 0:
        return image.convert("RGBA").copy()

    rgba_image = image.convert("RGBA")
    source_pixels = np.asarray(rgba_image, dtype=np.uint8)
    rgb = source_pixels[..., :3].copy()
    active_pixels = source_pixels[..., 3] > 0
    colors = get_palette(palette_name, tones, aged_ivory_hue, aged_ivory_influence)
    color_array = np.asarray(colors, dtype=np.uint8)
    color_luminances = palette_luminance(colors)

    if dither_loss > 0:
        rgb = _apply_dither_loss(rgb, active_pixels, color_array, color_luminances, dither_loss)
    if dither_spread > 0:
        rgb = _apply_dither_spread(
            rgb, active_pixels, color_array, color_luminances, dither_spread, scale
        )

    output_pixels = source_pixels.copy()
    output_pixels[..., :3] = rgb
    return Image.fromarray(output_pixels, "RGBA")


def _apply_dither_loss(
    rgb: np.ndarray,
    active_pixels: np.ndarray,
    color_array: np.ndarray,
    color_luminances: np.ndarray,
    value: int,
) -> np.ndarray:
    current_indexes = _closest_color_indexes(rgb, color_array)
    local_level = cv2.medianBlur(current_indexes.astype(np.uint8), 3)
    dither_elements = (current_indexes != local_level) & active_pixels
    if not np.any(dither_elements):
        return rgb

    strength = float(np.clip(value, 0, 100)) / 100.0
    random_generator = np.random.default_rng(5201)
    selection = random_generator.random(dither_elements.shape) < (0.03 + 0.35 * strength)
    loss_mask = dither_elements & selection
    lighter_indexes = _next_lighter_indexes(current_indexes, color_luminances)
    output = rgb.copy()
    output[loss_mask] = color_array[lighter_indexes[loss_mask]]
    return output


def _apply_dither_spread(
    rgb: np.ndarray,
    active_pixels: np.ndarray,
    color_array: np.ndarray,
    color_luminances: np.ndarray,
    value: int,
    scale: int,
) -> np.ndarray:
    strength = float(np.clip(value, 0, 100)) / 100.0
    safe_scale = int(np.clip(scale, 1, 32))
    radius = max(1, int(round(1 + strength * 2 / safe_scale)))
    ink_amount = _ink_amount_from_rgb(rgb, color_luminances)
    expanded_ink = cv2.dilate(ink_amount, np.ones((radius * 2 + 1, radius * 2 + 1), np.uint8))
    spread_amount = np.maximum(expanded_ink - ink_amount, 0.0) * strength * 0.7
    if not np.any(spread_amount):
        return rgb

    paper_luminance = float(np.max(color_luminances))
    ink_luminance = float(np.min(color_luminances))
    target_luminance = paper_luminance - expanded_ink * (paper_luminance - ink_luminance)
    target_indexes = nearest_palette_indexes(target_luminance, color_luminances)
    target_rgb = color_array[target_indexes].astype(np.float32)
    blend = np.clip(spread_amount * active_pixels, 0.0, 1.0)[..., np.newaxis]
    return np.round(rgb * (1.0 - blend) + target_rgb * blend).astype(np.uint8)


def _closest_color_indexes(rgb: np.ndarray, color_array: np.ndarray) -> np.ndarray:
    distances = np.sum(
        (rgb.astype(np.int32)[..., np.newaxis, :] - color_array.astype(np.int32)) ** 2,
        axis=-1,
    )
    return np.argmin(distances, axis=-1)


def _next_lighter_indexes(indexes: np.ndarray, color_luminances: np.ndarray) -> np.ndarray:
    ordered_indexes = np.argsort(color_luminances)
    positions = np.empty_like(ordered_indexes)
    positions[ordered_indexes] = np.arange(len(ordered_indexes))
    return ordered_indexes[np.minimum(positions[indexes] + 1, len(ordered_indexes) - 1)]


def _ink_amount_from_rgb(rgb: np.ndarray, color_luminances: np.ndarray) -> np.ndarray:
    rgb_float = rgb.astype(np.float32)
    luminance = (
        0.2126 * rgb_float[..., 0] + 0.7152 * rgb_float[..., 1] + 0.0722 * rgb_float[..., 2]
    ) / 255.0
    paper_luminance = float(np.max(color_luminances))
    ink_luminance = float(np.min(color_luminances))
    return np.clip(
        (paper_luminance - luminance) / max(paper_luminance - ink_luminance, 0.001),
        0.0,
        1.0,
    ).astype(np.float32)
