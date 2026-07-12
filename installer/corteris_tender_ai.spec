# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-file build for Corteris Tender AI."""

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)


SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent

entry_point = ROOT / "app" / "main.py"
templates = ROOT / "templates"
version_info = SPEC_DIR / "version_info.txt"

missing = []
if not entry_point.is_file():
    missing.append(f"entry point: {entry_point}")
if not templates.is_dir():
    missing.append(f"templates: {templates}")
if not version_info.is_file():
    missing.append(f"version info: {version_info}")
if missing:
    raise SystemExit(
        "Missing required project paths:\n" + "\n".join(missing)
    )


def optional_tree(name: str) -> list[tuple[str, str]]:
    source = ROOT / name
    return [(str(source), name)] if source.is_dir() else []


def optional_metadata(distribution: str) -> list[tuple[str, str]]:
    try:
        return copy_metadata(distribution)
    except Exception:
        return []


def optional_submodules(package: str) -> list[str]:
    try:
        return collect_submodules(package)
    except Exception:
        return []


datas = [(str(templates), "templates")]
for directory in ("assets", "data", "config"):
    datas.extend(optional_tree(directory))

# HTTPX uses certifi in standard installations. Explicit collection prevents a
# one-file build from losing cacert.pem after extraction to sys._MEIPASS.
datas.extend(collect_data_files("certifi"))
for distribution in (
    "certifi",
    "httpx",
    "httpcore",
    "anyio",
    "keyring",
    "cryptography",
    "py7zr",
    "rarfile",
):
    datas.extend(optional_metadata(distribution))

hiddenimports = {
    "anyio._backends._asyncio",
    "httpcore._backends.anyio",
    "httpcore._backends.auto",
    "httpcore._backends.sync",
    "keyring.backends.Windows",
    "keyring.backends.fail",
}
for package in (
    "keyring.backends",
    "py7zr",
    "rarfile",
):
    hiddenimports.update(optional_submodules(package))


a = Analysis(
    [str(entry_point)],
    pathex=[str(ROOT)],
    binaries=[],
    datas=sorted(set(datas)),
    hiddenimports=sorted(hiddenimports),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
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
    version=str(version_info),
)
