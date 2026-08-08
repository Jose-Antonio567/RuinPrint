"""Image loading and preview creation services."""

from pathlib import Path

from PIL import Image, ImageOps


MAX_PREVIEW_SIZE = 1200


def load_image(image_path: str | Path) -> Image.Image:
    """Load an image, correct its EXIF orientation, and preserve alpha in RGBA."""
    with Image.open(image_path) as source_image:
        corrected_image = ImageOps.exif_transpose(source_image)
        return corrected_image.convert("RGBA")


def create_preview(
    original_image: Image.Image, max_size: int = MAX_PREVIEW_SIZE
) -> Image.Image:
    """Create a non-destructive preview that fits within ``max_size`` pixels."""
    preview_image = original_image.copy()
    preview_image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    return preview_image
