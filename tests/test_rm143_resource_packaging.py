"""Expected repository-owned icon and frozen-build packaging contract."""

from __future__ import annotations

import json
from pathlib import Path

from app.ui.theme.icons import ICON_REGISTRY


ROOT = Path(__file__).parents[1]


def test_icon_manifest_has_provenance_and_matches_registry() -> None:
    icon_root = ROOT / "assets" / "icons"
    manifest = json.loads((icon_root / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["schema"] == "corteris-icon-assets-v1"
    assert manifest["license"] == "Corteris original assets"
    assert set(manifest["files"]) == {spec.filename for spec in ICON_REGISTRY.values()}
    assert all((icon_root / filename).is_file() for filename in manifest["files"])


def test_pyinstaller_and_frozen_self_test_require_icon_assets() -> None:
    spec = (ROOT / "installer" / "corteris_tender_ai.spec").read_text(encoding="utf-8")
    frozen = (ROOT / "app" / "core" / "frozen_self_test.py").read_text(encoding="utf-8")

    assert 'for directory in ("assets", "data", "config")' in spec
    assert "icon_manifest" in frozen
