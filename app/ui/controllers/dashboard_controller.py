"""Controller that connects Dashboard 1.0 to real tender data."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Protocol, Sequence

from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    QThread,
    QTimer,
    Signal,
    Slot,
)

from app.repositories.business_metrics import (
    BusinessActivity,
    BusinessMetricsRepository,
    BusinessMetricsSnapshot,
)
from app.repositories.tenders import TenderRepository, select_dashboard_tenders
from app.ui.dashboard.activity_feed import (
    ActivityEntry,
    ActivityTone,
)
from app.ui.dashboard.data_state import DataState
from app.ui.viewmodels.dashboard_viewmodel import (
    APP_TIMEZONE,
    DASHBOARD_KPI_BY_KEY,
    AiRecommendation,
    DashboardKpi,
    DashboardKpiState,
    DashboardSourceEvidence,
    RecentTender,
    aware_dashboard_time,
)


class TenderRepositoryLike(Protocol):
    """Minimum tender repository contract required by the controller."""

    def list(self) -> Sequence[Any]: ...


class BusinessMetricsRepositoryLike(Protocol):
    """Minimum business workflow repository contract."""

    def summary(self, *, today: date | None = None) -> BusinessMetricsSnapshot: ...


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """View-ready Dashboard data built from repository entities."""

    kpis: tuple[DashboardKpi, ...]
    tenders: tuple[RecentTender, ...]
    recommendations: tuple[AiRecommendation, ...]
    activities: tuple[ActivityEntry, ...]
    number_to_id: dict[str, str]
    loaded_at: datetime
    source_errors: tuple[str, ...] = ()


class DashboardSnapshotBuilder:
    """Maps ORM tender entities to stable Dashboard view models."""

    RECOMMENDED_SCORE = 80
    ATTENTION_DAYS = 3
    RECENT_LIMIT = 8
    FRESHNESS_THRESHOLD = timedelta(minutes=10)

    ATTENTION_STATUS_WORDS = (
        "вниман",
        "риск",
        "просроч",
        "уточн",
        "провер",
    )

    def build(
        self,
        entities: Iterable[Any],
        *,
        now: datetime | None = None,
        business: BusinessMetricsSnapshot | None = None,
        generation: int = 1,
        previous: DashboardSnapshot | None = None,
        tender_error: str = "",
        business_error: str = "",
    ) -> DashboardSnapshot:
        loaded_at = aware_dashboard_time(now or datetime.now(APP_TIMEZONE))
        rows = list(entities)
        sorted_rows = sorted(
            rows,
            key=self._created_sort_key,
            reverse=True,
        )

        if tender_error and previous is not None:
            recent = previous.tenders
            number_to_id = dict(previous.number_to_id)
        else:
            recent = tuple(
                self._to_recent_tender(entity) for entity in sorted_rows[: self.RECENT_LIMIT]
            )
            number_to_id = {
                tender.number: str(self._value(entity, "id", tender.number))
                for entity, tender in zip(
                    sorted_rows[: self.RECENT_LIMIT],
                    recent,
                    strict=False,
                )
            }

        today = loaded_at.date()
        new_today_rows = select_dashboard_tenders(
            rows,
            "tenders_created_today",
            at=loaded_at,
        )
        recommended = select_dashboard_tenders(
            rows,
            "tenders_score_80_plus",
            at=loaded_at,
        )
        tender_attention = [entity for entity in rows if self._requires_attention(entity, today)]

        kpis = self._build_kpis(
            loaded_at=loaded_at,
            rows=rows,
            new_today_rows=new_today_rows,
            recommended_rows=recommended,
            business=business,
            generation=generation,
            previous=previous,
            tender_error=tender_error,
            business_error=business_error,
        )
        if tender_error and previous is not None:
            recommendations = previous.recommendations
            activities = previous.activities
        else:
            recommendations = self._build_recommendations(
                rows,
                attention=tender_attention,
            )
            activities = self._build_activities(
                sorted_rows,
                loaded_at=loaded_at,
            )
        if business is not None and business.recent_activities:
            activities = tuple(
                sorted(
                    [
                        *activities,
                        *(self._business_activity(item) for item in business.recent_activities),
                    ],
                    key=lambda item: aware_dashboard_time(item.timestamp or datetime.min),
                    reverse=True,
                )[:8]
            )

        return DashboardSnapshot(
            kpis=kpis,
            tenders=recent,
            recommendations=recommendations,
            activities=activities,
            number_to_id=number_to_id,
            loaded_at=loaded_at,
            source_errors=tuple(message for message in (tender_error, business_error) if message),
        )

    def _build_kpis(
        self,
        *,
        loaded_at: datetime,
        rows: Sequence[Any],
        new_today_rows: Sequence[Any],
        recommended_rows: Sequence[Any],
        business: BusinessMetricsSnapshot | None,
        generation: int,
        previous: DashboardSnapshot | None,
        tender_error: str,
        business_error: str,
    ) -> tuple[DashboardKpi, ...]:
        def ids(values: Sequence[Any]) -> tuple[str, ...]:
            return tuple(str(self._value(item, "id", "")) for item in values)

        tender_record_count = len(rows)
        tender_evidence = {
            "new_tenders": DashboardSourceEvidence(
                source_id="tenders",
                generation=generation,
                observed_at=loaded_at,
                record_count=tender_record_count,
                contributor_ids=ids(new_today_rows),
            ),
            "recommended": DashboardSourceEvidence(
                source_id="tenders",
                generation=generation,
                observed_at=loaded_at,
                record_count=tender_record_count,
                contributor_ids=ids(recommended_rows),
            ),
        }
        business_record_count = business.record_count if business is not None else 0

        def business_evidence(
            contributor_ids: tuple[str, ...],
        ) -> tuple[DashboardSourceEvidence, ...]:
            if business is None:
                return ()
            return (
                DashboardSourceEvidence(
                    source_id="business_workflow",
                    generation=generation,
                    observed_at=loaded_at,
                    record_count=business_record_count,
                    contributor_ids=contributor_ids,
                ),
            )

        raw_values: dict[str, int | Decimal | None] = {
            "potential_profit": business.potential_profit if business is not None else None,
            "new_tenders": len(new_today_rows),
            "recommended": len(recommended_rows),
            "proposals_in_work": business.proposals_in_work if business is not None else None,
            "active_projects": business.active_projects if business is not None else None,
            "attention": business.attention if business is not None else None,
        }
        evidence = {
            "potential_profit": business_evidence(
                business.profit_contributor_ids if business is not None else ()
            ),
            "new_tenders": (tender_evidence["new_tenders"],),
            "recommended": (tender_evidence["recommended"],),
            "proposals_in_work": business_evidence(
                business.proposal_ids if business is not None else ()
            ),
            "active_projects": business_evidence(
                business.project_ids if business is not None else ()
            ),
            "attention": business_evidence(business.attention_ids if business is not None else ()),
        }
        trends = {
            "potential_profit": (
                f"Источников расчёта: {business.profit_sources}"
                if business is not None
                else "Источник workflow недоступен"
            ),
            "proposals_in_work": (
                f"Смет в работе: {business.estimates_in_work}"
                if business is not None
                else "Источник workflow недоступен"
            ),
        }

        def state_for(value: int | Decimal | None) -> DashboardKpiState:
            if value is None:
                return DashboardKpiState.ERROR
            if value == 0:
                return DashboardKpiState.ZERO
            return DashboardKpiState.READY

        fresh = {
            key: DashboardKpi.from_definition(
                DASHBOARD_KPI_BY_KEY[key],
                raw_value=raw_values[key],
                state=state_for(raw_values[key]),
                source_evidence=evidence[key],
                state_reason=(
                    "Источник workflow не загрузил значение." if raw_values[key] is None else ""
                ),
                trend=trends.get(key),
            )
            for key in DASHBOARD_KPI_BY_KEY
        }
        previous_by_key = {item.key: item for item in previous.kpis} if previous is not None else {}

        def failed_value(key: str, reason: str) -> DashboardKpi:
            prior = previous_by_key.get(key)
            if prior is None or prior.raw_value is None:
                failed_evidence = DashboardSourceEvidence(
                    source_id=(
                        "tenders" if key in {"new_tenders", "recommended"} else "business_workflow"
                    ),
                    generation=generation,
                    observed_at=loaded_at,
                    record_count=0,
                    complete=False,
                    refresh_failed=True,
                    reason=reason,
                )
                return DashboardKpi.from_definition(
                    DASHBOARD_KPI_BY_KEY[key],
                    raw_value=None,
                    state=DashboardKpiState.ERROR,
                    source_evidence=(failed_evidence,),
                    state_reason=reason,
                )

            prior_observed_at = min(
                (evidence.observed_at for evidence in prior.source_evidence),
                default=loaded_at,
            )
            age = loaded_at - aware_dashboard_time(prior_observed_at)
            state = (
                DashboardKpiState.STALE
                if age > self.FRESHNESS_THRESHOLD
                else DashboardKpiState.PARTIAL
            )
            retained_evidence = tuple(
                replace(
                    evidence,
                    refresh_failed=True,
                    reason=reason,
                )
                for evidence in prior.source_evidence
            )
            return DashboardKpi.from_definition(
                DASHBOARD_KPI_BY_KEY[key],
                raw_value=prior.raw_value,
                state=state,
                source_evidence=retained_evidence,
                state_reason=reason,
                trend=prior.trend,
                tone=prior.tone,
            )

        if tender_error:
            for key in ("new_tenders", "recommended"):
                fresh[key] = failed_value(key, tender_error)
        if business_error or business is None:
            reason = business_error or "Источник workflow недоступен."
            for key in (
                "potential_profit",
                "proposals_in_work",
                "active_projects",
                "attention",
            ):
                fresh[key] = failed_value(key, reason)
        return tuple(fresh[key] for key in DASHBOARD_KPI_BY_KEY)

    def _build_recommendations(
        self,
        rows: Sequence[Any],
        *,
        attention: Sequence[Any],
    ) -> tuple[AiRecommendation, ...]:
        recommendations: list[AiRecommendation] = []
        analyzed = [row for row in rows if self._score(row) > 0]

        if analyzed:
            priority = max(analyzed, key=self._score)
            number = self._display_number(priority)
            title = str(self._value(priority, "title", "Без названия"))
            score = self._score(priority)
            severity = "success" if score >= self.RECOMMENDED_SCORE else "info"
            recommendations.append(
                AiRecommendation(
                    title="Приоритетный тендер",
                    description=(f"{number} — {title}. AI Score: {score}/100."),
                    severity=severity,
                    action_text="Открыть тендер",
                )
            )

        if attention:
            nearest = min(
                attention,
                key=lambda row: (
                    self._days_to_deadline(row, date.today())
                    if self._days_to_deadline(row, date.today()) is not None
                    else 10_000
                ),
            )
            recommendations.append(
                AiRecommendation(
                    title="Требуется проверка",
                    description=(
                        f"{self._display_number(nearest)}: "
                        "проверьте срок подачи, статус и комплект документов."
                    ),
                    severity="warning",
                    action_text="Проверить документы",
                )
            )

        if not analyzed and rows:
            recommendations.append(
                AiRecommendation(
                    title="Тендеры ещё не проанализированы",
                    description=(
                        "Запустите AI-анализ, чтобы получить "
                        "рейтинг, риски и рекомендацию об участии."
                    ),
                    severity="info",
                    action_text="Запустить анализ",
                )
            )

        return tuple(recommendations[:4])

    def _build_activities(
        self,
        rows: Sequence[Any],
        *,
        loaded_at: datetime,
    ) -> tuple[ActivityEntry, ...]:
        activities: list[ActivityEntry] = [
            ActivityEntry(
                key=f"dashboard-refresh-{loaded_at.timestamp()}",
                title="Dashboard обновлён",
                description=f"Загружено тендеров: {len(rows)}.",
                timestamp=loaded_at,
                tone=ActivityTone.INFO,
                icon_text="↻",
            )
        ]

        for entity in rows[:3]:
            number = self._display_number(entity)
            score = self._score(entity)
            description = str(self._value(entity, "title", "Тендер без названия"))
            if score > 0:
                description = f"{description}. AI Score: {score}/100."

            activities.append(
                ActivityEntry(
                    key=f"tender-{self._value(entity, 'id', number)}",
                    title=f"Тендер {number}",
                    description=description,
                    timestamp=self._created_at(entity) or loaded_at,
                    tone=(
                        ActivityTone.SUCCESS
                        if score >= self.RECOMMENDED_SCORE
                        else ActivityTone.NEUTRAL
                    ),
                    icon_text="T",
                    action_text="Открыть",
                    action_key=f"open_tender:{number}",
                )
            )

        return tuple(activities)

    @staticmethod
    def _business_activity(
        item: BusinessActivity,
    ) -> ActivityEntry:
        tone = {
            "success": ActivityTone.SUCCESS,
            "warning": ActivityTone.WARNING,
            "danger": ActivityTone.DANGER,
            "info": ActivityTone.INFO,
            "neutral": ActivityTone.NEUTRAL,
        }.get(item.tone, ActivityTone.NEUTRAL)
        return ActivityEntry(
            key=item.key,
            title=item.title,
            description=item.description,
            timestamp=item.timestamp,
            tone=tone,
            icon_text="₽",
            action_text="Открыть",
            action_key=item.action_key,
        )

    def _to_recent_tender(self, entity: Any) -> RecentTender:
        score = self._score(entity)
        return RecentTender(
            number=self._display_number(entity),
            title=str(self._value(entity, "title", "Без названия")),
            customer=str(self._value(entity, "customer", "")),
            deadline=str(self._value(entity, "deadline", "")),
            score=score if score > 0 else None,
            recommendation=str(
                self._value(
                    entity,
                    "recommendation",
                    "Не анализировался",
                )
            ),
            nmck=self._format_money(self._decimal(self._value(entity, "nmck", 0))),
            status=str(self._value(entity, "status", "Новый")),
            platform=str(self._value(entity, "platform", "Ручной импорт")),
        )

    def _requires_attention(
        self,
        entity: Any,
        today: date,
    ) -> bool:
        days = self._days_to_deadline(entity, today)
        deadline_risk = days is not None and 0 <= days <= self.ATTENTION_DAYS
        status_risk = self._status_contains(
            entity,
            self.ATTENTION_STATUS_WORDS,
        )
        return deadline_risk or bool(status_risk)

    def _days_to_deadline(
        self,
        entity: Any,
        today: date,
    ) -> int | None:
        deadline = self._parse_deadline(self._value(entity, "deadline", ""))
        if deadline is None:
            return None
        return (deadline - today).days

    def _status_contains(
        self,
        entity: Any,
        words: Sequence[str],
    ) -> int:
        status = str(self._value(entity, "status", "")).strip().lower()
        return int(any(word in status for word in words))

    def _display_number(self, entity: Any) -> str:
        number = str(self._value(entity, "number", "")).strip()
        if number:
            return number

        entity_id = str(self._value(entity, "id", "")).strip()
        return f"ID-{entity_id[:8]}" if entity_id else "Без номера"

    def _score(self, entity: Any) -> int:
        try:
            return max(
                0,
                min(
                    100,
                    int(self._value(entity, "score", 0) or 0),
                ),
            )
        except (TypeError, ValueError):
            return 0

    def _created_sort_key(self, entity: Any) -> datetime:
        return self._created_at(entity) or datetime.min

    def _created_date(self, entity: Any) -> date | None:
        value = self._created_at(entity)
        return aware_dashboard_time(value).date() if value is not None else None

    def _created_at(self, entity: Any) -> datetime | None:
        value = self._value(entity, "created_at", None)
        return value if isinstance(value, datetime) else None

    @staticmethod
    def _parse_deadline(value: Any) -> date | None:
        text = str(value or "").strip()
        if not text:
            return None

        for pattern in (
            "%d.%m.%Y",
            "%Y-%m-%d",
            "%d.%m.%Y %H:%M",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                return datetime.strptime(text, pattern).date()
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value or 0))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @staticmethod
    def _format_money(value: Decimal) -> str:
        rounded = value.quantize(Decimal("1"))
        return f"{rounded:,.0f} ₽".replace(",", " ")

    @staticmethod
    def _value(entity: Any, name: str, default: Any) -> Any:
        try:
            return getattr(entity, name, default)
        except Exception:
            return default


class DashboardRefreshWorker(QObject):
    """Runs repository loading and snapshot building outside the UI thread."""

    completed = Signal(object, object)

    def __init__(
        self,
        task: Callable[[], DashboardSnapshot],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._task = task

    @Slot()
    def run(self) -> None:
        try:
            snapshot = self._task()
        except Exception as exc:
            self.completed.emit(None, exc)
            return

        self.completed.emit(snapshot, None)


class DashboardController(QObject):
    """Coordinates non-blocking Dashboard repository refreshes."""

    refresh_started = Signal()
    refresh_succeeded = Signal(object)
    refresh_failed = Signal(str)
    refresh_cycle_finished = Signal()
    tender_selected = Signal(str)

    DEFAULT_AUTO_REFRESH_MS = 5 * 60 * 1000

    def __init__(
        self,
        page: Any,
        *,
        repository: TenderRepositoryLike | None = None,
        business_repository: BusinessMetricsRepositoryLike | None = None,
        clock: Callable[[], datetime] | None = None,
        auto_refresh_ms: int = DEFAULT_AUTO_REFRESH_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.page = page
        self.repository = repository or TenderRepository()
        self.business_repository = business_repository or BusinessMetricsRepository()
        self.clock = clock or (lambda: datetime.now(APP_TIMEZONE))
        self.builder = DashboardSnapshotBuilder()

        self._number_to_id: dict[str, str] = {}
        self._started = False
        self._refreshing = False
        self._has_loaded_once = False
        self._preserve_content_during_refresh = False
        self._generation = 0
        self._last_snapshot: DashboardSnapshot | None = None

        self._refresh_thread: QThread | None = None
        self._refresh_worker: DashboardRefreshWorker | None = None

        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.setSingleShot(False)
        self._auto_refresh_timer.timeout.connect(self.refresh)
        self.set_auto_refresh_interval(auto_refresh_ms)

        application = QCoreApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.shutdown)

    @property
    def is_refreshing(self) -> bool:
        return self._refreshing

    @property
    def has_loaded_once(self) -> bool:
        return self._has_loaded_once

    @property
    def auto_refresh_interval(self) -> int:
        return self._auto_refresh_timer.interval()

    def set_auto_refresh_interval(self, milliseconds: int) -> None:
        """Configure periodic background refresh; zero disables it."""
        normalized = max(0, int(milliseconds))
        self._auto_refresh_timer.stop()

        if normalized == 0:
            self._auto_refresh_timer.setInterval(0)
            return

        self._auto_refresh_timer.setInterval(max(10_000, normalized))
        if self._started:
            self._auto_refresh_timer.start()

    def start(self) -> None:
        """Connect signals and schedule the first background refresh."""
        if self._started:
            return

        self._started = True
        self.page.viewmodel.refresh_requested.connect(self.refresh)
        self.page.tender_open_requested.connect(self._select_tender_by_number)

        if self._auto_refresh_timer.interval() > 0:
            self._auto_refresh_timer.start()

        if not bool(getattr(self.page, "demo_mode", False)):
            QTimer.singleShot(0, self.refresh)

    @Slot()
    def refresh(self) -> bool:
        """Start a repository refresh without blocking the Qt event loop."""
        if self._refreshing:
            return False
        if bool(getattr(self.page, "demo_mode", False)):
            return False

        self._refreshing = True
        self._preserve_content_during_refresh = self._has_loaded_once

        self.page.set_refreshing(
            True,
            preserve_content=self._preserve_content_during_refresh,
        )
        self.refresh_started.emit()

        repository = self.repository
        business_repository = self.business_repository
        builder = self.builder
        clock = self.clock
        self._generation += 1
        generation = self._generation
        previous = self._last_snapshot

        def load_snapshot() -> DashboardSnapshot:
            observed_at = aware_dashboard_time(clock())
            tender_error = ""
            business_error = ""
            try:
                dashboard_loader = getattr(
                    repository,
                    "list_for_dashboard",
                    None,
                )
                if callable(dashboard_loader):
                    entities = dashboard_loader(limit=None)
                else:
                    entities = repository.list()
            except Exception as exc:
                entities = []
                tender_error = f"Тендеры: {exc}"

            try:
                business = business_repository.summary(today=observed_at.date())
            except Exception as exc:
                business = None
                business_error = f"Workflow: {exc}"

            return builder.build(
                entities,
                now=observed_at,
                business=business,
                generation=generation,
                previous=previous,
                tender_error=tender_error,
                business_error=business_error,
            )

        thread = QThread(self)
        worker = DashboardRefreshWorker(load_snapshot)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.completed.connect(self._on_worker_completed)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._refresh_thread = thread
        self._refresh_worker = worker
        thread.start()
        return True

    @Slot(object, object)
    def _on_worker_completed(
        self,
        snapshot: DashboardSnapshot | None,
        error: Exception | None,
    ) -> None:
        if error is not None:
            self._handle_refresh_failure(error)
        elif snapshot is not None:
            try:
                self._apply_snapshot(snapshot)
            except Exception as exc:
                self._handle_refresh_failure(exc)
            else:
                has_source_errors = bool(snapshot.source_errors)
                self.page.set_refreshing(
                    False,
                    preserve_content=self._preserve_content_during_refresh,
                    successful=not has_source_errors,
                )
                self._last_snapshot = snapshot
                self._has_loaded_once = any(item.raw_value is not None for item in snapshot.kpis)
                if has_source_errors:
                    message = "Часть источников не обновлена: " + "; ".join(snapshot.source_errors)
                    self.page.set_partial_data(message)
                    self.refresh_failed.emit(message)
                else:
                    self.refresh_succeeded.emit(snapshot)

        worker = self._refresh_worker
        thread = self._refresh_thread

        if worker is not None:
            worker.deleteLater()
        if thread is not None and thread.isRunning():
            thread.quit()

    def _handle_refresh_failure(self, error: Exception) -> None:
        message = f"Не удалось обновить данные из локальной базы: {error}"

        self.page.set_refreshing(
            False,
            preserve_content=self._preserve_content_during_refresh,
            successful=False,
        )

        if self._has_loaded_once:
            self.page.set_partial_data(f"{message} Отображаются ранее загруженные данные.")
        else:
            self.page.show_error(
                message,
                action_text="Повторить",
                action_key="refresh_dashboard",
            )

        self.refresh_failed.emit(message)

    @Slot()
    def _on_thread_finished(self) -> None:
        self._refresh_worker = None
        self._refresh_thread = None
        self._refreshing = False
        self.refresh_cycle_finished.emit()

    def shutdown(self, wait_ms: int = 3000) -> None:
        """Stop timers and wait briefly for an active worker thread."""
        self._auto_refresh_timer.stop()

        thread = self._refresh_thread
        if thread is None or not thread.isRunning():
            return

        thread.requestInterruption()
        thread.quit()
        thread.wait(max(0, int(wait_ms)))

        self._refresh_worker = None
        self._refresh_thread = None
        self._refreshing = False

    def _apply_snapshot(
        self,
        snapshot: DashboardSnapshot,
    ) -> None:
        self._number_to_id = dict(snapshot.number_to_id)
        self.page.viewmodel.apply_snapshot(
            snapshot.kpis,
            recent_tenders=snapshot.tenders,
            ai_recommendations=snapshot.recommendations,
            loaded_at=snapshot.loaded_at,
        )
        self.page.set_activities(snapshot.activities)

        all_failed = all(item.state is DashboardKpiState.ERROR for item in snapshot.kpis)
        self.page.set_data_state(
            DataState.error("Источники Dashboard недоступны.") if all_failed else DataState.ready()
        )

    def _select_tender_by_number(self, number: str) -> None:
        entity_id = self._number_to_id.get(number)
        if entity_id:
            self.tender_selected.emit(entity_id)


__all__ = [
    "DashboardController",
    "DashboardRefreshWorker",
    "DashboardSnapshot",
    "DashboardSnapshotBuilder",
    "BusinessMetricsRepositoryLike",
    "TenderRepositoryLike",
]
