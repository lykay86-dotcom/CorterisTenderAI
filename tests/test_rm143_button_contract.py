"""Expected RM-143 canonical button family contract."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.ui.theme import DESIGN_TOKENS
from app.ui.theme.colors import ThemeName
from app.ui.theme.icons import IconId
from app.ui.widgets.button import ButtonSize, ButtonVariant, CorterisButton, IconButton


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("theme", tuple(ThemeName))
@pytest.mark.parametrize("variant", tuple(ButtonVariant))
@pytest.mark.parametrize("size", tuple(ButtonSize))
def test_button_matrix_is_token_backed_and_themeable(theme, variant, size) -> None:
    _app()
    kwargs = {"accessible_name": "Действие"} if variant is ButtonVariant.ICON_ONLY else {}
    button = CorterisButton("Действие", variant=variant, size=size, theme=theme, **kwargs)

    assert button.minimumHeight() == DESIGN_TOKENS.controls[size.value].height
    assert button.accessibleName()
    assert button.styleSheet()
    button.set_theme(ThemeName.LIGHT if theme is ThemeName.DARK else ThemeName.DARK)
    assert button.styleSheet()
    button.deleteLater()


def test_icon_only_requires_accessible_name_and_resolves_semantic_icon() -> None:
    _app()
    with pytest.raises(ValueError, match="accessible"):
        IconButton(IconId.ACTION_REFRESH, accessible_name="")

    button = IconButton(IconId.ACTION_REFRESH, accessible_name="Обновить")
    assert button.variant == ButtonVariant.ICON_ONLY.value
    assert button.accessibleName() == "Обновить"
    assert not button.icon().isNull()


def test_loading_uses_owned_timer_and_stops_cleanly() -> None:
    _app()
    button = CorterisButton("Запустить")
    timer = button.loading_timer

    button.loading = True
    assert timer.isActive()
    assert timer.interval() == DESIGN_TOKENS.motion.loading_frame_ms
    assert "Выполнение" in button.accessibleName()

    button.loading = False
    assert not timer.isActive()
    assert button.accessibleName() == "Запустить"
    button.deleteLater()
