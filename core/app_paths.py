"""Portable writable-data and bundled-resource paths for RuinPrint."""

from pathlib import Path
import sys

from PySide6.QtCore import QSettings, QStandardPaths


class AppDataError(RuntimeError):
    """Raised when RuinPrint cannot create or use its portable data directory."""


def app_root() -> Path:
    """Return the folder containing the executable or the source project root."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resource_path(relative_path: str | Path) -> Path:
    """Resolve a read-only bundled resource in source and PyInstaller modes."""
    base = Path(getattr(sys, "_MEIPASS", app_root()))
    return base / relative_path


def data_directory() -> Path:
    """Create and return the portable user-data directory beside the app."""
    directory = app_root() / "data"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".ruinprint-write-test"
        with probe.open("w", encoding="utf-8"):
            pass
        probe.unlink()
    except OSError as error:
        raise AppDataError(
            f"Não foi possível gravar na pasta de dados do RuinPrint:\n{directory}\n\n{error}"
        ) from error
    return directory


def user_presets_path() -> Path:
    """Return the portable User Presets file path."""
    return data_directory() / "user_presets.json"


def legacy_user_presets_path() -> Path:
    """Return the pre-portable User Presets location for one-time migration."""
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    return Path(location) / "user_presets.json"


def get_settings() -> QSettings:
    """Return the portable settings.ini, migrating legacy QSettings once if needed."""
    settings_path = data_directory() / "settings.ini"
    portable_settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
    if not settings_path.exists():
        legacy_settings = QSettings("RuinPrint", "RuinPrint")
        for key in legacy_settings.allKeys():
            portable_settings.setValue(key, legacy_settings.value(key))
        portable_settings.sync()
        try:
            settings_path.touch(exist_ok=True)
        except OSError as error:
            raise AppDataError(
                f"Não foi possível criar as configurações portáteis:\n{settings_path}\n\n{error}"
            ) from error
    return portable_settings
