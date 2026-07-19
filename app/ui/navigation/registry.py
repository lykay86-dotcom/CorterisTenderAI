"""Canonical immutable RM-142 route registry."""

from __future__ import annotations

from types import MappingProxyType
from typing import Iterable, Mapping

from app.ui.navigation.contracts import (
    DashboardFilterId,
    RouteAvailability,
    RouteContext,
    RouteId,
    RouteKind,
    RouteSpec,
)


_WORKFLOW_CONTEXT = frozenset(
    {
        "workflow_kind",
        "workflow_status",
        "workflow_archive_mode",
        "workflow_search",
        "workflow_record_id",
        "focus_token",
        "dashboard_filter",
    }
)
_TENDER_CONTEXT = frozenset(
    {
        "tender_id",
        "search_query",
        "tender_section",
        "settings_section",
        "focus_token",
        "dashboard_filter",
    }
)


class RouteRegistry:
    """Validated lookup for canonical identities and compatibility aliases."""

    def __init__(self, specs: Iterable[RouteSpec]) -> None:
        ordered = tuple(specs)
        if not ordered:
            raise ValueError("Route registry must not be empty")
        by_id: dict[RouteId, RouteSpec] = {}
        aliases: dict[str, RouteId] = {}
        for spec in ordered:
            if not isinstance(spec, RouteSpec):
                raise TypeError("Route registry accepts RouteSpec values only")
            if spec.route_id in by_id:
                raise ValueError(f"Duplicate route ID: {spec.route_id}")
            by_id[spec.route_id] = spec
            if not spec.title.strip():
                raise ValueError(f"Route title is required: {spec.route_id}")
            if spec.order < 0:
                raise ValueError(f"Route order must be non-negative: {spec.route_id}")
            if not spec.allowed_context <= RouteContext.field_names():
                raise ValueError(f"Unknown allowed context field: {spec.route_id}")
            if (
                spec.availability
                in {
                    RouteAvailability.AVAILABLE,
                    RouteAvailability.CONTEXT_REQUIRED,
                }
                and not spec.destination
            ):
                raise ValueError(f"Available route has no destination: {spec.route_id}")
            if spec.availability is RouteAvailability.PLANNED and not spec.planned_rm:
                raise ValueError(f"Planned route has no target RM: {spec.route_id}")
            for alias in spec.aliases:
                normalized = alias.strip()
                if not normalized or normalized != alias:
                    raise ValueError(f"Invalid route alias: {alias!r}")
                if normalized in aliases:
                    raise ValueError(f"Duplicate route alias: {normalized}")
                if normalized in {route_id.value for route_id in RouteId}:
                    raise ValueError(f"Route alias conflicts with canonical ID: {normalized}")
                aliases[normalized] = spec.route_id

        for spec in ordered:
            if spec.parent is not None and spec.parent not in by_id:
                raise ValueError(f"Unknown route parent: {spec.route_id}")
            if spec.show_in_primary and (
                spec.kind is not RouteKind.PRIMARY or spec.parent is not None
            ):
                raise ValueError(f"Invalid primary route parent: {spec.route_id}")
        self._validate_parent_graph(by_id)
        self._specs = tuple(sorted(ordered, key=lambda spec: (spec.order, spec.route_id.value)))
        self._by_id: Mapping[RouteId, RouteSpec] = MappingProxyType(by_id)
        self._aliases: Mapping[str, RouteId] = MappingProxyType(aliases)

    @staticmethod
    def _validate_parent_graph(by_id: Mapping[RouteId, RouteSpec]) -> None:
        for route_id in by_id:
            visited: set[RouteId] = set()
            current: RouteId | None = route_id
            while current is not None:
                if current in visited:
                    raise ValueError(f"Route parent cycle detected: {route_id}")
                visited.add(current)
                current = by_id[current].parent

    @property
    def specs(self) -> tuple[RouteSpec, ...]:
        return self._specs

    @property
    def aliases(self) -> Mapping[str, RouteId]:
        return self._aliases

    @property
    def primary_routes(self) -> tuple[RouteSpec, ...]:
        return tuple(spec for spec in self._specs if spec.show_in_primary)

    def get(self, route_id: RouteId) -> RouteSpec:
        return self._by_id[route_id]

    def resolve(self, target: RouteId | str) -> RouteSpec | None:
        if isinstance(target, RouteId):
            return self._by_id.get(target)
        if not isinstance(target, str):
            return None
        normalized = target.strip()
        resolved_id: RouteId | None
        try:
            resolved_id = RouteId(normalized)
        except ValueError:
            resolved_id = self._aliases.get(normalized)
        return self._by_id.get(resolved_id) if resolved_id is not None else None

    def validate_context(self, spec: RouteSpec, context: RouteContext) -> str | None:
        if context.provided_fields - spec.allowed_context:
            return "context_field_not_allowed"
        if (
            spec.availability is RouteAvailability.CONTEXT_REQUIRED
            and spec.route_id is RouteId.TENDER_DOCUMENTS
            and not context.tender_id
        ):
            return "tender_id_required"
        if context.dashboard_filter is not None:
            dashboard_filter = DashboardFilterId(context.dashboard_filter)
            if dashboard_filter.route_id is not spec.route_id:
                return "dashboard_filter_route_mismatch"
        return None


