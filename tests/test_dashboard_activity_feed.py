"""Tests for Dashboard Activity Feed."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.dashboard.activity_feed import (
    ActivityEntry,
    ActivityFeed,
    ActivityTone,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_activity_feed_orders_newest_first() -> None:
    _app()
    now = datetime.now()
    feed = ActivityFeed(
        [
            ActivityEntry(
                key="old",
                title="Старое событие",
                timestamp=now - timedelta(minutes=5),
            ),
            ActivityEntry(
                key="new",
                title="Новое событие",
                timestamp=now,
            ),
        ]
    )

    assert [entry.key for entry in feed.entries] == ["new", "old"]


def test_activity_feed_respects_history_limit() -> None:
    _app()
    feed = ActivityFeed(max_entries=2)

    for index in range(3):
        feed.add_entry(
            ActivityEntry(
                key=str(index),
                title=f"Событие {index}",
                timestamp=datetime.now() + timedelta(seconds=index),
                tone=ActivityTone.INFO,
            )
        )

    assert len(feed.entries) == 2
    assert [entry.key for entry in feed.entries] == ["2", "1"]


def test_activity_action_emits_key() -> None:
    _app()
    feed = ActivityFeed()
    received: list[str] = []

    feed.action_requested.connect(received.append)
    feed.trigger_action("find_tenders")

    assert received == ["find_tenders"]
