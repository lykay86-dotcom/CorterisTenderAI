"""Tests for Dashboard Quick Actions."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.ui.dashboard.quick_actions import (
    DEFAULT_QUICK_ACTIONS,
    QuickActions,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_default_quick_action_order() -> None:
    assert [action.key for action in DEFAULT_QUICK_ACTIONS] == [
        "find_tenders",
        "analyze_documents",
        "create_proposal",
        "create_estimate",
    ]


def test_quick_action_trigger_emits_key() -> None:
    _app()
    widget = QuickActions()
    received: list[str] = []

    widget.action_requested.connect(received.append)
    widget.trigger("create_proposal")

    assert received == ["create_proposal"]


def test_disabled_quick_action_is_not_triggered() -> None:
    _app()
    widget = QuickActions()
    received: list[str] = []

    widget.action_requested.connect(received.append)
    widget.set_enabled("create_estimate", False)
    widget.trigger("create_estimate")

    assert received == []
