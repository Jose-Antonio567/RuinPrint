"""In-memory source image managed by the current editor session."""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class ImageDocument:
    path: str
    original_full: Image.Image
    preview_original: Image.Image
    ruinprint_settings: dict | None = None

    @property
    def display_name(self) -> str:
        return Path(self.path).name
