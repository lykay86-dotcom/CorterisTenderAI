"""Expected-red tests for the RM-145 immutable KPI contract."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType

import pytest

from app.repositories.business_metrics import BusinessMetricsSnapshot
from app.ui.controllers.dashboard_controller import DashboardSnapshotBuilder
from app.ui.navigation.contracts import RouteId
from app.ui.viewmodels import dashboard_viewmodel as dashboard_contract


KPI_KEYS = (
    "potential_profit",
    "new_tenders",
    "recommended",
    "proposals_in_work",
    "active_projects",
    "attention",
)
MOSCOW_TIME = timezone(timedelta(hours=3), name="Europe/Moscow")
NOW = datetime(2026, 7, 19, 12, 0, tzinfo=MOSCOW_TIME)


def _contract_type(name: str):
    value = getattr(dashboard_contract, name, None)
    assert value is not None, f"RM-145 contract type is missing: {name}"
    return value


def test_registry_is_immutable_complete_and_the_only_definition_source() -> None:
    registry = getattr(dashboard_contract, "DASHBOARD_KPI_REGISTRY", None)

    assert isinstance(registry, tuple)
    assert tuple(definition.key for definition in registry) == KPI_KEYS
    assert len({definition.formula_version for definition in registry}) == 6
    assert all(definition.owner for definition in registry)
    assert all(definition.action is not None for definition in registry)

    by_key = getattr(dashboard_contract, "DASHBOARD_KPI_BY_KEY", None)
    assert isinstance(by_key, MappingProxyType)
    assert tuple(by_key) == KPI_KEYS
    with pytest.raises(TypeError):
        by_key["unknown"] = registry[0]


def test_builder_publishes_typed_values_evidence_states_and_actions() -> None:
    kpi_state = _contract_type("DashboardKpiState")
    kpi_unit = _contract_type("DashboardKpiUnit")
    snapshot = DashboardSnapshotBuilder().build(
        [],
        now=NOW,
        business=BusinessMetricsSnapshot(
            proposals_in_work=2,
            active_projects=1,
            attention=3,
            potential_profit=Decimal("10.25"),
            profit_sources=1,
        ),
    )
    values = {item.key: item for item in snapshot.kpis}

    assert values["potential_profit"].raw_value == Decimal("10.25")
    assert values["potential_profit"].unit is kpi_unit.RUB
    assert values["potential_profit"].state is kpi_state.READY
    assert values["potential_profit"].action.route_id is RouteId.WORKFLOW
    assert isinstance(values["new_tenders"].raw_value, int)
    assert values["new_tenders"].state is kpi_state.ZERO
    assert values["new_tenders"].raw_value == 0
    assert values["recommended"].title == "Оценка 80+"
    assert "не является рекомендацией" in values["recommended"].accessible_description.lower()
    assert all(
        evidence.observed_at.tzinfo is not None
        for item in snapshot.kpis
        for evidence in item.source_evidence
    )


def test_missing_is_not_coerced_to_zero() -> None:
    kpi_state = _contract_type("DashboardKpiState")
    kpi_type = _contract_type("DashboardKpi")
    definition = getattr(dashboard_contract, "DASHBOARD_KPI_BY_KEY")["new_tenders"]

    missing = kpi_type.from_definition(
        definition,
        raw_value=None,
        state=kpi_state.ERROR,
        source_evidence=(),
        state_reason="tender source failed",
    )

    assert missing.raw_value is None
    assert missing.state is kpi_state.ERROR
    assert missing.value != "0"


def test_viewmodel_publishes_a_complete_snapshot_with_one_state_signal() -> None:
    snapshot = DashboardSnapshotBuilder().build(
        [],
        now=NOW,
        business=BusinessMetricsSnapshot(),
    )
    viewmodel = dashboard_contract.DashboardViewModel()
    states: list[object] = []
    viewmodel.state_changed.connect(states.append)

    viewmodel.apply_snapshot(
        snapshot.kpis,
        recent_tenders=snapshot.tenders,
        ai_recommendations=snapshot.recommendations,
        loaded_at=snapshot.loaded_at,
    )

    assert len(states) == 1
    assert tuple(item.key for item in viewmodel.ordered_kpis()) == KPI_KEYS
    assert viewmodel.state.last_updated == NOW


def test_source_evidence_rejects_naive_observation_time() -> None:
    evidence_type = _contract_type("DashboardSourceEvidence")

    with pytest.raises(ValueError, match="timezone-aware"):
        evidence_type(
            source_id="tenders",
            generation=1,
            observed_at=datetime(2026, 7, 19, 12, 0),
            record_count=0,
        )
