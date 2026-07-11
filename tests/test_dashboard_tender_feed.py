"""Tests for the Dashboard tender feed."""

from __future__ import annotations

from app.ui.dashboard.tender_feed import COLUMNS, TenderFeedModel
from app.ui.viewmodels.dashboard_viewmodel import RecentTender


def test_tender_feed_has_expected_columns() -> None:
    assert [column.key for column in COLUMNS] == [
        "number",
        "title",
        "customer",
        "nmck",
        "deadline",
        "score",
        "status",
    ]


def test_tender_feed_model_stores_rows() -> None:
    tender = RecentTender(
        number="0123456789",
        title="Монтаж видеонаблюдения",
        customer="ООО Заказчик",
        nmck="1 250 000 ₽",
        deadline="20.07.2026",
        score=87,
        status="Рекомендуется",
    )
    model = TenderFeedModel([tender])

    assert model.rowCount() == 1
    assert model.columnCount() == len(COLUMNS)
    assert model.tender_at(0) == tender
    assert model.tender_at(5) is None
