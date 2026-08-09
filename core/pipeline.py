"""Preview-processing pipeline orchestration."""

from dataclasses import dataclass

from PIL import Image

from effects.dither import apply_dither
from effects.tone import apply_tone


@dataclass(frozen=True)
class ToneParameters:
    """Parameters for the tone stage of the image pipeline."""

    contrast: int = 0
    black_crush: int = 0
    highlight_burn: int = 0
    gamma: float = 1.0


@dataclass(frozen=True)
class PaletteParameters:
    """Parameters for the palette stage of the image pipeline."""

    name: str = "Aged Ivory"
    tones: int = 4


@dataclass(frozen=True)
class DitherParameters:
    """Parameters for the Dither/Palette stage of the image pipeline."""

    mode: str = "Bayer"
    strength: int = 70
    scale: int = 1


class ImagePipeline:
    """Apply the enabled processing stages to an original preview image."""

    def process_preview(
        self,
        original_preview: Image.Image,
        tone: ToneParameters,
        palette: PaletteParameters,
        dither: DitherParameters,
    ) -> Image.Image:
        """Process a preserved preview through Tone then Dither/Palette once."""
        tone_result = apply_tone(
            original_preview,
            contrast=tone.contrast,
            black_crush=tone.black_crush,
            highlight_burn=tone.highlight_burn,
            gamma=tone.gamma,
        )
        return apply_dither(
            tone_result,
            palette.name,
            palette.tones,
            dither.mode,
            dither.strength,
            dither.scale,
        )
