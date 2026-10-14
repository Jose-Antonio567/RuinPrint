"""Dither algorithms that map continuous tone luminance to explicit palettes."""

import numpy as np
from PIL import Image

from effects.dither_modifiers import distorted_thresholds, modulate_luminance
from effects.palette import (
    apply_palette,
    get_palette,
    nearest_palette_indexes,
    palette_luminance,
)


_BAYER_4X4 = np.array(
    ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5)),
    dtype=np.float32,
)
_CLUSTERED_DOT_4X4 = np.array(
    ((12, 5, 6, 13), (4, 0, 1, 7), (11, 3, 2, 8), (15, 10, 9, 14)),
    dtype=np.float32,
)
_CROSS_DITHER_5X5 = np.array(
    ((21, 13, 9, 14, 22), (15, 5, 1, 6, 16), (10, 2, 0, 3, 11), (17, 7, 4, 8, 18), (23, 19, 12, 20, 24)),
    dtype=np.float32,
)


def apply_dither(
    image: Image.Image,
    palette_name: str,
    tones: int,
    algorithm: str = "Off",
    strength: int = 70,
    scale: int = 1,
    pattern_distortion: int = 0,
    aged_ivory_hue: int = 0,
    aged_ivory_influence: int = 0,
) -> Image.Image:
    """Return a newly dithered RGBA image with its original alpha channel intact."""
    if algorithm == "Off":
        return apply_palette(image, palette_name, tones, aged_ivory_hue, aged_ivory_influence)

    if algorithm not in {"Bayer", "Clustered Dot", "Cross Dither", "Broken Dither", "Floyd-Steinberg", "Atkinson", "Noise"}:
        raise ValueError("Algoritmo de dithering inválido.")

    normalized_strength = float(np.clip(strength, 0, 100)) / 100.0
    if normalized_strength == 0.0:
        return apply_palette(image, palette_name, tones, aged_ivory_hue, aged_ivory_influence)

    rgba_image = image.convert("RGBA")
    colors = get_palette(palette_name, tones, aged_ivory_hue, aged_ivory_influence)
    color_array = np.asarray(colors, dtype=np.uint8)
    color_luminances = palette_luminance(colors)
    luminance = _image_luminance(rgba_image)
    work_luminance = _scaled_luminance(luminance, scale)
    if algorithm == "Bayer":
        color_indexes = _ordered_dither(
            work_luminance, color_luminances, _BAYER_4X4, normalized_strength, pattern_distortion
        )
    elif algorithm == "Clustered Dot":
        color_indexes = _ordered_dither(
            work_luminance, color_luminances, _CLUSTERED_DOT_4X4, normalized_strength, pattern_distortion
        )
    elif algorithm == "Cross Dither":
        color_indexes = _ordered_dither(
            work_luminance, color_luminances, _CROSS_DITHER_5X5, normalized_strength, pattern_distortion
        )
    elif algorithm == "Broken Dither":
        color_indexes = _ordered_dither(
            work_luminance, color_luminances, _broken_pattern(work_luminance.shape), normalized_strength, pattern_distortion
        )
    elif algorithm == "Floyd-Steinberg":
        color_indexes = _floyd_steinberg(
            modulate_luminance(work_luminance, pattern_distortion), color_luminances, normalized_strength
        )
    elif algorithm == "Atkinson":
        color_indexes = _atkinson(
            modulate_luminance(work_luminance, pattern_distortion), color_luminances, normalized_strength
        )
    else:
        color_indexes = _noise_dither(
            modulate_luminance(work_luminance, pattern_distortion), color_luminances, normalized_strength
        )

    work_rgb = color_array[color_indexes]
    full_rgb = _expand_rgb(work_rgb, rgba_image.size)
    source_pixels = np.asarray(rgba_image, dtype=np.uint8)
    output_pixels = np.empty_like(source_pixels)
    output_pixels[..., :3] = full_rgb
    output_pixels[..., 3] = source_pixels[..., 3]
    return Image.fromarray(output_pixels, "RGBA")


def _image_luminance(image: Image.Image) -> np.ndarray:
    pixels = np.asarray(image, dtype=np.float32)
    return (
        0.2126 * pixels[..., 0] + 0.7152 * pixels[..., 1] + 0.0722 * pixels[..., 2]
    ) / 255.0


