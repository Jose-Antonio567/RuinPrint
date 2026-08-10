"""Deterministic film and reproduction degradation, applied as the final stage."""

import cv2
import numpy as np
from PIL import Image

from effects.palette import get_palette, palette_luminance


def apply_degradation(
    image: Image.Image,
    palette_name: str,
    tones: int,
    *,
    film_grain: int = 0,
    dust: int = 0,
    scratches: int = 0,
    edge_decay: int = 0,
    exposure_drift: int = 0,
    vignette: int = 0,
    image_fade: int = 0,
) -> Image.Image:
    """Apply the ordered final degradation effects while preserving alpha exactly.

    Order: exposure drift, image fade, vignette, edge decay, film grain, dust,
    and scratches.
    """
    parameters = (film_grain, dust, scratches, edge_decay, exposure_drift, vignette, image_fade)
    if all(value <= 0 for value in parameters):
        return image.convert("RGBA").copy()

    rgba_image = image.convert("RGBA")
    source_pixels = np.asarray(rgba_image, dtype=np.uint8)
    rgb = source_pixels[..., :3].astype(np.float32) / 255.0
    active_pixels = source_pixels[..., 3] > 0
    ink_color, paper_color = _palette_extremes(palette_name, tones)

    if exposure_drift > 0:
        rgb = _apply_exposure_drift(rgb, ink_color, paper_color, exposure_drift, active_pixels)
    if image_fade > 0:
        rgb = _blend_toward(rgb, paper_color, active_pixels * _strength(image_fade) ** 1.25 * 0.88)
    if vignette > 0:
        rgb = _apply_vignette(rgb, ink_color, vignette, active_pixels)
    if edge_decay > 0:
        rgb = _apply_edge_decay(rgb, paper_color, edge_decay, active_pixels)
    if film_grain > 0:
        rgb = _apply_film_grain(rgb, film_grain, active_pixels)
    if dust > 0:
        rgb = _apply_dust(rgb, ink_color, paper_color, dust, active_pixels)
    if scratches > 0:
        rgb = _apply_scratches(rgb, ink_color, paper_color, scratches, active_pixels)

    output_pixels = source_pixels.copy()
    output_pixels[..., :3][active_pixels] = np.round(
        np.clip(rgb[active_pixels], 0.0, 1.0) * 255.0
    ).astype(np.uint8)
    return Image.fromarray(output_pixels, "RGBA")


def _palette_extremes(palette_name: str, tones: int) -> tuple[np.ndarray, np.ndarray]:
    colors = get_palette(palette_name, tones)
    color_array = np.asarray(colors, dtype=np.float32) / 255.0
    luminances = palette_luminance(colors)
    return color_array[np.argmin(luminances)], color_array[np.argmax(luminances)]


def _apply_exposure_drift(rgb: np.ndarray, ink: np.ndarray, paper: np.ndarray, value: int, active: np.ndarray) -> np.ndarray:
    field = _low_frequency_field(rgb.shape[:2], 7101)
    variation = (field - 0.5) * _strength(value) * 0.24
    rgb = _blend_toward(rgb, paper, np.clip(variation, 0.0, 1.0) * active)
    return _blend_toward(rgb, ink, np.clip(-variation, 0.0, 1.0) * active)


def _apply_vignette(rgb: np.ndarray, ink: np.ndarray, value: int, active: np.ndarray) -> np.ndarray:
    height, width = rgb.shape[:2]
    y, x = np.indices((height, width), dtype=np.float32)
    x = (x - (width - 1) / 2) / max(width / 2, 1)
    y = (y - (height - 1) / 2) / max(height / 2, 1)
    radial = np.sqrt(x * x + y * y)
    mask = np.clip((radial - 0.38) / 0.72, 0.0, 1.0) ** 1.5
    return _blend_toward(rgb, ink, mask * _strength(value) * 0.58 * active)


def _apply_edge_decay(rgb: np.ndarray, paper: np.ndarray, value: int, active: np.ndarray) -> np.ndarray:
    height, width = rgb.shape[:2]
    y, x = np.indices((height, width), dtype=np.float32)
    distance = np.minimum.reduce((x, y, width - 1 - x, height - 1 - y))
    normalized_distance = distance / max(min(width, height) * 0.20, 1.0)
    edge_mask = 1.0 - np.clip(normalized_distance, 0.0, 1.0)
    irregularity = 0.55 + _low_frequency_field((height, width), 7201) * 0.45
    return _blend_toward(rgb, paper, edge_mask * irregularity * _strength(value) * 0.64 * active)


