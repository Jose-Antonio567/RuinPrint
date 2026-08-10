"""Persistent, versioned user processing presets."""

import json
from pathlib import Path

from PySide6.QtCore import QStandardPaths


class PresetManager:
    VERSION = 1

    def __init__(self) -> None:
        location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        self.path = Path(location) / "user_presets.json"
        self.presets: dict[str, dict] = {}
        self.load_error = False
        self.load()

    def load(self) -> None:
        if not self.path.exists():
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

    def names(self) -> list[str]:
        return sorted(self.presets, key=str.casefold)

    def get(self, name: str) -> dict | None:
        value = self.presets.get(name)
        return value.copy() if value else None

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
        return isinstance(name, str) and bool(name.strip()) and isinstance(settings, dict) and bool(settings)
