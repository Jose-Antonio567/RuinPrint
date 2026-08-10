"""Preview-processing pipeline orchestration."""

from dataclasses import dataclass

from PIL import Image

from effects.dither import apply_dither
from effects.dither_modifiers import apply_dither_destruction
from effects.degradation import apply_degradation
from effects.black_consumption import apply_black_consumption
from effects.engraving import apply_engraving
from effects.focus import apply_focus_blur, create_focus_mask
from effects.ink import apply_ink
from effects.lens import apply_lens, apply_uneven_focus
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
class EngravingParameters:
    """Parameters for the structural edge engraving stage."""

    strength: int = 0
    detail: int = 35
    thickness: int = 1
    direction: str = "Natural"


@dataclass(frozen=True)
class BlackConsumptionParameters:
    """Parameters for spatial growth of dark masses."""

    amount: int = 0
    reach: int = 2
    detail_swallow: int = 0


@dataclass(frozen=True)
class FocusParameters:
    """Parameters that define an image-space focus mask."""

    shape: str = "Horizontal"
    position_x: int = 50
    position_y: int = 50
    width: int = 40
    softness: int = 40
    angle: int = 0
    blur: int = 0


@dataclass(frozen=True)
class LensParameters:
    """Parameters for old-lens imperfections after Focus Map."""

    uneven_focus: int = 0
    lens_smear: int = 0
    smear_angle: int = 0
    soft_bleed: int = 0


@dataclass(frozen=True)
class DegradationParameters:
    """Parameters for final film/reproduction degradation."""

    film_grain: int = 0
    dust: int = 0
    scratches: int = 0
    edge_decay: int = 0
    exposure_drift: int = 0
    vignette: int = 0
    image_fade: int = 0


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
        engraving: EngravingParameters,
        black_consumption: BlackConsumptionParameters,
        ink: InkParameters,
        focus: FocusParameters,
        lens: LensParameters,
        degradation: DegradationParameters,
    ) -> Image.Image:
        """Process a preview through all stages in their intentional visual order."""
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
        engraving_result = apply_engraving(
            destruction_result,
            palette.name,
            palette.tones,
            strength=engraving.strength,
            detail=engraving.detail,
            thickness=engraving.thickness,
            direction=engraving.direction,
        )
        consumption_result = apply_black_consumption(
            engraving_result,
            palette.name,
            palette.tones,
            amount=black_consumption.amount,
            reach=black_consumption.reach,
            detail_swallow=black_consumption.detail_swallow,
            dither_scale=dither.scale,
        )
        ink_result = apply_ink(
            consumption_result,
            palette.name,
            palette.tones,
            ink_bleed=ink.ink_bleed,
            ink_loss=ink.ink_loss,
            paper_grain=ink.paper_grain,
            speckles=ink.speckles,
            print_misalignment=ink.print_misalignment,
        )
        focus_mask = create_focus_mask(
            ink_result.size,
            shape=focus.shape,
            position_x=focus.position_x,
            position_y=focus.position_y,
            width=focus.width,
            softness=focus.softness,
            angle=focus.angle,
        )
        uneven_focus_mask = apply_uneven_focus(focus_mask, lens.uneven_focus)
        focus_result = apply_focus_blur(ink_result, uneven_focus_mask, focus.blur)
        lens_result = apply_lens(
            focus_result,
            palette.name,
            palette.tones,
            uneven_focus_mask,
            lens_smear=lens.lens_smear,
            smear_angle=lens.smear_angle,
            soft_bleed=lens.soft_bleed,
        )
        return apply_degradation(
            lens_result,
            palette.name,
            palette.tones,
            film_grain=degradation.film_grain,
            dust=degradation.dust,
            scratches=degradation.scratches,
            edge_decay=degradation.edge_decay,
            exposure_drift=degradation.exposure_drift,
            vignette=degradation.vignette,
            image_fade=degradation.image_fade,
        )
