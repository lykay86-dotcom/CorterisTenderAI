"""Tests for Dashboard repository snapshot building."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.ui.controllers.dashboard_controller import (
    DashboardSnapshotBuilder,
)


@dataclass
class FakeAnalysis:
    estimated_profit: Decimal
    created_at: datetime


@dataclass
class FakeTender:
    id: str
    number: str
    title: str
    customer: str = ""
    nmck: Decimal = Decimal("0")
    deadline: str = ""
    score: int = 0
    status: str = "Новый"
    recommendation: str = "Не анализировался"
    platform: str = "Ручной импорт"
    created_at: datetime = datetime(2026, 7, 11, 9, 0)
    analyses: list[FakeAnalysis] = field(default_factory=list)


NOW = datetime(2026, 7, 11, 12, 0)


def test_snapshot_maps_real_tender_fields() -> None:
    builder = DashboardSnapshotBuilder()
    snapshot = builder.build(
        [
            FakeTender(
                id="uuid-1",
                number="0123456789",
                title="Монтаж видеонаблюдения",
                customer="Заказчик",
                nmck=Decimal("1250000"),
                deadline="14.07.2026",
                score=91,
                status="Проанализирован",
                recommendation="Участвовать",
                platform="ЕИС",
            )
        ],
        now=NOW,
    )

    tender = snapshot.tenders[0]
    assert tender.number == "0123456789"
    assert tender.nmck == "1 250 000.00 ₽"
    assert tender.score == 91
    assert snapshot.number_to_id["0123456789"] == "uuid-1"


def test_snapshot_does_not_mix_tender_analysis_into_workflow_profit() -> None:
    builder = DashboardSnapshotBuilder()
    snapshot = builder.build(
        [
            FakeTender(
                id="uuid-1",
                number="1",
                title="Тендер",
                analyses=[
                    FakeAnalysis(
                        Decimal("100000"),
                        datetime(2026, 7, 10, 8, 0),
                    ),
                    FakeAnalysis(
                        Decimal("240000"),
                        datetime(2026, 7, 11, 8, 0),
                    ),
                ],
            )
        ],
        now=NOW,
    )

    profit = next(item for item in snapshot.kpis if item.key == "potential_profit")
    assert profit.raw_value is None
    assert profit.value == "—"


def test_snapshot_counts_score_cohort_but_not_tender_attention() -> None:
    builder = DashboardSnapshotBuilder()
    snapshot = builder.build(
        [
            FakeTender(
                id="recommended",
                number="1",
                title="Рекомендуемый",
                score=88,
                deadline="20.07.2026",
            ),
            FakeTender(
                id="urgent",
                number="2",
                title="Срочный",
                score=55,
                deadline="12.07.2026",
                status="Требует проверки",
            ),
        ],
        now=NOW,
    )

    values = {item.key: item.value for item in snapshot.kpis}
    assert values["recommended"] == "1"
    assert values["attention"] == "—"


def test_snapshot_creates_priority_recommendation() -> None:
    builder = DashboardSnapshotBuilder()
    snapshot = builder.build(
        [
            FakeTender(
                id="low",
                number="1",
                title="Низкий рейтинг",
                score=60,
            ),
            FakeTender(
                id="high",
                number="2",
                title="Высокий рейтинг",
                score=94,
            ),
        ],
        now=NOW,
    )

    assert snapshot.recommendations
    assert "2" in snapshot.recommendations[0].description
    assert "94/100" in snapshot.recommendations[0].description
