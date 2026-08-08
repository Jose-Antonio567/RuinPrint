"""Explicit reduced palettes and non-destructive RGBA quantization."""

import numpy as np
from PIL import Image


PALETTES: dict[str, dict[int, tuple[tuple[int, int, int], ...]]] = {
    "Neutral": {
        2: ((18, 18, 18), (235, 235, 235)),
        3: ((18, 18, 18), (126, 126, 126), (235, 235, 235)),
        4: ((18, 18, 18), (83, 83, 83), (161, 161, 161), (235, 235, 235)),
        5: ((18, 18, 18), (63, 63, 63), (126, 126, 126), (181, 181, 181), (235, 235, 235)),
        6: ((18, 18, 18), (52, 52, 52), (101, 101, 101), (151, 151, 151), (195, 195, 195), (235, 235, 235)),
    },
    "Aged Ivory": {
        2: ((25, 22, 19), (224, 216, 194)),
        3: ((25, 22, 19), (112, 102, 86), (224, 216, 194)),
        4: ((25, 22, 19), (72, 65, 55), (145, 134, 112), (224, 216, 194)),
        5: ((25, 22, 19), (56, 51, 44), (105, 96, 80), (166, 154, 128), (224, 216, 194)),
        6: ((25, 22, 19), (48, 44, 38), (84, 77, 65), (127, 117, 98), (178, 165, 137), (224, 216, 194)),
    },
    "Warm Sepia": {
        2: ((29, 22, 17), (230, 211, 172)),
        3: ((29, 22, 17), (111, 82, 57), (230, 211, 172)),
        4: ((29, 22, 17), (75, 54, 39), (151, 116, 78), (230, 211, 172)),
        5: ((29, 22, 17), (58, 43, 32), (108, 80, 57), (176, 138, 93), (230, 211, 172)),
        6: ((29, 22, 17), (49, 37, 28), (84, 62, 45), (132, 98, 68), (188, 149, 100), (230, 211, 172)),
    },
    "Cold Ash": {
        2: ((20, 24, 27), (211, 216, 214)),
        3: ((20, 24, 27), (91, 104, 109), (211, 216, 214)),
        4: ((20, 24, 27), (59, 70, 76), (128, 142, 145), (211, 216, 214)),
        5: ((20, 24, 27), (47, 57, 63), (84, 98, 105), (151, 163, 164), (211, 216, 214)),
        6: ((20, 24, 27), (40, 49, 55), (69, 81, 88), (112, 126, 132), (165, 175, 175), (211, 216, 214)),
    },
}


def apply_palette(image: Image.Image, palette_name: str, tones: int) -> Image.Image:
    """Map an RGBA image to an explicit palette while preserving alpha exactly."""
    try:
        colors = PALETTES[palette_name][tones]
    except KeyError as error:
        raise ValueError("Paleta ou quantidade de tons inválida.") from error

    rgba_image = image.convert("RGBA")
    pixels = np.asarray(rgba_image, dtype=np.uint8)
    rgb = pixels[..., :3].astype(np.float32)
    luminance = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]) / 255.0

    color_array = np.asarray(colors, dtype=np.uint8)
    color_indexes = np.minimum((luminance * len(colors)).astype(np.intp), len(colors) - 1)

    output_pixels = np.empty_like(pixels)
    output_pixels[..., :3] = color_array[color_indexes]
    output_pixels[..., 3] = pixels[..., 3]
    return Image.fromarray(output_pixels, "RGBA")
