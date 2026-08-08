"""Preview-processing pipeline orchestration."""

from dataclasses import dataclass

from PIL import Image

from effects.tone import apply_tone


@dataclass(frozen=True)
class ToneParameters:
    """Parameters for the tone stage of the image pipeline."""

    contrast: int = 0
    black_crush: int = 0
    highlight_burn: int = 0
    gamma: float = 1.0


class ImagePipeline:
    """Apply the enabled processing stages to an original preview image."""

    def process_preview(
        self, original_preview: Image.Image, tone: ToneParameters
    ) -> Image.Image:
        """Process a preview from its preserved original, starting with Tone."""
        return apply_tone(
            original_preview,
            contrast=tone.contrast,
            black_crush=tone.black_crush,
            highlight_burn=tone.highlight_burn,
            gamma=tone.gamma,
        )
