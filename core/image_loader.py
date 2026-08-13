"""Image loading and preview creation services."""

from pathlib import Path

import json

from PIL import Image, ImageOps

from core.processing_settings import METADATA_KEY, recoverable_settings


MAX_PREVIEW_SIZE = 1200
SUPPORTED_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})


def load_image(image_path: str | Path) -> Image.Image:
    """Load an image, correct its EXIF orientation, and preserve alpha in RGBA."""
    image, _ = load_image_with_metadata(image_path)
    return image


def load_image_with_metadata(image_path: str | Path) -> tuple[Image.Image, dict | None]:
    """Load an image and, for PNGs, return valid embedded RuinPrint settings."""
    with Image.open(image_path) as source_image:
        settings = _ruinprint_settings_from_png(source_image)
        corrected_image = ImageOps.exif_transpose(source_image)
        return corrected_image.convert("RGBA"), settings


def _ruinprint_settings_from_png(source_image: Image.Image) -> dict | None:
    if source_image.format != "PNG":
        return None
    raw_settings = source_image.info.get(METADATA_KEY)
    if not isinstance(raw_settings, str):
        return None
    try:
        return recoverable_settings(json.loads(raw_settings))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def create_preview(
    original_image: Image.Image, max_size: int = MAX_PREVIEW_SIZE
) -> Image.Image:
    """Create a non-destructive preview that fits within ``max_size`` pixels."""
    preview_image = original_image.copy()
    preview_image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    return preview_image
