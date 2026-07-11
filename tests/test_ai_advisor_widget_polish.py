"""Tests for AI Advisor widget polish."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.ui.dashboard.ai_advisor import AiAdvisor, AiStatus


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_ai_advisor_score_is_clamped() -> None:
    _app()
    widget = AiAdvisor()
    widget.set_focus(title="Тендер", score=140)

    assert widget.score_bar.value() == 100
    assert widget.score_value.text() == "100/100"


def test_ai_advisor_busy_state() -> None:
    _app()
    widget = AiAdvisor()
    widget.set_busy(True)

    assert widget._status == AiStatus.BUSY
    assert widget.action_button.get_loading() is True

    widget.set_busy(False)
    assert widget._status == AiStatus.ONLINE
    assert widget.action_button.get_loading() is False
