"""Integration tests for Dashboard AI Advisor."""

from __future__ import annotations

from app.ui.pages.dashboard_page import DashboardPage
from app.ui.viewmodels.dashboard_viewmodel import RecentTender


def test_priority_tender_uses_highest_ai_score() -> None:
    tenders = [
        RecentTender(number="1", title="A", customer="X", score=65),
        RecentTender(number="2", title="B", customer="Y", score=92),
        RecentTender(number="3", title="C", customer="Z", score=None),
    ]

    priority = DashboardPage._priority_tender(tenders)

    assert priority is not None
    assert priority.number == "2"


def test_priority_tender_returns_none_for_empty_list() -> None:
    assert DashboardPage._priority_tender([]) is None
