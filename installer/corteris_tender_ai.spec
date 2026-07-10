# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

# PyInstaller defines SPECPATH as the directory containing this spec file.
SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent

required_paths = {
    "entry point": ROOT / "app" / "main.py",
    "templates": ROOT / "templates",
    "data": ROOT / "data",
    "assets": ROOT / "assets",
}
missing = [f"{name}: {path}" for name, path in required_paths.items() if not path.exists()]
if missing:
    raise SystemExit("Missing required project paths:\n" + "\n".join(missing))

datas = [
    (str(ROOT / "templates"), "templates"),
    (str(ROOT / "data"), "data"),
    (str(ROOT / "assets"), "assets"),
]

a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["keyring.backends.Windows"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CorterisTenderAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)
