"""Focus-mask generation and alpha-safe out-of-focus blur."""

import cv2
import numpy as np
from PIL import Image


def create_focus_mask(
    image_size: tuple[int, int],
    *,
    shape: str = "Horizontal",
    position_x: int = 50,
    position_y: int = 50,
    width: int = 40,
    softness: int = 40,
    angle: int = 0,
) -> np.ndarray:
    """Return float32 mask where 0 is sharp and 1 is out of focus."""
    image_width, image_height = image_size
    shortest_side = max(1, min(image_width, image_height))
    center_x = np.clip(position_x, 0, 100) / 100.0 * (image_width - 1)
    center_y = np.clip(position_y, 0, 100) / 100.0 * (image_height - 1)
    y_coordinates, x_coordinates = np.indices((image_height, image_width), dtype=np.float32)
    x = (x_coordinates - center_x) / shortest_side
    y = (y_coordinates - center_y) / shortest_side

    radians = np.deg2rad(np.clip(angle, -90, 90))
    rotated_x = x * np.cos(radians) + y * np.sin(radians)
    rotated_y = -x * np.sin(radians) + y * np.cos(radians)
    focus_width = 0.025 + np.clip(width, 5, 100) / 100.0 * 0.50

    if shape == "Horizontal":
        distance = np.abs(rotated_y)
    elif shape == "Vertical":
        distance = np.abs(rotated_x)
    elif shape == "Radial":
        distance = np.sqrt(x * x + y * y)
    elif shape == "Elliptical":
        distance = np.sqrt((rotated_x / 1.35) ** 2 + (rotated_y / 0.85) ** 2)
    else:
        raise ValueError("Forma de foco inválida.")

    transition = 0.001 + np.clip(softness, 0, 100) / 100.0 * 0.45
    return np.clip((distance - focus_width) / transition, 0.0, 1.0).astype(np.float32)


def apply_focus_blur(image: Image.Image, focus_mask: np.ndarray, blur: int) -> Image.Image:
    """Blend an alpha-safe Gaussian blur only where the focus mask is out of focus."""
    if blur <= 0:
        return image.convert("RGBA").copy()

    rgba_image = image.convert("RGBA")
    source_pixels = np.asarray(rgba_image, dtype=np.uint8)
    rgb = source_pixels[..., :3].astype(np.float32) / 255.0
    alpha = source_pixels[..., 3].astype(np.float32) / 255.0
    sigma = 0.4 + np.clip(blur, 0, 100) / 100.0 * 12.0
    blurred_rgb = alpha_safe_gaussian_blur(rgb, alpha, sigma)
    blend = np.clip(focus_mask, 0.0, 1.0) * (alpha > 0.0)
    output_rgb = rgb * (1.0 - blend[..., np.newaxis]) + blurred_rgb * blend[..., np.newaxis]
    return _compose_rgba(output_rgb, source_pixels)


def alpha_safe_gaussian_blur(rgb: np.ndarray, alpha: np.ndarray, sigma: float) -> np.ndarray:
    """Blur RGB in premultiplied-alpha space to avoid transparent-edge halos."""
    premultiplied_rgb = rgb * alpha[..., np.newaxis]
    blurred_rgb = cv2.GaussianBlur(premultiplied_rgb, (0, 0), sigma)
    blurred_alpha = cv2.GaussianBlur(alpha, (0, 0), sigma)
    return blurred_rgb / np.maximum(blurred_alpha[..., np.newaxis], 1e-6)


def _compose_rgba(rgb: np.ndarray, source_pixels: np.ndarray) -> Image.Image:
    output_pixels = source_pixels.copy()
    active_pixels = source_pixels[..., 3] > 0
    output_pixels[..., :3][active_pixels] = np.round(
        np.clip(rgb[active_pixels], 0.0, 1.0) * 255.0
    ).astype(np.uint8)
    return Image.fromarray(output_pixels, "RGBA")
