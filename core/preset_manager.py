"""Persistent, versioned user processing presets."""

import json
from pathlib import Path

from core.app_paths import legacy_user_presets_path, resource_path, user_presets_path
from core.processing_settings import is_valid_processing_settings, migrate_processing_settings


class PresetManager:
    VERSION = 1

    def __init__(self) -> None:
        self.path = user_presets_path()
        self.presets: dict[str, dict] = {}
        self.factory_presets: dict[str, dict] = {}
        self.load_error = False
        self.load()
        self._load_factory()

    def load(self) -> None:
        if not self.path.exists():
            self._migrate_legacy_presets()
        if not self.path.exists():
            self._write()
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            presets = payload.get("presets", {})
            if payload.get("version") != self.VERSION or not isinstance(presets, dict):
                raise ValueError("Formato de presets inválido.")
            self.presets = {name: values for name, values in presets.items() if self._valid(name, values)}
        except (OSError, ValueError, json.JSONDecodeError):
            self.load_error = True
            self.presets = {}

    def _migrate_legacy_presets(self) -> None:
        """Copy a valid legacy file once, without changing its original copy."""
        legacy_path = legacy_user_presets_path()
        if not legacy_path.exists() or legacy_path.resolve() == self.path.resolve():
            return
        try:
            payload = json.loads(legacy_path.read_text(encoding="utf-8"))
            presets = payload.get("presets", {})
            if payload.get("version") != self.VERSION or not isinstance(presets, dict):
                raise ValueError("Formato de presets inválido.")
            migrated = {name: values for name, values in presets.items() if self._valid(name, values)}
            if len(migrated) != len(presets):
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps({"version": self.VERSION, "presets": migrated}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except (OSError, ValueError, json.JSONDecodeError):
            return

    def names(self) -> list[str]:
        return sorted(self.presets, key=str.casefold)

    def get(self, name: str) -> dict | None:
        value = self.factory_presets.get(name) or self.presets.get(name)
        return migrate_processing_settings(value) if value else None

    def is_factory(self, name: str) -> bool:
        return name in self.factory_presets

    def _load_factory(self) -> None:
        factory_path = resource_path("presets/factory_presets.json")
        try:
            overrides = json.loads(factory_path.read_text(encoding="utf-8")).get("presets", {})
            defaults = self._defaults()
            self.factory_presets = {name: self._merge(defaults, value) for name, value in overrides.items() if isinstance(value, dict)}
        except (OSError, ValueError, json.JSONDecodeError):
            self.factory_presets = {}

    @staticmethod
    def _merge(base: dict, override: dict) -> dict:
        return {key: PresetManager._merge(value, override.get(key, {})) if isinstance(value, dict) else override.get(key, value) for key, value in base.items()}

    @staticmethod
    def _defaults() -> dict:
        return {"tone":{"contrast":0,"black_crush":0,"highlight_burn":0,"gamma":1.0},"palette":{"name":"Aged Ivory","tones":4,"aged_ivory_hue":0,"aged_ivory_influence":0},"dither":{"mode":"Bayer","strength":70,"scale":1},"dither_destruction":{"pattern_distortion":0,"dither_loss":0,"dither_spread":0},"engraving":{"strength":0,"detail":35,"thickness":1,"direction":"Natural"},"black_consumption":{"amount":0,"reach":2,"detail_swallow":0},"ink":{"ink_bleed":0,"ink_loss":0,"paper_grain":0,"speckles":0,"print_misalignment":0},"focus":{"shape":"Horizontal","position_x":50,"position_y":50,"width":40,"softness":40,"angle":0,"blur":0},"lens":{"uneven_focus":0,"lens_smear":0,"smear_angle":0,"soft_bleed":0},"degradation":{"film_grain":0,"dust":0,"scratches":0,"edge_decay":0,"exposure_drift":0,"vignette":0,"image_fade":0}}

    def save(self, name: str, settings: dict) -> None:
        name = self._clean_name(name)
        if not self._valid(name, settings):
            raise ValueError("Preset inválido.")
        self.presets[name] = settings
        self._write()

    def rename(self, old_name: str, new_name: str) -> None:
        new_name = self._clean_name(new_name)
        if old_name not in self.presets or (new_name != old_name and new_name in self.presets):
            raise ValueError("Nome de preset inválido ou já existente.")
        self.presets[new_name] = self.presets.pop(old_name)
        self._write()

    def delete(self, name: str) -> None:
        if name in self.presets:
            del self.presets[name]
            self._write()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"version": self.VERSION, "presets": self.presets}, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _clean_name(name: str) -> str:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("O nome do preset não pode estar vazio.")
        return cleaned

    @staticmethod
    def _valid(name: str, settings: object) -> bool:
        return (
            isinstance(name, str)
            and bool(name.strip())
            and is_valid_processing_settings(settings)
        )
