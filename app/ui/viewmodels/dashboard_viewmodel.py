"""Typed immutable presentation contract for the Corteris Dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Callable, Iterable, Mapping

from PySide6.QtCore import QObject, Signal

from app.ui.navigation.contracts import DashboardFilterId, RouteId


APP_TIMEZONE = timezone(timedelta(hours=3), name="Europe/Moscow")


def aware_dashboard_time(value: datetime) -> datetime:
    """Normalize repository/local timestamps to the configured application zone."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=APP_TIMEZONE)
    return value.astimezone(APP_TIMEZONE)


class DashboardKpiState(StrEnum):
    """Closed per-KPI data state."""

    LOADING = "loading"
    READY = "ready"
    ZERO = "zero"
    PARTIAL = "partial"
    STALE = "stale"
    ERROR = "error"


class DashboardKpiUnit(StrEnum):
    """Raw-value unit understood by the presentation formatter."""

    COUNT = "count"
    RUB = "rub"


@dataclass(frozen=True, slots=True)
class DashboardSourceEvidence:
    """Evidence for one repository observation used by one KPI."""

    source_id: str
    generation: int
    observed_at: datetime
    record_count: int
    contributor_ids: tuple[str, ...] = ()
    complete: bool = True
    refresh_failed: bool = False
    reason: str = ""
    demo: bool = False

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.source_id.strip():
            raise ValueError("source_id must not be blank")
        if self.generation < 0:
            raise ValueError("generation must be non-negative")
        if self.record_count < 0:
            raise ValueError("record_count must be non-negative")
        normalized_ids = tuple(dict.fromkeys(str(item) for item in self.contributor_ids))
        object.__setattr__(self, "contributor_ids", normalized_ids)


@dataclass(frozen=True, slots=True)
class DashboardKpiAction:
    """Typed navigation action carried by a KPI value."""

    route_id: RouteId
    filter_id: DashboardFilterId
    focus_token: str = "dashboard-kpi"

    def __post_init__(self) -> None:
        if self.filter_id.route_id is not self.route_id:
            raise ValueError("Dashboard filter does not belong to the action route")


@dataclass(frozen=True, slots=True)
class DashboardKpiDefinition:
    """One immutable registry definition."""

    key: str
    title: str
    unit: DashboardKpiUnit
    formula_version: str
    owner: str
    action: DashboardKpiAction
    trend: str = ""
    tone: str = "default"
    icon_text: str = ""
    accessibility: str = ""


DASHBOARD_KPI_REGISTRY = (
    DashboardKpiDefinition(
        key="potential_profit",
        title="Потенциальная прибыль",
        unit=DashboardKpiUnit.RUB,
        formula_version="workflow-potential-profit-v1",
        owner="BusinessMetricsRepository",
        action=DashboardKpiAction(
            RouteId.WORKFLOW,
            DashboardFilterId.WORKFLOW_PROFIT_CONTRIBUTORS,
        ),
        trend="По текущим workflow-записям",
        tone="success",
        icon_text="₽",
        accessibility="Сумма по точным участникам workflow-расчёта.",
    ),
    DashboardKpiDefinition(
        key="new_tenders",
        title="Новые тендеры сегодня",
        unit=DashboardKpiUnit.COUNT,
        formula_version="tender-created-local-day-v1",
        owner="TenderRepository",
        action=DashboardKpiAction(
            RouteId.TENDERS,
            DashboardFilterId.TENDERS_CREATED_TODAY,
        ),
        trend="Добавлены сегодня",
        tone="info",
        icon_text="T",
        accessibility="Активные тендеры, созданные в текущий локальный день.",
    ),
    DashboardKpiDefinition(
        key="recommended",
        title="Оценка 80+",
        unit=DashboardKpiUnit.COUNT,
        formula_version="tender-score-threshold-v1",
        owner="TenderRepository",
        action=DashboardKpiAction(
            RouteId.TENDERS,
            DashboardFilterId.TENDERS_SCORE_80_PLUS,
        ),
        trend="Числовая оценка от 80",
        tone="success",
        icon_text="80+",
        accessibility=(
            "Числовой порог оценки. Когорта не является рекомендацией об участии "
            "и не отменяет критические стоп-факторы."
        ),
    ),
    DashboardKpiDefinition(
        key="proposals_in_work",
        title="Предложения в работе",
        unit=DashboardKpiUnit.COUNT,
        formula_version="workflow-active-proposals-v1",
        owner="BusinessMetricsRepository",
        action=DashboardKpiAction(
            RouteId.WORKFLOW,
            DashboardFilterId.WORKFLOW_ACTIVE_PROPOSALS,
        ),
        trend="Черновик, проверка, готово или отправлено",
        tone="warning",
        icon_text="КП",
        accessibility="Активные коммерческие предложения workflow.",
    ),
    DashboardKpiDefinition(
        key="active_projects",
        title="Активные проекты",
        unit=DashboardKpiUnit.COUNT,
        formula_version="workflow-active-projects-v1",
        owner="BusinessMetricsRepository",
        action=DashboardKpiAction(
            RouteId.WORKFLOW,
            DashboardFilterId.WORKFLOW_ACTIVE_PROJECTS,
        ),
        trend="Текущие стадии исполнения",
        tone="info",
        icon_text="P",
        accessibility="Проекты на активных стадиях исполнения workflow.",
    ),
    DashboardKpiDefinition(
        key="attention",
        title="Workflow: требуют внимания",
        unit=DashboardKpiUnit.COUNT,
        formula_version="workflow-attention-v1",
        owner="BusinessMetricsRepository",
        action=DashboardKpiAction(
            RouteId.WORKFLOW,
            DashboardFilterId.WORKFLOW_ATTENTION,
        ),
        trend="Блокировка или срок до трёх дней",
        tone="warning",
        icon_text="!",
        accessibility="Workflow-записи с блокировкой или ближайшим сроком.",
    ),
)
DASHBOARD_KPI_BY_KEY: Mapping[str, DashboardKpiDefinition] = MappingProxyType(
    {definition.key: definition for definition in DASHBOARD_KPI_REGISTRY}
)


