"""Fail-closed renderer environment and Windows font fingerprinting."""

from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import os
from pathlib import Path
import platform
import sys

import PIL
from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QLocale, qVersion
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from app.ui.theme.tokens import DESIGN_SYSTEM_VERSION

from .contracts import FontFingerprint, RendererFingerprint


FONT_FILENAMES = ("segoeui.ttf", "seguisb.ttf", "segoeuib.ttf", "consola.ttf")
EXPECTED_FONT_FAMILIES = {"segoeui.ttf": "Segoe UI", "consola.ttf": "Consolas"}
PROFILE_ID_ENV = "RM154_RENDERER_PROFILE"
TIMEZONE_ID = "Europe/Moscow"


class RendererEnvironmentError(RuntimeError):
    """The host cannot produce a trustworthy RM-154 capture."""


def _font_root() -> Path:
    windows_root = Path(os.environ.get("WINDIR", r"C:\Windows")).resolve(strict=False)
    font_root = (windows_root / "Fonts").resolve(strict=False)
    if not font_root.is_relative_to(windows_root):
        raise RendererEnvironmentError("Windows font root escapes WINDIR")
    return font_root


@lru_cache(maxsize=1)
def register_and_fingerprint_fonts() -> tuple[FontFingerprint, ...]:
    if QApplication.instance() is None:
        raise RendererEnvironmentError("QApplication must exist before font registration")
    if platform.system() != "Windows":
        raise RendererEnvironmentError("RM-154 canonical renderer requires Windows")

    records: list[FontFingerprint] = []
    for filename in FONT_FILENAMES:
        path = (_font_root() / filename).resolve(strict=True)
        if not path.is_relative_to(_font_root()):
            raise RendererEnvironmentError(f"font path escaped root: {filename}")
        payload = path.read_bytes()
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            raise RendererEnvironmentError(f"Qt rejected required font: {filename}")
        families = tuple(QFontDatabase.applicationFontFamilies(font_id))
        expected_family = EXPECTED_FONT_FAMILIES.get(filename, "Segoe UI")
        if expected_family not in families:
            raise RendererEnvironmentError(
                f"required family {expected_family!r} missing from {filename}"
            )
        records.append(
            FontFingerprint(
                file_name=filename,
                byte_size=len(payload),
                sha256=sha256(payload).hexdigest(),
                families=families,
            )
        )

    available = set(QFontDatabase.families())
    for family in ("Segoe UI", "Consolas"):
        if family not in available:
            raise RendererEnvironmentError(f"required registered family unavailable: {family}")
    return tuple(records)


def collect_renderer_fingerprint(root: Path) -> RendererFingerprint:
    app = QApplication.instance()
    if app is None:
        raise RendererEnvironmentError("QApplication is not initialized")
    screen = app.primaryScreen()
    if screen is None:
        raise RendererEnvironmentError("Qt offscreen primary screen is unavailable")
    icon_manifest = root / "assets" / "icons" / "manifest.json"
    icon_hash = sha256(icon_manifest.read_bytes()).hexdigest()
    locale = QLocale("ru_RU")
    QLocale.setDefault(locale)
    ci_image = ":".join(
        value
        for value in (os.environ.get("ImageOS", "local"), os.environ.get("ImageVersion", ""))
        if value
    )
    return RendererFingerprint(
        profile_id=os.environ.get(PROFILE_ID_ENV, "local-noncanonical"),
        platform=platform.system(),
        platform_release=platform.release(),
        platform_version=platform.version(),
        ci_image=ci_image,
        python=platform.python_version(),
        pyside=pyside_version,
        qt=qVersion(),
        pillow=PIL.__version__,
        qpa_platform=os.environ.get("QT_QPA_PLATFORM", ""),
        qt_style=app.style().objectName().lower(),
        qt_locale=locale.name(),
        timezone=TIMEZONE_ID,
        logical_dpi=round(float(screen.logicalDotsPerInch()), 4),
        device_pixel_ratio=round(float(screen.devicePixelRatio()), 4),
        color_depth=int(screen.depth()),
        fonts=register_and_fingerprint_fonts(),
        icon_manifest_sha256=icon_hash,
        design_system_version=DESIGN_SYSTEM_VERSION,
    )


def is_canonical_ci() -> bool:
    return (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get(PROFILE_ID_ENV) == "windows-latest-python312"
        and sys.version_info[:2] == (3, 12)
    )
