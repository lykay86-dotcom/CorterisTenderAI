"""Expected RM-142 canonical registry and legacy-alias contract."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.ui.navigation import (
    DEFAULT_ROUTE_REGISTRY,
    RouteAvailability,
    RouteId,
    RouteRegistry,
)


LEGACY_ALIASES = (
    "dashboard",
    "tenders",
    "ai",
    "quotes",
    "estimates",
    "documents",
    "clients",
    "analytics",
    "settings",
)


def test_registry_has_unique_stable_routes_aliases_and_primary_order() -> None:
    specs = DEFAULT_ROUTE_REGISTRY.specs

    assert len({spec.route_id for spec in specs}) == len(specs)
    aliases = tuple(alias for spec in specs for alias in spec.aliases)
    assert len(set(aliases)) == len(aliases)
    assert set(LEGACY_ALIASES) <= set(aliases)
    assert tuple(spec.route_id for spec in DEFAULT_ROUTE_REGISTRY.primary_routes) == (
        RouteId.DASHBOARD,
        RouteId.TENDERS,
        RouteId.WORKFLOW,
        RouteId.FUTURE_ANALYTICS,
    )


@pytest.mark.parametrize(
    ("alias", "route_id"),
    (
        ("dashboard", RouteId.DASHBOARD),
        ("tenders", RouteId.TENDERS),
        ("ai", RouteId.TENDER_AI),
        ("quotes", RouteId.WORKFLOW_PROPOSALS),
        ("estimates", RouteId.WORKFLOW_ESTIMATES),
        ("documents", RouteId.TENDER_DOCUMENTS),
        ("settings", RouteId.TENDER_SETTINGS),
        ("clients", RouteId.FUTURE_CLIENTS),
        ("analytics", RouteId.FUTURE_ANALYTICS),
    ),
)
def test_every_legacy_alias_has_one_explicit_disposition(alias: str, route_id: RouteId) -> None:
    assert DEFAULT_ROUTE_REGISTRY.resolve(alias).route_id is route_id


def test_rm147_analytics_is_primary_while_other_planned_routes_stay_hidden() -> None:
    clients = DEFAULT_ROUTE_REGISTRY.get(RouteId.FUTURE_CLIENTS)
    analytics = DEFAULT_ROUTE_REGISTRY.get(RouteId.FUTURE_ANALYTICS)
    documents = DEFAULT_ROUTE_REGISTRY.get(RouteId.TENDER_DOCUMENTS)

    assert clients.availability is RouteAvailability.PLANNED
    assert clients.planned_rm == "RM-156"
    assert analytics.availability is RouteAvailability.AVAILABLE
    assert analytics.planned_rm is None
    assert documents.availability is RouteAvailability.CONTEXT_REQUIRED
    assert not any(
        spec.route_id in {clients.route_id, documents.route_id}
        for spec in DEFAULT_ROUTE_REGISTRY.primary_routes
    )
    assert analytics in DEFAULT_ROUTE_REGISTRY.primary_routes


def test_registry_rejects_duplicate_alias_and_parent_cycle() -> None:
    dashboard = DEFAULT_ROUTE_REGISTRY.get(RouteId.DASHBOARD)
    tenders = DEFAULT_ROUTE_REGISTRY.get(RouteId.TENDERS)

    with pytest.raises(ValueError, match="alias"):
        RouteRegistry((dashboard, replace(tenders, aliases=("dashboard",))))

    with pytest.raises(ValueError, match="cycle|parent"):
        RouteRegistry(
            (
                replace(dashboard, parent=RouteId.TENDERS),
                replace(tenders, parent=RouteId.DASHBOARD),
            )
        )


def test_every_available_route_has_an_owned_destination() -> None:
    assert all(
        spec.destination
        for spec in DEFAULT_ROUTE_REGISTRY.specs
        if spec.availability in {RouteAvailability.AVAILABLE, RouteAvailability.CONTEXT_REQUIRED}
    )