def _format_raw_value(
    raw_value: int | Decimal | None,
    unit: DashboardKpiUnit,
) -> str:
    if raw_value is None:
        return "—"
    if unit is DashboardKpiUnit.RUB:
        amount = raw_value if isinstance(raw_value, Decimal) else Decimal(raw_value)
        rounded = amount.quantize(Decimal("1"))
        return f"{rounded:,.0f} ₽".replace(",", " ")
    return str(int(raw_value))


@dataclass(frozen=True, slots=True)
class DashboardKpi:
    """One typed and view-ready KPI from the canonical registry."""

    key: str
    title: str
    value: str
    trend: str = ""
    tone: str = "default"
    icon_text: str = ""
    raw_value: int | Decimal | None = None
    unit: DashboardKpiUnit = DashboardKpiUnit.COUNT
    formula_version: str = "legacy"
    owner: str = "DashboardViewModel"
    source_evidence: tuple[DashboardSourceEvidence, ...] = ()
    state: DashboardKpiState = DashboardKpiState.LOADING
    state_reason: str = ""
    action: DashboardKpiAction | None = None
    accessible_description: str = ""

    @classmethod
    def from_definition(
        cls,
        definition: DashboardKpiDefinition,
        *,
        raw_value: int | Decimal | None,
        state: DashboardKpiState,
        source_evidence: tuple[DashboardSourceEvidence, ...],
        state_reason: str = "",
        trend: str | None = None,
        tone: str | None = None,
    ) -> DashboardKpi:
        value = _format_raw_value(raw_value, definition.unit)
        evidence_text = ", ".join(
            f"{item.source_id}: {item.observed_at.isoformat()}" for item in source_evidence
        )
        description_parts = [
            definition.accessibility,
            f"Состояние: {state.value}.",
        ]
        if evidence_text:
            description_parts.append(f"Источник: {evidence_text}.")
        if state_reason:
            description_parts.append(state_reason)
        return cls(
            key=definition.key,
            title=definition.title,
            value=value,
            trend=definition.trend if trend is None else trend,
            tone=definition.tone if tone is None else tone,
            icon_text=definition.icon_text,
            raw_value=raw_value,
            unit=definition.unit,
            formula_version=definition.formula_version,
            owner=definition.owner,
            source_evidence=source_evidence,
            state=state,
            state_reason=state_reason,
            action=definition.action,
            accessible_description=" ".join(part for part in description_parts if part),
        )


@dataclass(frozen=True, slots=True)
class RecentTender:
    """Compact tender value shown in the recent-tender feed."""

    number: str
    title: str
    customer: str
    deadline: str = ""
    score: int | None = None
    recommendation: str = ""
    nmck: str = ""
    status: str = ""
    platform: str = ""


@dataclass(frozen=True, slots=True)
class AiRecommendation:
    """One message from the existing AI advisor presentation area."""

    title: str
    description: str
    severity: str = "info"
    action_text: str = ""


@dataclass(frozen=True, slots=True)
class DashboardState:
    """One atomically replaced Dashboard publication."""

    kpis: Mapping[str, DashboardKpi] = field(default_factory=lambda: MappingProxyType({}))
    recent_tenders: tuple[RecentTender, ...] = ()
    ai_recommendations: tuple[AiRecommendation, ...] = ()
    last_updated: datetime | None = None


