"""Canonical serialization and validation for visual processing settings."""

from dataclasses import asdict, fields, is_dataclass
from typing import Type, get_type_hints

from core.pipeline import PipelineSettings
from effects.palette import LEGACY_AGED_IVORY_VARIANTS, PALETTES


METADATA_KEY = "ruinprint.settings"
METADATA_SCHEMA_VERSION = 1


def settings_to_dict(settings: PipelineSettings) -> dict:
    """Return the shared, complete settings representation used by the editor."""
    return asdict(settings)


def is_valid_processing_settings(settings: object) -> bool:
    """Check that a settings payload is a complete PipelineSettings-shaped snapshot."""
    return migrate_processing_settings(settings) is not None


def migrate_processing_settings(settings: object) -> dict | None:
    """Normalize legacy Aged Ivory snapshots without modifying their source files."""
    if not isinstance(settings, dict):
        return None
    migrated = {group: values.copy() if isinstance(values, dict) else values for group, values in settings.items()}
    palette = migrated.get("palette")
    if not isinstance(palette, dict):
        return None
    palette = palette.copy()
    legacy_name = palette.get("name")
    if legacy_name in LEGACY_AGED_IVORY_VARIANTS:
        hue, influence = _LEGACY_AGED_IVORY_SETTINGS[legacy_name]
        palette.update(name="Aged Ivory", aged_ivory_hue=hue, aged_ivory_influence=influence)
    palette.setdefault("aged_ivory_hue", 0)
    palette.setdefault("aged_ivory_influence", 0)
    migrated["palette"] = palette
    if not _matches_dataclass(migrated, PipelineSettings):
        return None

    dither = migrated["dither"]
    if not (
        palette["name"] in PALETTES
        and palette["tones"] in PALETTES[palette["name"]]
        and 1 <= dither["scale"] <= 32
        and 0 <= palette["aged_ivory_hue"] <= 359
        and 0 <= palette["aged_ivory_influence"] <= 100
    ):
        return None
    return migrated


def metadata_payload(settings: PipelineSettings) -> dict:
    """Create the versioned metadata envelope stored in exported PNG files."""
    return {
        "app": "RuinPrint",
        "type": "processing-settings",
        "schema_version": METADATA_SCHEMA_VERSION,
        "settings": settings_to_dict(settings),
    }


def recoverable_settings(payload: object) -> dict | None:
    """Return a valid settings snapshot from a RuinPrint metadata envelope."""
    if not isinstance(payload, dict):
        return None
    if (
        payload.get("app") != "RuinPrint"
        or payload.get("type") != "processing-settings"
        or payload.get("schema_version") != METADATA_SCHEMA_VERSION
    ):
        return None
    return migrate_processing_settings(payload.get("settings"))


_LEGACY_AGED_IVORY_SETTINGS = {
    "Aged Ivory Moss": (120, 24), "Aged Ivory Ash": (240, 20),
    "Aged Ivory Umber": (24, 34), "Aged Ivory Ochre": (54, 32),
    "Aged Ivory Violet": (280, 25), "Aged Ivory Amber": (30, 38),
    "Aged Ivory Rose": (330, 27), "Aged Ivory Warm": (4, 22),
    "Aged Ivory Soot": (0, 5), "Aged Ivory Paper": (55, 14),
    "Aged Ivory Oxide": (20, 30),
}


def _matches_dataclass(value: object, dataclass_type: Type) -> bool:
    if not isinstance(value, dict):
        return False
    dataclass_fields = fields(dataclass_type)
    type_hints = get_type_hints(dataclass_type)
    if set(value) != {field.name for field in dataclass_fields}:
        return False

    for field in dataclass_fields:
        candidate = value[field.name]
        field_type = type_hints[field.name]
        if is_dataclass(field_type):
            if not _matches_dataclass(candidate, field_type):
                return False
        elif field_type is bool:
            if not isinstance(candidate, bool):
                return False
        elif field_type is int:
            if not isinstance(candidate, int) or isinstance(candidate, bool):
                return False
        elif field_type is float:
            if not isinstance(candidate, (int, float)) or isinstance(candidate, bool):
                return False
        elif not isinstance(candidate, field_type):
            return False
    return True
