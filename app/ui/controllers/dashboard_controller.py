"""Controller that connects Dashboard 1.0 to real tender data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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

from app.repositories.tenders import TenderRepository
from app.ui.dashboard.activity_feed import (
    ActivityEntry,
    ActivityTone,
)
from app.ui.dashboard.data_state import DataState
from app.ui.viewmodels.dashboard_viewmodel import (
    AiRecommendation,
    DashboardKpi,
    RecentTender,
)


class TenderRepositoryLike(Protocol):
    """Minimum repository contract required by DashboardController."""

    def list(self) -> Sequence[Any]:
        ...


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """View-ready Dashboard data built from repository entities."""

    kpis: tuple[DashboardKpi, ...]
    tenders: tuple[RecentTender, ...]
    recommendations: tuple[AiRecommendation, ...]
    activities: tuple[ActivityEntry, ...]
    number_to_id: dict[str, str]
    loaded_at: datetime


class DashboardSnapshotBuilder:
    """Maps ORM tender entities to stable Dashboard view models."""

    RECOMMENDED_SCORE = 80
    ATTENTION_DAYS = 3
    RECENT_LIMIT = 8

    PROPOSAL_STATUS_WORDS = (
        "кп",
        "коммерческ",
        "предложен",
        "подготовка заявки",
    )
    PROJECT_STATUS_WORDS = (
        "побед",
        "контракт",
        "исполн",
        "монтаж",
        "проект",
        "в работе",
    )
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
    ) -> DashboardSnapshot:
        loaded_at = now or datetime.now()
        rows = list(entities)
        sorted_rows = sorted(
            rows,
            key=self._created_sort_key,
            reverse=True,
        )

        recent = tuple(
            self._to_recent_tender(entity)
            for entity in sorted_rows[: self.RECENT_LIMIT]
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
        new_today = sum(
            1
            for entity in rows
            if self._created_date(entity) == today
        )
        recommended = [
            entity
            for entity in rows
            if self._score(entity) >= self.RECOMMENDED_SCORE
        ]
        attention = [
            entity
            for entity in rows
            if self._requires_attention(entity, today)
        ]
        proposal_count = sum(
            self._status_contains(entity, self.PROPOSAL_STATUS_WORDS)
            for entity in rows
        )
        project_count = sum(
            self._status_contains(entity, self.PROJECT_STATUS_WORDS)
            for entity in rows
        )
        profit, profit_sources = self._potential_profit(rows)

        kpis = self._build_kpis(
            profit=profit,
            profit_sources=profit_sources,
            new_today=new_today,
            recommended=len(recommended),
            proposals=proposal_count,
            projects=project_count,
            attention=len(attention),
        )
        recommendations = self._build_recommendations(
            rows,
            attention=attention,
        )
        activities = self._build_activities(
            sorted_rows,
            loaded_at=loaded_at,
        )

        return DashboardSnapshot(
            kpis=kpis,
            tenders=recent,
            recommendations=recommendations,
            activities=activities,
            number_to_id=number_to_id,
            loaded_at=loaded_at,
        )

    def _build_kpis(
        self,
        *,
        profit: Decimal,
        profit_sources: int,
        new_today: int,
        recommended: int,
        proposals: int,
        projects: int,
        attention: int,
    ) -> tuple[DashboardKpi, ...]:
        profit_trend = (
            f"По {profit_sources} проанализированным тендерам"
            if profit_sources
            else "Нет сохранённых расчётов прибыли"
        )
        return (
            DashboardKpi(
                key="potential_profit",
                title="Потенциальная прибыль",
                value=self._format_money(profit),
                trend=profit_trend,
                tone="success" if profit > 0 else "info",
                icon_text="₽",
            ),
            DashboardKpi(
                key="new_tenders",
                title="Новые тендеры",
                value=str(new_today),
                trend="Добавлены сегодня",
                tone="info",
                icon_text="T",
            ),
            DashboardKpi(
                key="recommended",
                title="AI рекомендует",
                value=str(recommended),
                trend=f"AI Score от {self.RECOMMENDED_SCORE}",
                tone="success",
                icon_text="AI",
            ),
            DashboardKpi(
                key="proposals_in_work",
                title="КП в работе",
                value=str(proposals),
                trend=(
                    "По статусам тендеров"
                    if proposals
                    else "Активные КП не найдены"
                ),
                tone="warning" if proposals else "default",
                icon_text="КП",
            ),
            DashboardKpi(
                key="active_projects",
                title="Активные проекты",
                value=str(projects),
                trend=(
                    "Контракты и проекты в работе"
                    if projects
                    else "Активные проекты не найдены"
                ),
                tone="info",
                icon_text="P",
            ),
            DashboardKpi(
                key="attention",
                title="Требуют внимания",
                value=str(attention),
                trend=(
                    f"Срок до {self.ATTENTION_DAYS} дней или риск"
                    if attention
                    else "Срочных рисков не найдено"
                ),
                tone="warning",
                icon_text="!",
            ),
        )

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
            severity = (
                "success"
                if score >= self.RECOMMENDED_SCORE
                else "info"
            )
            recommendations.append(
                AiRecommendation(
                    title="Приоритетный тендер",
                    description=(
                        f"{number} — {title}. AI Score: {score}/100."
                    ),
                    severity=severity,
                    action_text="Открыть тендер",
                )
            )

        if attention:
            nearest = min(
                attention,
                key=lambda row: (
                    self._days_to_deadline(row, date.today())
                    if self._days_to_deadline(row, date.today())
                    is not None
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
            description = str(
                self._value(entity, "title", "Тендер без названия")
            )
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
            nmck=self._format_money(
                self._decimal(self._value(entity, "nmck", 0))
            ),
            status=str(self._value(entity, "status", "Новый")),
            platform=str(
                self._value(entity, "platform", "Ручной импорт")
            ),
        )

    def _potential_profit(
        self,
        rows: Sequence[Any],
    ) -> tuple[Decimal, int]:
        total = Decimal("0")
        sources = 0

        for entity in rows:
            analyses = self._value(entity, "analyses", ()) or ()
            if not analyses:
                continue

            latest = max(
                analyses,
                key=lambda analysis: (
                    self._created_at(analysis) or datetime.min
                ),
            )
            amount = self._decimal(
                self._value(latest, "estimated_profit", 0)
            )
            if amount > 0:
                total += amount
                sources += 1

        return total, sources

    def _requires_attention(
        self,
        entity: Any,
        today: date,
    ) -> bool:
        days = self._days_to_deadline(entity, today)
        deadline_risk = (
            days is not None
            and 0 <= days <= self.ATTENTION_DAYS
        )
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
        deadline = self._parse_deadline(
            self._value(entity, "deadline", "")
        )
        if deadline is None:
            return None
        return (deadline - today).days

    def _status_contains(
        self,
        entity: Any,
        words: Sequence[str],
    ) -> int:
        status = str(
            self._value(entity, "status", "")
        ).strip().lower()
        return int(any(word in status for word in words))

    def _display_number(self, entity: Any) -> str:
        number = str(
            self._value(entity, "number", "")
        ).strip()
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
        return value.date() if value is not None else None

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
            return datetime.fromisoformat(
                text.replace("Z", "+00:00")
            ).date()
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
        clock: Callable[[], datetime] = datetime.now,
        auto_refresh_ms: int = DEFAULT_AUTO_REFRESH_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.page = page
        self.repository = repository or TenderRepository()
        self.clock = clock
        self.builder = DashboardSnapshotBuilder()

        self._number_to_id: dict[str, str] = {}
        self._started = False
        self._refreshing = False
        self._has_loaded_once = False
        self._preserve_content_during_refresh = False

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
        self.page.tender_open_requested.connect(
            self._select_tender_by_number
        )

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
        builder = self.builder
        clock = self.clock

        def load_snapshot() -> DashboardSnapshot:
            dashboard_loader = getattr(
                repository,
                "list_for_dashboard",
                None,
            )
            if callable(dashboard_loader):
                entities = dashboard_loader(limit=100)
            else:
                entities = repository.list()

            return builder.build(
                entities,
                now=clock(),
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
                self.page.set_refreshing(
                    False,
                    preserve_content=self._preserve_content_during_refresh,
                    successful=True,
                )
                self._has_loaded_once = True
                self.refresh_succeeded.emit(snapshot)

        worker = self._refresh_worker
        thread = self._refresh_thread

        if worker is not None:
            worker.deleteLater()
        if thread is not None and thread.isRunning():
            thread.quit()

    def _handle_refresh_failure(self, error: Exception) -> None:
        message = (
            "Не удалось обновить данные из локальной базы: "
            f"{error}"
        )

        self.page.set_refreshing(
            False,
            preserve_content=self._preserve_content_during_refresh,
            successful=False,
        )

        if self._has_loaded_once:
            self.page.set_partial_data(
                f"{message} Отображаются ранее загруженные данные."
            )
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

        for kpi in snapshot.kpis:
            self.page.viewmodel.set_kpi(
                kpi.key,
                value=kpi.value,
                trend=kpi.trend,
                tone=kpi.tone,
                title=kpi.title,
                icon_text=kpi.icon_text,
            )

        self.page.viewmodel.set_recent_tenders(snapshot.tenders)
        self.page.viewmodel.set_ai_recommendations(
            snapshot.recommendations
        )
        self.page.set_activities(snapshot.activities)

        self.page.set_data_state(
            DataState.ready()
            if snapshot.tenders
            else DataState.empty(
                "В локальной базе пока нет тендеров."
            )
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
    "TenderRepositoryLike",
]