def _spec(
    route_id: RouteId,
    title: str,
    *,
    kind: RouteKind,
    availability: RouteAvailability = RouteAvailability.AVAILABLE,
    order: int,
    destination: str | None,
    parent: RouteId | None = None,
    allowed_context: frozenset[str] = frozenset(),
    aliases: tuple[str, ...] = (),
    capability: str = "",
    primary: bool = False,
    history: bool = True,
    journeys: tuple[str, ...] = (),
    planned_rm: str | None = None,
    icon: str = "",
) -> RouteSpec:
    return RouteSpec(
        route_id=route_id,
        title=title,
        parent=parent,
        kind=kind,
        availability=availability,
        order=order,
        destination=destination,
        allowed_context=allowed_context,
        aliases=aliases,
        capability=capability,
        show_in_primary=primary,
        history_enabled=history,
        journeys=journeys,
        planned_rm=planned_rm,
        icon=icon,
    )


DEFAULT_ROUTE_REGISTRY = RouteRegistry(
    (
        _spec(
            RouteId.DASHBOARD,
            "Рабочий стол",
            kind=RouteKind.PRIMARY,
            order=10,
            destination="dashboard",
            aliases=("dashboard",),
            primary=True,
            journeys=("J01", "J03"),
            icon="navigation.dashboard",
        ),
        _spec(
            RouteId.TENDERS,
            "Тендеры и рабочие модули",
            kind=RouteKind.PRIMARY,
            order=20,
            destination="tenders",
            allowed_context=_TENDER_CONTEXT,
            aliases=("tenders",),
            primary=True,
            journeys=("J03", "J04", "J07", "J09"),
            icon="navigation.tenders",
        ),
        _spec(
            RouteId.WORKFLOW,
            "КП, сметы и проекты",
            kind=RouteKind.PRIMARY,
            order=30,
            destination="workflow",
            allowed_context=_WORKFLOW_CONTEXT,
            primary=True,
            journeys=("J12", "J13"),
            icon="navigation.workflow",
        ),
        _spec(
            RouteId.WORKFLOW_PROPOSALS,
            "Коммерческие предложения",
            kind=RouteKind.SECONDARY,
            order=31,
            destination="workflow",
            parent=RouteId.WORKFLOW,
            allowed_context=_WORKFLOW_CONTEXT,
            aliases=("quotes",),
            journeys=("J12",),
        ),
        _spec(
            RouteId.WORKFLOW_ESTIMATES,
            "Сметы",
            kind=RouteKind.SECONDARY,
            order=32,
            destination="workflow",
            parent=RouteId.WORKFLOW,
            allowed_context=_WORKFLOW_CONTEXT,
            aliases=("estimates",),
            journeys=("J12",),
        ),
        _spec(
            RouteId.WORKFLOW_PROJECTS,
            "Проекты",
            kind=RouteKind.SECONDARY,
            order=33,
            destination="workflow",
            parent=RouteId.WORKFLOW,
            allowed_context=_WORKFLOW_CONTEXT,
            journeys=("J12",),
        ),
        _spec(
            RouteId.TENDER_AI,
            "AI-анализ",
            kind=RouteKind.EMBEDDED,
            order=40,
            destination="tenders",
            parent=RouteId.TENDERS,
            allowed_context=_TENDER_CONTEXT,
            aliases=("ai",),
            journeys=("J10",),
        ),
        _spec(
            RouteId.TENDER_SETTINGS,
            "Настройки тендеров",
            kind=RouteKind.EMBEDDED,
            order=41,
            destination="tenders",
            parent=RouteId.TENDERS,
            allowed_context=_TENDER_CONTEXT,
            aliases=("settings",),
            journeys=("J06", "J10"),
        ),
        _spec(
            RouteId.TENDER_DOCUMENTS,
            "Документы тендера",
            kind=RouteKind.MODAL,
            availability=RouteAvailability.CONTEXT_REQUIRED,
            order=42,
            destination="tender_documents",
            parent=RouteId.TENDERS,
            allowed_context=frozenset({"tender_id", "focus_token"}),
            aliases=("documents",),
            capability="tender_id_required",
            history=False,
            journeys=("J09",),
        ),
        _spec(
            RouteId.TENDER_SCHEDULER,
            "Расписание поиска",
            kind=RouteKind.MODAL,
            order=43,
            destination="tender_scheduler",
            parent=RouteId.TENDERS,
            allowed_context=frozenset({"focus_token"}),
            history=False,
            journeys=("J08",),
        ),
        _spec(
            RouteId.TENDER_NOTIFICATIONS,
            "Уведомления",
            kind=RouteKind.MODAL,
            order=44,
            destination="tender_notifications",
            parent=RouteId.TENDERS,
            allowed_context=frozenset({"focus_token"}),
            history=False,
            journeys=("J08",),
        ),
        _spec(
            RouteId.PROFILE,
            "Профиль",
            kind=RouteKind.MODAL,
            order=45,
            destination="profile",
            parent=RouteId.DASHBOARD,
            allowed_context=frozenset({"focus_token"}),
            history=False,
            journeys=("J01",),
        ),
        _spec(
            RouteId.FUTURE_ANALYTICS,
            "Аналитика",
            kind=RouteKind.COMPATIBILITY,
            availability=RouteAvailability.PLANNED,
            order=90,
            destination=None,
            aliases=("analytics",),
            capability="planned_rm_147",
            primary=False,
            history=False,
            planned_rm="RM-147",
        ),
        _spec(
            RouteId.FUTURE_CLIENTS,
            "Клиенты",
            kind=RouteKind.COMPATIBILITY,
            availability=RouteAvailability.PLANNED,
            order=91,
            destination=None,
            aliases=("clients",),
            capability="planned_rm_156",
            primary=False,
            history=False,
            planned_rm="RM-156",
        ),
    )
)


__all__ = ["DEFAULT_ROUTE_REGISTRY", "RouteRegistry"]
