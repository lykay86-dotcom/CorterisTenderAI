"""Expected RM-142 bounded in-memory history and return behavior."""

from __future__ import annotations

from app.ui.navigation import (
    NavigationHistory,
    NavigationSnapshot,
    RouteContext,
    RouteId,
)


def _snapshot(route_id: RouteId, *, tender_id: str | None = None) -> NavigationSnapshot:
    return NavigationSnapshot(route_id, RouteContext(tender_id=tender_id))


def test_history_is_bounded_and_consecutive_duplicates_coalesce() -> None:
    history = NavigationHistory(limit=3)
    dashboard = _snapshot(RouteId.DASHBOARD)

    assert history.push(dashboard) is True
    assert history.push(dashboard) is False
    assert history.push(_snapshot(RouteId.TENDERS, tender_id="T-001")) is True
    assert history.push(_snapshot(RouteId.WORKFLOW_PROPOSALS)) is True
    assert history.push(_snapshot(RouteId.WORKFLOW_ESTIMATES)) is True

    assert len(history) == 3
    assert history.entries[0].route_id is RouteId.TENDERS
    assert history.entries[-1].route_id is RouteId.WORKFLOW_ESTIMATES


def test_history_pop_is_safe_and_preserves_exact_context() -> None:
    history = NavigationHistory()
    snapshot = _snapshot(RouteId.TENDERS, tender_id="000123")
    history.push(snapshot)

    assert history.pop() == snapshot
    assert history.pop() is None
    assert snapshot.context.tender_id == "000123"


def test_history_is_memory_only_and_contains_no_runtime_objects() -> None:
    history = NavigationHistory()
    history.push(
        NavigationSnapshot(
            RouteId.WORKFLOW_PROJECTS,
            RouteContext(workflow_kind="project", workflow_record_id="record-7"),
            focus_token="QuickActionTile",
        )
    )

    assert history.entries[0].context.workflow_record_id == "record-7"
    assert not hasattr(history, "path")
    assert not hasattr(history, "save")
