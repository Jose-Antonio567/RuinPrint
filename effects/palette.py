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

_MASTER_PALETTES = {
    "Aged Ivory Moss": ((9,10,7),(35,39,28),(68,73,50),(105,110,78),(152,154,113),(213,207,167)),
    "Aged Ivory Ash": ((8,9,10),(32,35,37),(65,69,71),(103,107,106),(151,153,146),(215,211,190)),
    "Aged Ivory Umber": ((12,9,7),(43,33,26),(78,60,45),(118,92,69),(166,136,103),(223,197,159)),
    "Aged Ivory Ochre": ((12,10,6),(45,39,24),(82,71,42),(123,108,66),(172,154,102),(228,211,157)),
    "Aged Ivory Violet": ((10,8,10),(39,31,38),(71,56,70),(108,86,106),(154,126,149),(217,190,205)),
    "Aged Ivory Amber": ((13,9,6),(47,31,21),(86,55,36),(127,84,55),(175,123,84),(229,184,134)),
    "Aged Ivory Rose": ((12,8,9),(44,31,34),(79,57,63),(118,87,93),(164,125,129),(222,184,181)),
    "Aged Ivory Warm": ((11,9,7),(43,36,29),(80,66,52),(122,101,78),(171,147,113),(226,208,172)),
    "Aged Ivory Soot": ((7,8,8),(30,31,30),(62,61,57),(101,97,88),(151,143,126),(213,202,178)),
    "Aged Ivory Paper": ((13,11,8),(48,43,34),(88,78,60),(132,117,89),(181,163,126),(232,216,179)),
    "Aged Ivory Oxide": ((13,9,7),(48,32,25),(84,55,42),(123,84,62),(169,128,96),(222,194,157)),
    "Bone & Soot": ((9,9,8),(40,39,36),(76,73,67),(118,113,102),(170,162,145),(224,215,193)),
    "Newsprint": ((12,12,11),(45,44,41),(83,81,75),(124,121,111),(171,167,152),(218,214,196)),
    "Silver Gelatin": ((8,10,12),(36,41,45),(72,80,86),(113,123,129),(163,171,176),(219,223,224)),
    "Oxide Brown": ((15,10,8),(55,35,28),(93,58,45),(132,85,64),(174,129,101),(222,190,155)),
    "Moss Archive": ((10,12,8),(37,42,28),(72,78,50),(108,113,76),(155,157,112),(214,208,165)),
    "Faded Blueprint": ((8,11,14),(31,43,52),(59,76,87),(94,111,121),(143,157,164),(207,214,215)),
    "Dust Rose": ((14,10,11),(48,35,38),(81,60,64),(119,90,93),(162,127,129),(216,183,178)),
    "Parchment": ((14,11,8),(50,42,31),(88,73,53),(128,108,79),(175,151,114),(228,205,163)),
}
_TONE_INDEXES = {2:(0,5), 3:(0,3,5), 4:(0,2,4,5), 5:(0,1,3,4,5), 6:(0,1,2,3,4,5)}
PALETTES.update({name: {tones: tuple(master[index] for index in indexes) for tones, indexes in _TONE_INDEXES.items()} for name, master in _MASTER_PALETTES.items()})


def get_palette(palette_name: str, tones: int) -> tuple[tuple[int, int, int], ...]:
    """Return the explicit RGB colors for a palette selection."""
    try:
        return PALETTES[palette_name][tones]
    except KeyError as error:
        raise ValueError("Paleta ou quantidade de tons inválida.") from error


def palette_luminance(colors: tuple[tuple[int, int, int], ...]) -> np.ndarray:
    """Return normalized luminance values for explicit RGB palette colors."""
    color_array = np.asarray(colors, dtype=np.float32)
    return (
        0.2126 * color_array[:, 0]
        + 0.7152 * color_array[:, 1]
        + 0.0722 * color_array[:, 2]
    ) / 255.0


def nearest_palette_indexes(
    luminance: np.ndarray, palette_luminances: np.ndarray
) -> np.ndarray:
    """Find the nearest explicit palette color for each luminance value."""
    distances = np.abs(luminance[..., np.newaxis] - palette_luminances)
    return np.argmin(distances, axis=-1)


def apply_palette(image: Image.Image, palette_name: str, tones: int) -> Image.Image:
    """Map an RGBA image to an explicit palette while preserving alpha exactly."""
    colors = get_palette(palette_name, tones)

    rgba_image = image.convert("RGBA")
    pixels = np.asarray(rgba_image, dtype=np.uint8)
    rgb = pixels[..., :3].astype(np.float32)
    luminance = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]) / 255.0

    color_array = np.asarray(colors, dtype=np.uint8)
    color_indexes = nearest_palette_indexes(luminance, palette_luminance(colors))

    output_pixels = np.empty_like(pixels)
    output_pixels[..., :3] = color_array[color_indexes]
    output_pixels[..., 3] = pixels[..., 3]
    return Image.fromarray(output_pixels, "RGBA")
