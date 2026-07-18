"""Pure typed contracts for RM-142 information architecture."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class RouteId(StrEnum):
    """Stable canonical route identities independent from display titles."""

    DASHBOARD = "workspace.dashboard"
    TENDERS = "workspace.tenders"
    WORKFLOW = "workspace.workflow"
    WORKFLOW_PROPOSALS = "workspace.workflow.proposals"
    WORKFLOW_ESTIMATES = "workspace.workflow.estimates"
    WORKFLOW_PROJECTS = "workspace.workflow.projects"
    TENDER_AI = "workspace.tenders.ai"
    TENDER_SETTINGS = "workspace.tenders.settings"
    TENDER_DOCUMENTS = "workspace.tenders.documents"
    TENDER_SCHEDULER = "workspace.tenders.scheduler"
    TENDER_NOTIFICATIONS = "workspace.tenders.notifications"
    PROFILE = "workspace.profile"
    FUTURE_CLIENTS = "future.clients"
    FUTURE_ANALYTICS = "future.analytics"


class RouteKind(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    EMBEDDED = "embedded"
    MODAL = "modal"
    COMPATIBILITY = "compatibility"


class RouteAvailability(StrEnum):
    AVAILABLE = "available"
    PLANNED = "planned"
    DISABLED = "disabled"
    CONTEXT_REQUIRED = "context_required"


class NavigationCause(StrEnum):
    SIDEBAR = "sidebar"
    TOPBAR = "topbar"
    QUICK_ACTION = "quick_action"
    SHORTCUT = "shortcut"
    DEEP_LINK = "deep_link"
    BACK = "back"
    RETURN = "return"
    COMPATIBILITY = "compatibility"
    PROGRAMMATIC = "programmatic"


class NavigationStatus(StrEnum):
    NAVIGATED = "navigated"
    UNAVAILABLE = "unavailable"
    INVALID_CONTEXT = "invalid_context"
    UNKNOWN_ROUTE = "unknown_route"
    NO_CHANGE = "no_change"


_BIDI_CONTROLS = frozenset(
    {
        "\u061c",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)


def _normalize_text(
    value: str | None,
    *,
    field_name: str,
    limit: int,
    collapse_whitespace: bool = False,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = " ".join(value.split()) if collapse_whitespace else value.strip()
    if not normalized:
        return None
    if len(normalized) > limit:
        raise ValueError(f"Invalid {field_name}: value is too long")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError(f"Invalid {field_name}: control characters are forbidden")
    if any(character in _BIDI_CONTROLS for character in normalized):
        raise ValueError(f"Invalid {field_name}: bidi controls are forbidden")
    return normalized


@dataclass(frozen=True, slots=True)
class RouteContext:
    """Closed presentation-only context carried between routes."""

    tender_id: str | None = None
    workflow_kind: str | None = None
    workflow_status: str | None = None
    workflow_archive_mode: str | None = None
    workflow_search: str | None = None
    workflow_record_id: str | None = None
    search_query: str | None = None
    tender_section: str | None = None
    settings_section: str | None = None
    focus_token: str | None = None

    def __post_init__(self) -> None:
        values = {
            "tender_id": _normalize_text(
                self.tender_id,
                field_name="tender_id",
                limit=256,
            ),
            "workflow_kind": _normalize_text(
                self.workflow_kind,
                field_name="workflow_kind",
                limit=32,
            ),
            "workflow_status": _normalize_text(
                self.workflow_status,
                field_name="workflow_status",
                limit=64,
            ),
            "workflow_archive_mode": _normalize_text(
                self.workflow_archive_mode,
                field_name="workflow_archive_mode",
                limit=32,
            ),
            "workflow_search": _normalize_text(
                self.workflow_search,
                field_name="workflow_search",
                limit=512,
                collapse_whitespace=True,
            ),
            "workflow_record_id": _normalize_text(
                self.workflow_record_id,
                field_name="workflow_record_id",
                limit=256,
            ),
            "search_query": _normalize_text(
                self.search_query,
                field_name="search_query",
                limit=512,
                collapse_whitespace=True,
            ),
            "tender_section": _normalize_text(
                self.tender_section,
                field_name="tender_section",
                limit=64,
            ),
            "settings_section": _normalize_text(
                self.settings_section,
                field_name="settings_section",
                limit=64,
            ),
            "focus_token": _normalize_text(
                self.focus_token,
                field_name="focus_token",
                limit=128,
            ),
        }
        if values["workflow_kind"] not in {None, "proposal", "estimate", "project"}:
            raise ValueError("Invalid workflow_kind")
        for name, value in values.items():
            object.__setattr__(self, name, value)

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> RouteContext:
        if not isinstance(values, Mapping):
            raise TypeError("Route context must be a mapping")
        unknown = set(values).difference(cls.field_names())
        if unknown:
            raise ValueError("Unknown route context fields")
        return cls(**dict(values))  # type: ignore[arg-type]

    @classmethod
    def field_names(cls) -> frozenset[str]:
        return frozenset(field.name for field in fields(cls))

    @property
    def provided_fields(self) -> frozenset[str]:
        return frozenset(
            field.name for field in fields(self) if getattr(self, field.name) is not None
        )

    def public_mapping(self) -> Mapping[str, str]:
        return MappingProxyType(
            {
                field.name: value
                for field in fields(self)
                if (value := getattr(self, field.name)) is not None
            }
        )


@dataclass(frozen=True, slots=True)
class RouteSpec:
    route_id: RouteId
    title: str
    parent: RouteId | None
    kind: RouteKind
    availability: RouteAvailability
    order: int
    destination: str | None
    allowed_context: frozenset[str] = frozenset()
    aliases: tuple[str, ...] = ()
    capability: str = ""
    show_in_primary: bool = False
    history_enabled: bool = True
    journeys: tuple[str, ...] = ()
    planned_rm: str | None = None
    icon: str = ""


@dataclass(frozen=True, slots=True)
class RouteRequest:
    target: RouteId | str
    cause: NavigationCause = NavigationCause.PROGRAMMATIC
    context: RouteContext = RouteContext()
    origin: RouteId | None = None
    focus_token: str | None = None
    record_history: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.target, (RouteId, str)):
            raise TypeError("Route target must be a string identity")
        if isinstance(self.target, str) and not self.target.strip():
            raise ValueError("Route target must not be blank")
        object.__setattr__(
            self,
            "focus_token",
            _normalize_text(
                self.focus_token,
                field_name="focus_token",
                limit=128,
            ),
        )


@dataclass(frozen=True, slots=True)
class NavigationSnapshot:
    route_id: RouteId
    context: RouteContext = RouteContext()
    focus_token: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "focus_token",
            _normalize_text(
                self.focus_token,
                field_name="focus_token",
                limit=128,
            ),
        )


@dataclass(frozen=True, slots=True)
class RouteResult:
    status: NavigationStatus
    resolved_route: RouteId | None = None
    reason_code: str = ""
    message: str = ""
    snapshot: NavigationSnapshot | None = None
    history_changed: bool = False
    recovery_route: RouteId | None = None

    @property
    def succeeded(self) -> bool:
        return self.status in {NavigationStatus.NAVIGATED, NavigationStatus.NO_CHANGE}


__all__ = [
    "NavigationCause",
    "NavigationSnapshot",
    "NavigationStatus",
    "RouteAvailability",
    "RouteContext",
    "RouteId",
    "RouteKind",
    "RouteRequest",
    "RouteResult",
    "RouteSpec",
]
