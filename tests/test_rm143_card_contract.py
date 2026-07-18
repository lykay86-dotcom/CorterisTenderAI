"""Expected RM-143 card focus, keyboard, tone and effect lifecycle."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ui.theme.colors import ThemeName
from app.ui.widgets.card import Card, CardTone, KpiCard


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("theme", tuple(ThemeName))
@pytest.mark.parametrize("tone", tuple(CardTone))
def test_card_tone_theme_matrix_has_accessible_text(theme, tone) -> None:
    _app()
    card = Card("Результат", subtitle="Пояснение", tone=tone, theme=theme)
    assert card.accessibleName() == "Результат"
    assert card.accessibleDescription() == "Пояснение"
    assert card.styleSheet()


def test_clickable_card_activates_by_keyboard_and_reuses_shadow_effect() -> None:
    _app()
    card = Card("Открыть", clickable=True, shadow=True)
    received: list[bool] = []
    card.clicked.connect(lambda: received.append(True))
    effect = card.graphicsEffect()

    assert card.focusPolicy() == Qt.FocusPolicy.StrongFocus
    QTest.keyClick(card, Qt.Key.Key_Space)
    assert received == [True]

    for theme in (ThemeName.LIGHT, ThemeName.DARK, ThemeName.LIGHT):
        card.set_theme(theme)
    assert card.graphicsEffect() is effect


def test_kpi_card_remains_a_presentation_only_value_surface() -> None:
    _app()
    card = KpiCard("Новые", "12", trend="+2", trend_tone=CardTone.SUCCESS)
    assert card.value == "12"
    assert card._trend_label.text() == "+2"
