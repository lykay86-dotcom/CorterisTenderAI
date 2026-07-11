"""Tests for Dashboard UX review fixes."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.dashboard.quick_actions import QuickActions
from app.ui.dashboard.tender_feed import (
    TenderFeed,
    TenderFeedDelegate,
    TenderFeedDensity,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_tender_feed_density_breakpoints() -> None:
    assert (
        TenderFeed.density_for_width(500)
        == TenderFeedDensity.NARROW
    )
    assert (
        TenderFeed.density_for_width(650)
        == TenderFeedDensity.COMPACT
    )
    assert (
        TenderFeed.density_for_width(850)
        == TenderFeedDensity.STANDARD
    )
    assert (
        TenderFeed.density_for_width(1200)
        == TenderFeedDensity.DETAILED
    )


def test_tender_feed_visible_columns_are_reduced() -> None:
    _app()
    feed = TenderFeed()

    feed.set_density(TenderFeedDensity.NARROW)
    assert feed.visible_column_keys == (
        "title",
        "deadline",
        "score",
    )

    feed.set_density(TenderFeedDensity.DETAILED)
    assert "number" in feed.visible_column_keys
    assert "status" in feed.visible_column_keys


def test_score_and_status_semantics() -> None:
    assert TenderFeedDelegate.score_level(94) == "success"
    assert TenderFeedDelegate.score_level(72) == "warning"
    assert TenderFeedDelegate.score_level(41) == "danger"
    assert (
        TenderFeedDelegate.status_level("Рекомендуется")
        == "success"
    )
    assert (
        TenderFeedDelegate.status_level("Требует внимания")
        == "warning"
    )


def test_quick_actions_compact_mode_reduces_density() -> None:
    _app()
    actions = QuickActions()
    first = actions.tiles[0]

    actions.set_compact(True)
    assert first.minimumHeight() == 78
    assert first.description_label.isHidden()
    assert first.shortcut_label.isHidden()

    actions.set_compact(False)
    assert first.minimumHeight() == 104
    assert not first.description_label.isHidden()
