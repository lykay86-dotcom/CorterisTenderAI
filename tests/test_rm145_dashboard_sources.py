"""RM-145 source isolation, completeness, and freshness contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.repositories.business_metrics import BusinessMetricsSnapshot
from app.ui.controllers.dashboard_controller import DashboardSnapshotBuilder
from app.ui.viewmodels.dashboard_viewmodel import DashboardKpiState


MOSCOW_TIME = timezone(timedelta(hours=3), name="Europe/Moscow")
NOW = datetime(2026, 7, 19, 12, 0, tzinfo=MOSCOW_TIME)


@dataclass
class _Tender:
    id: str = "tender-1"
    number: str = "145-1"
    title: str = "Тендер"
    score: int = 85
    created_at: datetime = NOW
    customer: str = ""
    nmck: Decimal = Decimal("0")
    deadline: str = ""
    status: str = "Новый"
    recommendation: str = "Не участвовать"
    platform: str = ""
    analyses: tuple[object, ...] = ()


def _business(*, proposals: int = 1) -> BusinessMetricsSnapshot:
    return BusinessMetricsSnapshot(
        proposals_in_work=proposals,
        potential_profit=Decimal("12.50"),
        profit_sources=1,
        proposal_ids=("proposal-1",) if proposals else (),
        profit_contributor_ids=("proposal-1",),
        record_count=1,
    )


def _values(snapshot):
    return {item.key: item for item in snapshot.kpis}


def test_recent_failed_source_is_partial_and_other_source_is_fresh() -> None:
    builder = DashboardSnapshotBuilder()
    previous = builder.build([_Tender()], now=NOW, business=_business(), generation=1)

    refreshed = builder.build(
        [],
        now=NOW + timedelta(minutes=5),
        business=_business(proposals=0),
        generation=2,
        previous=previous,
        tender_error="tender database unavailable",
    )
    values = _values(refreshed)

    assert values["new_tenders"].raw_value == 1
    assert values["new_tenders"].state is DashboardKpiState.PARTIAL
    assert values["recommended"].state is DashboardKpiState.PARTIAL
    assert values["proposals_in_work"].raw_value == 0
    assert values["proposals_in_work"].state is DashboardKpiState.ZERO
    assert values["proposals_in_work"].source_evidence[0].generation == 2
    assert values["new_tenders"].source_evidence[0].refresh_failed is True


def test_retained_value_becomes_stale_after_ten_minutes() -> None:
    builder = DashboardSnapshotBuilder()
    previous = builder.build([_Tender()], now=NOW, business=_business(), generation=1)

    refreshed = builder.build(
        [],
        now=NOW + timedelta(minutes=11),
        business=_business(),
        generation=2,
        previous=previous,
        tender_error="tender database unavailable",
    )

    assert _values(refreshed)["new_tenders"].state is DashboardKpiState.STALE


def test_failed_source_without_prior_value_is_error_not_zero() -> None:
    snapshot = DashboardSnapshotBuilder().build(
        [_Tender()],
        now=NOW,
        business=None,
        generation=1,
        business_error="workflow store unavailable",
    )
    values = _values(snapshot)

    assert values["new_tenders"].state is DashboardKpiState.READY
    for key in (
        "potential_profit",
        "proposals_in_work",
        "active_projects",
        "attention",
    ):
        assert values[key].raw_value is None
        assert values[key].state is DashboardKpiState.ERROR
        assert values[key].value == "—"


def test_complete_empty_source_is_zero() -> None:
    snapshot = DashboardSnapshotBuilder().build(
        [],
        now=NOW,
        business=BusinessMetricsSnapshot(),
    )

    assert all(item.state is DashboardKpiState.ZERO for item in snapshot.kpis)
