"""Expected semantic icon registry and safe fallback."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.navigation import DEFAULT_ROUTE_REGISTRY
from app.ui.theme.icons import ICON_REGISTRY, IconId, IconProvider


ROOT = Path(__file__).parents[1]


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_required_icon_ids_have_owned_svg_assets() -> None:
    required = {
        IconId.NAV_DASHBOARD,
        IconId.NAV_TENDERS,
        IconId.NAV_WORKFLOW,
        IconId.TOPBAR_AI,
        IconId.TOPBAR_NOTIFICATIONS,
        IconId.TOPBAR_THEME,
        IconId.TOPBAR_PROFILE,
        IconId.STATE_INFO,
        IconId.STATE_SUCCESS,
        IconId.STATE_WARNING,
        IconId.STATE_DANGER,
        IconId.FALLBACK,
    }
    assert required <= set(ICON_REGISTRY)

    for spec in ICON_REGISTRY.values():
        asset = ROOT / "assets" / "icons" / spec.filename
        source = asset.read_text(encoding="utf-8")
        assert asset.suffix == ".svg"
        assert "<script" not in source.casefold()
        assert "http://" not in source.casefold()
        assert "https://" not in source.casefold()


def test_routes_use_semantic_icon_ids_without_changing_primary_contract() -> None:
    assert tuple(spec.route_id.value for spec in DEFAULT_ROUTE_REGISTRY.primary_routes) == (
        "workspace.dashboard",
        "workspace.tenders",
        "workspace.workflow",
    )
    assert all(IconId(spec.icon) in ICON_REGISTRY for spec in DEFAULT_ROUTE_REGISTRY.primary_routes)


def test_missing_asset_resolves_to_non_null_safe_fallback(tmp_path: Path) -> None:
    _app()
    provider = IconProvider(asset_root=tmp_path)

    icon = provider.icon(IconId.NAV_DASHBOARD)

    assert not icon.isNull()
    assert provider.fallback_count == 1
