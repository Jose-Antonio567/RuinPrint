"""Canonical serialization and validation for visual processing settings."""

from dataclasses import asdict, fields, is_dataclass
from typing import Type, get_type_hints

from core.pipeline import PipelineSettings
from effects.palette import PALETTES


METADATA_KEY = "ruinprint.settings"
METADATA_SCHEMA_VERSION = 1


def settings_to_dict(settings: PipelineSettings) -> dict:
    """Return the shared, complete settings representation used by the editor."""
    return asdict(settings)


def is_valid_processing_settings(settings: object) -> bool:
    """Check that a settings payload is a complete PipelineSettings-shaped snapshot."""
    if not _matches_dataclass(settings, PipelineSettings):
        return False

    palette = settings["palette"]
    dither = settings["dither"]
    return (
        palette["name"] in PALETTES
        and palette["tones"] in PALETTES[palette["name"]]
        and 1 <= dither["scale"] <= 32
    )


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
    settings = payload.get("settings")
    return settings if is_valid_processing_settings(settings) else None


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
