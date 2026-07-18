"""Expected RM-142 navigation security, privacy and authority guards."""

from __future__ import annotations

import inspect

from app.ui import navigation
from app.ui.navigation import NavigationStatus, RouteContext, RouteRequest
from app.ui.widgets.dashboard_layout import DashboardLayout


def test_pure_navigation_contract_does_not_import_runtime_or_domain_owners() -> None:
    source = inspect.getsource(navigation)

    assert "PySide6" not in source
    assert "repositories" not in source
    assert "keyring" not in source
    assert "socket" not in source


def test_unknown_route_failure_is_safe_and_does_not_echo_input() -> None:
    layout = DashboardLayout()
    secret_shaped_target = "unknown?api_key=rm142-sentinel"

    result = layout.navigate(RouteRequest(secret_shaped_target))

    assert result.status is NavigationStatus.UNKNOWN_ROUTE
    assert "rm142-sentinel" not in result.message
    assert "rm142-sentinel" not in result.reason_code


def test_context_cannot_hold_runtime_objects_or_private_material() -> None:
    class RuntimeOwner:
        pass

    try:
        RouteContext.from_mapping({"tender_id": RuntimeOwner()})
    except (TypeError, ValueError):
        pass
    else:
        raise AssertionError("runtime object was accepted into route context")

    context = RouteContext(tender_id="T-1", focus_token="TenderFeedTable")
    representation = repr(context)
    assert "api_key" not in representation
    assert "C:\\Users" not in representation
