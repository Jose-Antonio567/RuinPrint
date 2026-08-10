"""Preview-processing pipeline orchestration."""

from dataclasses import dataclass

from PIL import Image

from effects.dither import apply_dither
from effects.dither_modifiers import apply_dither_destruction
from effects.ink import apply_ink
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


@dataclass(frozen=True)
class DitherDestructionParameters:
    """Structural modifiers that alter the dither pattern before Print/Ink."""

    pattern_distortion: int = 0
    dither_loss: int = 0
    dither_spread: int = 0


@dataclass(frozen=True)
class InkParameters:
    """Parameters for the Print/Ink stage of the image pipeline."""

    ink_bleed: int = 0
    ink_loss: int = 0
    paper_grain: int = 0
    speckles: int = 0
    print_misalignment: int = 0


class ImagePipeline:
    """Apply the enabled processing stages to an original preview image."""

    def process_preview(
        self,
        original_preview: Image.Image,
        tone: ToneParameters,
        palette: PaletteParameters,
        dither: DitherParameters,
        dither_destruction: DitherDestructionParameters,
        ink: InkParameters,
    ) -> Image.Image:
        """Process a preview through Tone, Dither, Destruction, then Print/Ink."""
        tone_result = apply_tone(
            original_preview,
            contrast=tone.contrast,
            black_crush=tone.black_crush,
            highlight_burn=tone.highlight_burn,
            gamma=tone.gamma,
        )
        dither_result = apply_dither(
            tone_result,
            palette.name,
            palette.tones,
            dither.mode,
            dither.strength,
            dither.scale,
            dither_destruction.pattern_distortion,
        )
        destruction_result = apply_dither_destruction(
            dither_result,
            palette.name,
            palette.tones,
            dither_loss=dither_destruction.dither_loss,
            dither_spread=dither_destruction.dither_spread,
            scale=dither.scale,
        )
        return apply_ink(
            destruction_result,
            palette.name,
            palette.tones,
            ink_bleed=ink.ink_bleed,
            ink_loss=ink.ink_loss,
            paper_grain=ink.paper_grain,
            speckles=ink.speckles,
            print_misalignment=ink.print_misalignment,
        )
