"""Expected deterministic offline RM-143 component gallery."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.component_gallery import COMPONENT_GALLERY_VERSION, ComponentGallery
from app.ui.theme.colors import ThemeName


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_gallery_constructs_all_contract_groups_without_production_route() -> None:
    _app()
    gallery = ComponentGallery(theme=ThemeName.DARK)

    assert COMPONENT_GALLERY_VERSION == "corteris-gallery-v1"
    assert gallery.objectName() == "CorterisComponentGallery"
    assert set(gallery.group_ids) == {
        "buttons",
        "cards",
        "status",
        "data_states",
        "forms",
        "icons",
    }
    assert "Очень длинная" in gallery.synthetic_long_label


def test_gallery_rethemes_repeatedly_without_timer_or_effect_growth() -> None:
    app = _app()
    gallery = ComponentGallery(theme=ThemeName.DARK)
    baseline = gallery.lifecycle_counts()

    for _ in range(3):
        gallery.set_theme(ThemeName.LIGHT)
        gallery.set_theme(ThemeName.DARK)
        app.processEvents()

    assert gallery.lifecycle_counts() == baseline
    gallery.deleteLater()
    app.processEvents()
