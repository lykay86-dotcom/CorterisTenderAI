"""Expected RM-142 typed route and request/result contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.ui.navigation import (
    NavigationCause,
    NavigationSnapshot,
    NavigationStatus,
    RouteAvailability,
    RouteContext,
    RouteId,
    RouteKind,
    RouteRequest,
    RouteResult,
)


def test_route_enums_expose_the_closed_contract() -> None:
    assert {kind.value for kind in RouteKind} == {
        "primary",
        "secondary",
        "embedded",
        "modal",
        "compatibility",
    }
    assert {state.value for state in RouteAvailability} == {
        "available",
        "planned",
        "disabled",
        "context_required",
    }
    assert {state.value for state in NavigationStatus} == {
        "navigated",
        "unavailable",
        "invalid_context",
        "unknown_route",
        "no_change",
    }


def test_request_context_snapshot_and_result_are_immutable() -> None:
    context = RouteContext(tender_id="tender-007", focus_token="TenderFeedTable")
    request = RouteRequest(
        target="tenders",
        cause=NavigationCause.DEEP_LINK,
        context=context,
    )
    snapshot = NavigationSnapshot(RouteId.TENDERS, context, "TenderFeedTable")
    result = RouteResult(
        status=NavigationStatus.NAVIGATED,
        resolved_route=RouteId.TENDERS,
        snapshot=snapshot,
        history_changed=True,
    )

    with pytest.raises(FrozenInstanceError):
        context.tender_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        request.target = "dashboard"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        snapshot.route_id = RouteId.DASHBOARD  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.status = NavigationStatus.NO_CHANGE  # type: ignore[misc]


def test_route_identity_is_independent_from_display_title() -> None:
    assert RouteId.DASHBOARD.value == "workspace.dashboard"
    assert RouteId.TENDERS.value == "workspace.tenders"
    assert RouteId.WORKFLOW_PROPOSALS.value == "workspace.workflow.proposals"
    assert RouteId.TENDER_NOTIFICATIONS.value == "workspace.tenders.notifications"