class DashboardViewModel(QObject):
    """Store and atomically publish Dashboard presentation values."""

    state_changed = Signal(object)
    kpi_changed = Signal(str, object)
    recent_tenders_changed = Signal(object)
    ai_recommendations_changed = Signal(object)
    refresh_requested = Signal()

    KPI_ORDER = tuple(definition.key for definition in DASHBOARD_KPI_REGISTRY)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__(parent)
        self._clock = clock or (lambda: datetime.now(APP_TIMEZONE))
        initial = {
            definition.key: DashboardKpi.from_definition(
                definition,
                raw_value=None,
                state=DashboardKpiState.LOADING,
                source_evidence=(),
                state_reason="Данные ещё не загружены.",
            )
            for definition in DASHBOARD_KPI_REGISTRY
        }
        self._state = DashboardState(kpis=MappingProxyType(initial))

    @property
    def state(self) -> DashboardState:
        return self._state

    def ordered_kpis(self) -> list[DashboardKpi]:
        return [self._state.kpis[key] for key in self.KPI_ORDER if key in self._state.kpis]

    def request_refresh(self) -> None:
        self.refresh_requested.emit()

    def apply_snapshot(
        self,
        kpis: Iterable[DashboardKpi],
        *,
        recent_tenders: Iterable[RecentTender],
        ai_recommendations: Iterable[AiRecommendation],
        loaded_at: datetime,
    ) -> None:
        """Replace every Dashboard value before emitting one state publication."""
        ordered = tuple(kpis)
        by_key = {item.key: item for item in ordered}
        if tuple(item.key for item in ordered) != self.KPI_ORDER:
            raise ValueError("Dashboard snapshot must contain the six registry KPIs in order")
        self._state = DashboardState(
            kpis=MappingProxyType(by_key),
            recent_tenders=tuple(recent_tenders),
            ai_recommendations=tuple(ai_recommendations),
            last_updated=aware_dashboard_time(loaded_at),
        )
        for item in ordered:
            self.kpi_changed.emit(item.key, item)
        self.recent_tenders_changed.emit(self._state.recent_tenders)
        self.ai_recommendations_changed.emit(self._state.ai_recommendations)
        self.state_changed.emit(self._state)

    def set_kpi(
        self,
        key: str,
        *,
        value: str,
        trend: str | None = None,
        tone: str | None = None,
        title: str | None = None,
        icon_text: str | None = None,
    ) -> None:
        """Compatibility mutation that still replaces the complete state."""
        current = self._state.kpis.get(
            key,
            DashboardKpi(key=key, title=title or key, value=value),
        )
        updated = replace(
            current,
            title=current.title if title is None else title,
            value=value,
            trend=current.trend if trend is None else trend,
            tone=current.tone if tone is None else tone,
            icon_text=current.icon_text if icon_text is None else icon_text,
        )
        kpis = dict(self._state.kpis)
        kpis[key] = updated
        self._state = replace(
            self._state,
            kpis=MappingProxyType(kpis),
            last_updated=aware_dashboard_time(self._clock()),
        )
        self.kpi_changed.emit(key, updated)
        self.state_changed.emit(self._state)

    def set_recent_tenders(self, tenders: Iterable[RecentTender]) -> None:
        values = tuple(tenders)
        self._state = replace(
            self._state,
            recent_tenders=values,
            last_updated=aware_dashboard_time(self._clock()),
        )
        self.recent_tenders_changed.emit(values)
        self.state_changed.emit(self._state)

    def set_ai_recommendations(
        self,
        recommendations: Iterable[AiRecommendation],
    ) -> None:
        values = tuple(recommendations)
        self._state = replace(
            self._state,
            ai_recommendations=values,
            last_updated=aware_dashboard_time(self._clock()),
        )
        self.ai_recommendations_changed.emit(values)
        self.state_changed.emit(self._state)

    def clear(self) -> None:
        self._state = replace(
            self._state,
            recent_tenders=(),
            ai_recommendations=(),
            last_updated=aware_dashboard_time(self._clock()),
        )
        self.recent_tenders_changed.emit(())
        self.ai_recommendations_changed.emit(())
        self.state_changed.emit(self._state)


__all__ = [
    "APP_TIMEZONE",
    "AiRecommendation",
    "DASHBOARD_KPI_BY_KEY",
    "DASHBOARD_KPI_REGISTRY",
    "DashboardKpi",
    "DashboardKpiAction",
    "DashboardKpiDefinition",
    "DashboardKpiState",
    "DashboardKpiUnit",
    "DashboardSourceEvidence",
    "DashboardState",
    "DashboardViewModel",
    "RecentTender",
    "aware_dashboard_time",
]
