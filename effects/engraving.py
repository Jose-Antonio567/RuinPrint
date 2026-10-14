"""Structural edge engraving for palette-mapped images."""

import cv2
import numpy as np
from PIL import Image

from effects.palette import get_palette, palette_luminance


def apply_engraving(
    image: Image.Image,
    palette_name: str,
    tones: int,
    *,
    strength: int = 0,
    detail: int = 35,
    thickness: int = 1,
    direction: str = "Natural",
    aged_ivory_hue: int = 0,
    aged_ivory_influence: int = 0,
) -> Image.Image:
    """Reinforce selected structural edges toward the active palette ink color."""
    if strength <= 0:
        return image.convert("RGBA").copy()

    rgba_image = image.convert("RGBA")
    source_pixels = np.asarray(rgba_image, dtype=np.uint8)
    active_pixels = source_pixels[..., 3] > 0
    rgb = source_pixels[..., :3].astype(np.float32) / 255.0
    luminance = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]

    edge_mask = _edge_mask(luminance, active_pixels, detail, thickness, direction)
    ink_color = _ink_color(palette_name, tones, aged_ivory_hue, aged_ivory_influence)
    blend = (edge_mask * (np.clip(strength, 0, 100) / 100.0))[..., np.newaxis]
    output_rgb = rgb * (1.0 - blend) + ink_color * blend

    output_pixels = source_pixels.copy()
    output_pixels[..., :3] = np.round(np.clip(output_rgb, 0.0, 1.0) * 255.0).astype(np.uint8)
    return Image.fromarray(output_pixels, "RGBA")


def _edge_mask(
    luminance: np.ndarray,
    active_pixels: np.ndarray,
    detail: int,
    thickness: int,
    direction: str,
) -> np.ndarray:
    detail_strength = float(np.clip(detail, 0, 100)) / 100.0
    sigma = 3.4 - detail_strength * 2.9
    smoothed = cv2.GaussianBlur(luminance, (0, 0), max(sigma, 0.35))
    gradient_x = cv2.Sobel(smoothed, cv2.CV_32F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(smoothed, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(gradient_x, gradient_y)

    active_magnitude = magnitude[active_pixels]
    if active_magnitude.size == 0 or float(active_magnitude.max()) == 0.0:
        return np.zeros_like(luminance)

    threshold = np.percentile(active_magnitude, 78.0 - detail_strength * 14.0)
    upper_bound = max(float(np.percentile(active_magnitude, 96.0)), threshold + 0.0001)
    mask = np.clip((magnitude - threshold) / (upper_bound - threshold), 0.0, 1.0)
    mask *= _direction_weight(gradient_x, gradient_y, direction)
    mask *= active_pixels

    safe_thickness = int(np.clip(thickness, 1, 6))
    if safe_thickness > 1:
        kernel_size = safe_thickness * 2 - 1
        mask = cv2.dilate(mask, np.ones((kernel_size, kernel_size), dtype=np.uint8))
        mask *= active_pixels
    return np.clip(mask, 0.0, 1.0)


def _direction_weight(
    gradient_x: np.ndarray, gradient_y: np.ndarray, direction: str
) -> np.ndarray:
    targets = {
        "Horizontal": 0.0,
        "Vertical": 90.0,
        "Diagonal /": 135.0,
        "Diagonal \\": 45.0,
    }
    if direction == "Natural":
        return np.ones_like(gradient_x)
    if direction not in targets:
        raise ValueError("Direção de engraving inválida.")

    gradient_angle = np.degrees(np.arctan2(gradient_y, gradient_x))
    edge_angle = (gradient_angle + 90.0) % 180.0
    difference = np.deg2rad(edge_angle - targets[direction])
    return np.abs(np.cos(difference)) ** 4


def _ink_color(palette_name: str, tones: int, hue: int = 0, influence: int = 0) -> np.ndarray:
    colors = get_palette(palette_name, tones, hue, influence)
    color_array = np.asarray(colors, dtype=np.float32) / 255.0
    return color_array[np.argmin(palette_luminance(colors))]