def _scaled_luminance(luminance: np.ndarray, scale: int) -> np.ndarray:
    safe_scale = int(np.clip(scale, 1, 32))
    if safe_scale == 1:
        return luminance.copy()

    height, width = luminance.shape
    work_size = ((width + safe_scale - 1) // safe_scale, (height + safe_scale - 1) // safe_scale)
    grayscale = Image.fromarray(np.round(luminance * 255.0).astype(np.uint8), "L")
    return np.asarray(grayscale.resize(work_size, Image.Resampling.BOX), dtype=np.float32) / 255.0


def _ordered_dither(
    luminance: np.ndarray,
    color_luminances: np.ndarray,
    threshold_matrix: np.ndarray,
    strength: float,
    pattern_distortion: int,
) -> np.ndarray:
    height, width = luminance.shape
    tiled_thresholds = distorted_thresholds(
        threshold_matrix, height, width, pattern_distortion
    )
    centered_thresholds = (tiled_thresholds + 0.5) / threshold_matrix.size - 0.5
    amplitude = strength / len(color_luminances)
    adjusted_luminance = np.clip(luminance + centered_thresholds * amplitude, 0.0, 1.0)
    return nearest_palette_indexes(adjusted_luminance, color_luminances)


def _broken_pattern(shape: tuple[int, int]) -> np.ndarray:
    """Build a Bayer-derived pattern with stable local phase and threshold defects."""
    height, width = shape
    random_generator = np.random.default_rng(4703)
    block_size = 8
    block_rows = int(np.ceil(height / block_size))
    block_columns = int(np.ceil(width / block_size))
    phase_x = random_generator.integers(0, 4, (block_rows, block_columns))
    phase_y = random_generator.integers(0, 4, (block_rows, block_columns))
    threshold_shift = random_generator.integers(-2, 3, (block_rows, block_columns))

    y_coordinates, x_coordinates = np.indices(shape)
    blocks_y, blocks_x = y_coordinates // block_size, x_coordinates // block_size
    pattern = _BAYER_4X4[
        (y_coordinates + phase_y[blocks_y, blocks_x]) % 4,
        (x_coordinates + phase_x[blocks_y, blocks_x]) % 4,
    ]
    return np.mod(pattern + threshold_shift[blocks_y, blocks_x], 16).astype(np.float32)


def _floyd_steinberg(
    luminance: np.ndarray, color_luminances: np.ndarray, strength: float
) -> np.ndarray:
    work = luminance.copy()
    height, width = work.shape
    indexes = np.empty((height, width), dtype=np.intp)
    neighbors = ((1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16))

    for y in range(height):
        for x in range(width):
            index = int(np.argmin(np.abs(color_luminances - work[y, x])))
            indexes[y, x] = index
            error = (work[y, x] - color_luminances[index]) * strength
            for offset_x, offset_y, weight in neighbors:
                neighbor_x, neighbor_y = x + offset_x, y + offset_y
                if 0 <= neighbor_x < width and 0 <= neighbor_y < height:
                    work[neighbor_y, neighbor_x] = np.clip(
                        work[neighbor_y, neighbor_x] + error * weight, 0.0, 1.0
                    )
    return indexes


def _atkinson(
    luminance: np.ndarray, color_luminances: np.ndarray, strength: float
) -> np.ndarray:
    work = luminance.copy()
    height, width = work.shape
    indexes = np.empty((height, width), dtype=np.intp)
    neighbors = ((1, 0), (2, 0), (-1, 1), (0, 1), (1, 1), (0, 2))

    for y in range(height):
        for x in range(width):
            index = int(np.argmin(np.abs(color_luminances - work[y, x])))
            indexes[y, x] = index
            error_share = (work[y, x] - color_luminances[index]) * strength / 8.0
            for offset_x, offset_y in neighbors:
                neighbor_x, neighbor_y = x + offset_x, y + offset_y
                if 0 <= neighbor_x < width and 0 <= neighbor_y < height:
                    work[neighbor_y, neighbor_x] = np.clip(
                        work[neighbor_y, neighbor_x] + error_share, 0.0, 1.0
                    )
    return indexes


def _noise_dither(
    luminance: np.ndarray, color_luminances: np.ndarray, strength: float
) -> np.ndarray:
    random_generator = np.random.default_rng(24601)
    amplitude = strength / len(color_luminances)
    noise = random_generator.uniform(-0.5, 0.5, luminance.shape).astype(np.float32)
    adjusted_luminance = np.clip(luminance + noise * amplitude, 0.0, 1.0)
    return nearest_palette_indexes(adjusted_luminance, color_luminances)


def _expand_rgb(work_rgb: np.ndarray, original_size: tuple[int, int]) -> np.ndarray:
    width, height = original_size
    if work_rgb.shape[:2] == (height, width):
        return work_rgb

    work_image = Image.fromarray(work_rgb, "RGB")
    return np.asarray(
        work_image.resize((width, height), Image.Resampling.NEAREST), dtype=np.uint8
    )