def _apply_film_grain(rgb: np.ndarray, value: int, active: np.ndarray) -> np.ndarray:
    random_generator = np.random.default_rng(7301)
    fine = random_generator.normal(0.0, 1.0, rgb.shape[:2]).astype(np.float32)
    coarse = cv2.GaussianBlur(fine, (0, 0), 0.7)
    grain = fine * 0.72 + coarse * 0.28
    return rgb + grain[..., np.newaxis] * _strength(value) * 0.035 * active[..., np.newaxis]


def _apply_dust(rgb: np.ndarray, ink: np.ndarray, paper: np.ndarray, value: int, active: np.ndarray) -> np.ndarray:
    strength = _strength(value)
    light_mask, dark_mask = _particle_masks(rgb.shape[:2], 7401, strength, is_scratch=False)
    rgb = _blend_toward(rgb, paper, light_mask * strength * active)
    return _blend_toward(rgb, ink, dark_mask * strength * 0.45 * active)


def _apply_scratches(rgb: np.ndarray, ink: np.ndarray, paper: np.ndarray, value: int, active: np.ndarray) -> np.ndarray:
    strength = _strength(value)
    light_mask, dark_mask = _particle_masks(rgb.shape[:2], 7501, strength, is_scratch=True)
    rgb = _blend_toward(rgb, paper, light_mask * strength * 0.72 * active)
    return _blend_toward(rgb, ink, dark_mask * strength * 0.28 * active)


def _particle_masks(shape: tuple[int, int], seed: int, strength: float, *, is_scratch: bool) -> tuple[np.ndarray, np.ndarray]:
    height, width = shape
    random_generator = np.random.default_rng(seed)
    light_mask = np.zeros(shape, dtype=np.float32)
    dark_mask = np.zeros(shape, dtype=np.float32)
    count = int(2 + strength * (30 if is_scratch else min(380, max(24, height * width * 0.00035))))
    cluster_centers = random_generator.uniform(
        (0, 0), (max(width - 1, 1), max(height - 1, 1)), size=(4, 2)
    )

    for index in range(count):
        target = dark_mask if random_generator.random() < 0.16 else light_mask
        if not is_scratch and random_generator.random() < 0.48:
            center_x, center_y = cluster_centers[random_generator.integers(0, len(cluster_centers))]
            start_x = int(np.clip(random_generator.normal(center_x, max(width * 0.06, 1)), 0, width - 1))
            start_y = int(np.clip(random_generator.normal(center_y, max(height * 0.06, 1)), 0, height - 1))
        else:
            start_x, start_y = int(random_generator.integers(0, width)), int(random_generator.integers(0, height))
        intensity = float(random_generator.uniform(0.35, 1.0))
        if is_scratch:
            length = int(random_generator.integers(max(5, height // 14), max(8, height // 2)))
            angle = np.deg2rad(random_generator.normal(90.0, 15.0))
            end_x = int(np.clip(start_x + np.cos(angle) * length, 0, width - 1))
            end_y = int(np.clip(start_y + np.sin(angle) * length, 0, height - 1))
            cv2.line(target, (start_x, start_y), (end_x, end_y), intensity, int(random_generator.integers(1, 3)))
        else:
            radius = int(random_generator.choice((1, 1, 1, 2, 2, 3)))
            if random_generator.random() < 0.12:
                cv2.ellipse(target, (start_x, start_y), (radius * 2, radius), float(random_generator.uniform(0, 180)), 0, 360, intensity, -1)
            else:
                cv2.circle(target, (start_x, start_y), radius, intensity, -1)
    return np.clip(light_mask, 0.0, 1.0), np.clip(dark_mask, 0.0, 1.0)


def _low_frequency_field(shape: tuple[int, int], seed: int) -> np.ndarray:
    height, width = shape
    random_generator = np.random.default_rng(seed)
    grid = random_generator.random((max(2, height // 80), max(2, width // 80)), dtype=np.float32)
    field = cv2.resize(grid, (width, height), interpolation=cv2.INTER_CUBIC)
    field = cv2.GaussianBlur(field, (0, 0), max(2.0, min(width, height) / 40))
    return np.clip((field - field.min()) / max(float(field.max() - field.min()), 1e-6), 0.0, 1.0)


def _blend_toward(rgb: np.ndarray, color: np.ndarray, amount: np.ndarray) -> np.ndarray:
    blend = np.clip(amount, 0.0, 1.0)[..., np.newaxis]
    return rgb * (1.0 - blend) + color * blend


def _strength(value: int) -> float:
    return float(np.clip(value, 0, 100)) / 100.0
