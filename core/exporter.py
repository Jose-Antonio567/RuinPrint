"""PNG export helpers for RuinPrint output files."""

import json
from pathlib import Path

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from core.pipeline import PipelineSettings
from core.processing_settings import METADATA_KEY, metadata_payload


def save_png_with_metadata(
    image: Image.Image, output_path: str | Path, settings: PipelineSettings
) -> None:
    """Save an RGBA PNG with the exact processing snapshot embedded as iTXt."""
    png_info = PngInfo()
    png_info.add_itxt(
        METADATA_KEY,
        json.dumps(metadata_payload(settings), ensure_ascii=False, separators=(",", ":")),
    )
    image.save(output_path, "PNG", pnginfo=png_info)
