# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller ONEDIR specification for the portable RuinPrint build.

For startup diagnostics, temporarily change ``console=False`` to ``console=True``.
"""

from pathlib import Path

project_root = Path(SPECPATH).resolve().parent
icon_path = project_root / "assets" / "ruinprint.ico"

analysis = Analysis(
    [str(project_root / "app.py")], pathex=[str(project_root)], binaries=[],
    datas=[(str(project_root / "presets" / "factory_presets.json"), "presets")],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz, analysis.scripts, [], exclude_binaries=True, name="RuinPrint", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=True, console=False,
    version=str(project_root / "packaging" / "version_info.txt"),
    icon=str(icon_path) if icon_path.is_file() else None,
)
coll = COLLECT(executable, analysis.binaries, analysis.datas, strip=False, upx=True, name="RuinPrint")
