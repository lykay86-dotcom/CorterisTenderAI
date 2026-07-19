"""Expected-red tests for RM-145 typed Dashboard drill-down parity."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessStatus,
)
from app.ui.navigation import contracts as navigation_contracts
from app.ui.navigation.contracts import RouteContext, RouteId
from app.ui.navigation.registry import DEFAULT_ROUTE_REGISTRY


def _filter_type():
    filter_type = getattr(navigation_contracts, "DashboardFilterId", None)
    assert filter_type is not None, "DashboardFilterId is missing"
    return filter_type


def test_route_context_round_trips_only_closed_dashboard_filters() -> None:
    filter_type = _filter_type()
    filter_id = filter_type.TENDERS_SCORE_80_PLUS

    context = RouteContext(dashboard_filter=filter_id.value)
    restored = RouteContext.from_mapping(context.public_mapping())

    assert restored == context
    assert (
        DEFAULT_ROUTE_REGISTRY.validate_context(
            DEFAULT_ROUTE_REGISTRY.get(RouteId.TENDERS),
            context,
        )
        is None
    )
    assert (
        DEFAULT_ROUTE_REGISTRY.validate_context(
            DEFAULT_ROUTE_REGISTRY.get(RouteId.WORKFLOW),
            context,
        )
        == "dashboard_filter_route_mismatch"
    )
    with pytest.raises(ValueError, match="dashboard_filter"):
        RouteContext(dashboard_filter="invented_filter")


def test_workflow_snapshot_exposes_exact_count_and_profit_contributors(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    proposal = repository.record_proposal(
        "tender-1",
        status=BusinessStatus.READY,
        profit=Decimal("10.10"),
        due_date="2026-07-20",
    )
    project = repository.record_project(
        "tender-1",
        title="Исполнение",
        status=BusinessStatus.ACTIVE,
        expected_profit=Decimal("20.20"),
    )
    blocked = repository.record_proposal(
        "tender-2",
        status=BusinessStatus.BLOCKED,
        profit=Decimal("15.05"),
    )
    active_proposal = repository.record_proposal(
        "tender-3",
        status=BusinessStatus.DRAFT,
    )

    snapshot = repository.summary(today=date(2026, 7, 19))

    assert snapshot.proposal_ids == (proposal.id, active_proposal.id)
    assert snapshot.project_ids == (project.id,)
    assert snapshot.attention_ids == (proposal.id, blocked.id)
    assert snapshot.profit_contributor_ids == (project.id, blocked.id)
    assert snapshot.proposals_in_work == len(snapshot.proposal_ids)
    assert snapshot.active_projects == len(snapshot.project_ids)
    assert snapshot.attention == len(snapshot.attention_ids)
    assert snapshot.potential_profit == Decimal("35.25")


def test_all_six_filters_have_one_route_family() -> None:
    filter_type = _filter_type()

    assert filter_type.TENDERS_CREATED_TODAY.route_id is RouteId.TENDERS
    assert filter_type.TENDERS_SCORE_80_PLUS.route_id is RouteId.TENDERS
    assert filter_type.WORKFLOW_PROFIT_CONTRIBUTORS.route_id is RouteId.WORKFLOW
    assert filter_type.WORKFLOW_ACTIVE_PROPOSALS.route_id is RouteId.WORKFLOW
    assert filter_type.WORKFLOW_ACTIVE_PROJECTS.route_id is RouteId.WORKFLOW
    assert filter_type.WORKFLOW_ATTENTION.route_id is RouteId.WORKFLOW
