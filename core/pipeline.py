"""Preview-processing pipeline orchestration."""

from dataclasses import dataclass
from typing import Callable

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


@dataclass(frozen=True)
class PipelineSettings:
    """Complete visual settings snapshot, reusable for preview and export."""

    tone: ToneParameters
    palette: PaletteParameters
    dither: DitherParameters
    dither_destruction: DitherDestructionParameters
    engraving: EngravingParameters
    black_consumption: BlackConsumptionParameters
    ink: InkParameters
    focus: FocusParameters
    lens: LensParameters
    degradation: DegradationParameters


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
        return self.process(
            original_preview,
            PipelineSettings(tone, palette, dither, dither_destruction, engraving, black_consumption, ink, focus, lens, degradation),
        )

    def process(
        self,
        image: Image.Image,
        settings: PipelineSettings,
        *,
        spatial_scale: float = 1.0,
        progress_callback: Callable[[int], None] | None = None,
    ) -> Image.Image:
        """Run the single visual pipeline for any resolution using a settings snapshot."""
        def report(value: int) -> None:
            if progress_callback is not None:
                progress_callback(value)

        tone, palette = settings.tone, settings.palette
        dither, destruction = settings.dither, settings.dither_destruction
        engraving, consumption = settings.engraving, settings.black_consumption
        ink, focus, lens, degradation = settings.ink, settings.focus, settings.lens, settings.degradation
        spatial_scale = max(float(spatial_scale), 1.0)
        report(5)
        tone_result = apply_tone(
            image,
            contrast=tone.contrast,
            black_crush=tone.black_crush,
            highlight_burn=tone.highlight_burn,
            gamma=tone.gamma,
        )
        report(15)
        dither_result = apply_dither(
            tone_result,
            palette.name,
            palette.tones,
            dither.mode,
            dither.strength,
            max(1, int(round(dither.scale * spatial_scale))),
            destruction.pattern_distortion,
        )
        report(30)
        destruction_result = apply_dither_destruction(
            dither_result,
            palette.name,
            palette.tones,
            dither_loss=destruction.dither_loss,
            dither_spread=destruction.dither_spread,
            scale=max(1, int(round(dither.scale * spatial_scale))),
        )
        report(40)
        engraving_result = apply_engraving(
            destruction_result,
            palette.name,
            palette.tones,
            strength=engraving.strength,
            detail=engraving.detail,
            thickness=max(1, int(round(engraving.thickness * spatial_scale))),
            direction=engraving.direction,
        )
        report(50)
        consumption_result = apply_black_consumption(
            engraving_result,
            palette.name,
            palette.tones,
            amount=consumption.amount,
            reach=max(1, int(round(consumption.reach * spatial_scale))),
            detail_swallow=consumption.detail_swallow,
            dither_scale=max(1, int(round(dither.scale * spatial_scale))),
        )
        report(58)
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
        report(68)
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
        report(78)
        lens_result = apply_lens(
            focus_result,
            palette.name,
            palette.tones,
            uneven_focus_mask,
            lens_smear=lens.lens_smear,
            smear_angle=lens.smear_angle,
            soft_bleed=lens.soft_bleed,
        )
        report(86)
        result = apply_degradation(
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
        report(94)
        return result
