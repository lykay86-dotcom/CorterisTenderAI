"""Passing characterization for the owners inherited by RM-145."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.repositories.business_metrics import BusinessMetricsSnapshot
from app.ui.controllers import DashboardController as ExportedDashboardController
from app.ui.controllers.dashboard_controller import (
    DashboardController,
    DashboardSnapshotBuilder,
)
from app.ui.navigation.contracts import RouteId
from app.ui.navigation.registry import DEFAULT_ROUTE_REGISTRY
from app.ui.viewmodels.dashboard_viewmodel import DashboardViewModel


KPI_KEYS = (
    "potential_profit",
    "new_tenders",
    "recommended",
    "proposals_in_work",
    "active_projects",
    "attention",
)
NOW = datetime(
    2026,
    7,
    19,
    12,
    0,
    tzinfo=timezone(timedelta(hours=3), name="Europe/Moscow"),
)


@dataclass
class _Tender:
    id: str
    number: str
    title: str
    score: int
    recommendation: str
    created_at: datetime = NOW
    customer: str = ""
    nmck: Decimal = Decimal("0")
    deadline: str = ""
    status: str = "Новый"
    platform: str = "Ручной импорт"
    analyses: tuple[object, ...] = ()


def test_dashboard_controller_has_one_public_class_identity() -> None:
    assert ExportedDashboardController is DashboardController


def test_existing_route_registry_owns_dashboard_and_drilldown_destinations() -> None:
    assert DEFAULT_ROUTE_REGISTRY.get(RouteId.DASHBOARD).destination == "dashboard"
    assert DEFAULT_ROUTE_REGISTRY.get(RouteId.TENDERS).destination == "tenders"
    assert DEFAULT_ROUTE_REGISTRY.get(RouteId.WORKFLOW).destination == "workflow"
    assert DEFAULT_ROUTE_REGISTRY.get(RouteId.WORKFLOW_PROPOSALS).destination == "workflow"
    assert DEFAULT_ROUTE_REGISTRY.get(RouteId.WORKFLOW_PROJECTS).destination == "workflow"


def test_dashboard_preserves_the_six_stable_kpi_keys_and_order() -> None:
    viewmodel = DashboardViewModel()

    assert tuple(item.key for item in viewmodel.ordered_kpis()) == KPI_KEYS


def test_snapshot_builder_uses_workflow_metrics_without_changing_key_order() -> None:
    snapshot = DashboardSnapshotBuilder().build(
        [],
        now=NOW,
        business=BusinessMetricsSnapshot(
            proposals_in_work=2,
            estimates_in_work=1,
            active_projects=3,
            attention=4,
            potential_profit=Decimal("1234.56"),
            profit_sources=2,
        ),
    )

    assert tuple(item.key for item in snapshot.kpis) == KPI_KEYS
    assert snapshot.loaded_at == NOW
    values = {item.key: item.value for item in snapshot.kpis}
    assert values["proposals_in_work"] == "2"
    assert values["active_projects"] == "3"


def test_score_cohort_does_not_mutate_the_saved_recommendation() -> None:
    tender = _Tender(
        id="stop-factor",
        number="145-1",
        title="Пороговая оценка",
        score=80,
        recommendation="Не участвовать: критический стоп-фактор",
    )

    snapshot = DashboardSnapshotBuilder().build([tender], now=NOW)
    values = {item.key: item.value for item in snapshot.kpis}

    assert values["recommended"] == "1"
    assert tender.recommendation == "Не участвовать: критический стоп-фактор"
