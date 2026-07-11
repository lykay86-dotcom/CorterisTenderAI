"""Tests for Dashboard status feedback."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.dashboard.status_banner import (
    DashboardStatusBanner,
    StatusTone,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_banner_is_hidden_by_default() -> None:
    _app()
    banner = DashboardStatusBanner()

    assert banner.isHidden()


def test_banner_shows_semantic_status() -> None:
    _app()
    banner = DashboardStatusBanner()

    banner.show_status(
        title="Данные обновлены",
        message="Все показатели актуальны.",
        tone=StatusTone.SUCCESS,
    )

    assert not banner.isHidden()
    assert banner.tone == StatusTone.SUCCESS
    assert banner.title_label.text() == "Данные обновлены"


def test_banner_action_emits_key() -> None:
    _app()
    banner = DashboardStatusBanner()
    received: list[str] = []

    banner.action_requested.connect(received.append)
    banner.show_status(
        title="Ошибка",
        tone=StatusTone.ERROR,
        action_text="Повторить",
        action_key="refresh",
    )
    banner.action_button.click()

    assert received == ["refresh"]


def test_banner_clear_resets_action() -> None:
    _app()
    banner = DashboardStatusBanner()
    banner.show_status(
        title="Ошибка",
        action_text="Повторить",
        action_key="refresh",
    )

    banner.clear()

    assert banner.isHidden()
    assert banner.action_key == ""
