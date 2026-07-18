"""Characterization of the public presentation contracts inherited by RM-143."""

from __future__ import annotations

from dataclasses import fields
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.navigation import DEFAULT_ROUTE_REGISTRY
from app.ui.theme.colors import DARK_PALETTE, LIGHT_PALETTE, ThemeName, get_palette
from app.ui.theme.stylesheet import build_stylesheet
from app.ui.theme.typography import FontWeight, Typography
from app.ui.widgets import (
    ButtonSize,
    ButtonVariant,
    Card,
    CardTone,
    CorterisButton,
    KpiCard,
)


ROOT = Path(__file__).parents[1]


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_existing_theme_ids_palette_shape_and_typography_names_are_stable() -> None:
    assert ThemeName.DARK.value == "dark"
    assert ThemeName.LIGHT.value == "light"
    assert get_palette("dark") is DARK_PALETTE
    assert get_palette("light") is LIGHT_PALETTE
    assert tuple(item.name for item in fields(DARK_PALETTE)) == tuple(
        item.name for item in fields(LIGHT_PALETTE)
    )
    assert Typography.FAMILY == "Segoe UI"
    assert Typography.BUTTON.weight is FontWeight.SEMIBOLD


def test_existing_global_stylesheet_is_one_pure_palette_builder() -> None:
    dark = build_stylesheet("dark")
    light = build_stylesheet("light")

    assert DARK_PALETTE.app_background in dark
    assert LIGHT_PALETTE.app_background in light
    assert "QMainWindow" in dark
    assert "QPushButton" in dark
    assert "QTableView" in dark
    assert dark != light


def test_existing_button_public_properties_object_name_and_set_text_are_stable() -> None:
    _app()
    button = CorterisButton(
        "Сохранить",
        variant=ButtonVariant.OUTLINE,
        size=ButtonSize.LARGE,
        theme=ThemeName.LIGHT,
    )

    assert button.objectName() == "CorterisButton"
    assert button.variant == ButtonVariant.OUTLINE.value
    assert button.size_name == ButtonSize.LARGE.value
    assert button.theme == ThemeName.LIGHT.value
    assert button.accessibleName() == "Сохранить"

    button.setText("Применить")
    assert button.text() == "Применить"
    assert button.accessibleName() == "Применить"

    button.loading = True
    assert button.loading is True
    assert not button.isEnabled()
    assert button.text().startswith("Выполнение")
    button.loading = False
    assert button.text() == "Применить"
    button.deleteLater()


def test_existing_card_and_kpi_public_surface_is_stable() -> None:
    _app()
    card = Card(
        "Карточка",
        subtitle="Описание",
        value="42",
        tone=CardTone.INFO,
        clickable=True,
    )

    assert card.objectName() == "CorterisCard"
    assert card.title == "Карточка"
    assert card.subtitle == "Описание"
    assert card.value == "42"
    assert card.tone == CardTone.INFO.value
    assert card.clickable is True

    kpi = KpiCard("Новые тендеры", "12", trend="+2")
    assert kpi.title == "Новые тендеры"
    assert kpi.value == "12"
    assert kpi.findChild(type(kpi._trend_label), "KpiTrend") is kpi._trend_label
    card.deleteLater()
    kpi.deleteLater()


def test_route_icon_field_remains_nonempty_string_compatibility_metadata() -> None:
    for spec in DEFAULT_ROUTE_REGISTRY.primary_routes:
        assert isinstance(spec.icon, str)
        assert spec.icon


def test_existing_build_pipeline_collects_assets_tree() -> None:
    spec = (ROOT / "installer" / "corteris_tender_ai.spec").read_text(encoding="utf-8")

    assert 'for directory in ("assets", "data", "config")' in spec
    assert (ROOT / "assets").is_dir()
