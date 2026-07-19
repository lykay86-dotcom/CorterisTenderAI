"""Canonical RM-142 information-architecture boundary."""

from app.ui.navigation.contracts import (
    DashboardFilterId,
    NavigationCause,
    NavigationSnapshot,
    NavigationStatus,
    RouteAvailability,
    RouteContext,
    RouteId,
    RouteKind,
    RouteRequest,
    RouteResult,
    RouteSpec,
)
from app.ui.navigation.history import DEFAULT_HISTORY_LIMIT, NavigationHistory
from app.ui.navigation.registry import DEFAULT_ROUTE_REGISTRY, RouteRegistry

__all__ = [
    "DEFAULT_HISTORY_LIMIT",
    "DEFAULT_ROUTE_REGISTRY",
    "DashboardFilterId",
    "NavigationCause",
    "NavigationHistory",
    "NavigationSnapshot",
    "NavigationStatus",
    "RouteAvailability",
    "RouteContext",
    "RouteId",
    "RouteKind",
    "RouteRegistry",
    "RouteRequest",
    "RouteResult",
    "RouteSpec",
]
