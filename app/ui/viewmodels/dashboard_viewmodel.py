"""ViewModel главного рабочего стола Corteris Tender AI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True, slots=True)
class DashboardKpi:
    """Один показатель рабочего стола."""

    key: str
    title: str
    value: str
    trend: str = ""
    tone: str = "default"
    icon_text: str = ""


@dataclass(frozen=True, slots=True)
class RecentTender:
    """Краткая информация о последнем тендере."""

    number: str
    title: str
    customer: str
    deadline: str
    score: int | None = None
    recommendation: str = ""


@dataclass(frozen=True, slots=True)
class AiRecommendation:
    """Одна рекомендация встроенного AI-аналитика."""

    title: str
    description: str
    severity: str = "info"
    action_text: str = ""


@dataclass(slots=True)
class DashboardState:
    """Полное состояние рабочего стола."""

    kpis: dict[str, DashboardKpi] = field(default_factory=dict)
    recent_tenders: list[RecentTender] = field(default_factory=list)
    ai_recommendations: list[AiRecommendation] = field(default_factory=list)
    last_updated: datetime | None = None


class DashboardViewModel(QObject):
    """Хранит данные Dashboard и уведомляет страницу об изменениях."""

    state_changed = Signal(object)
    kpi_changed = Signal(str, object)
    recent_tenders_changed = Signal(object)
    ai_recommendations_changed = Signal(object)
    refresh_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = DashboardState()
        self._load_demo_state()

    @property
    def state(self) -> DashboardState:
        """Возвращает текущее состояние."""
        return self._state

    def _load_demo_state(self) -> None:
        """Создаёт стартовое состояние до подключения реальных сервисов."""
        self._state.kpis = {
            "potential_profit": DashboardKpi(
                key="potential_profit",
                title="Потенциальная прибыль",
                value="0 ₽",
                trend="Нет расчётов",
                tone="info",
                icon_text="₽",
            ),
            "new_tenders": DashboardKpi(
                key="new_tenders",
                title="Новые тендеры",
                value="0",
                trend="За сегодня",
                tone="info",
                icon_text="🔎",
            ),
            "recommended": DashboardKpi(
                key="recommended",
                title="Рекомендуется участвовать",
                value="0",
                trend="После анализа",
                tone="success",
                icon_text="★",
            ),
            "attention": DashboardKpi(
                key="attention",
                title="Требуют внимания",
                value="0",
                trend="Нет срочных",
                tone="warning",
                icon_text="!",
            ),
        }
        self._state.last_updated = datetime.now()

    def request_refresh(self) -> None:
        """Запрашивает обновление данных у будущего контроллера."""
        self.refresh_requested.emit()

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
        """Обновляет один показатель."""
        current = self._state.kpis.get(
            key,
            DashboardKpi(key=key, title=title or key, value=value),
        )

        updated = DashboardKpi(
            key=key,
            title=title if title is not None else current.title,
            value=value,
            trend=trend if trend is not None else current.trend,
            tone=tone if tone is not None else current.tone,
            icon_text=icon_text if icon_text is not None else current.icon_text,
        )
        self._state.kpis[key] = updated
        self._state.last_updated = datetime.now()
        self.kpi_changed.emit(key, updated)
        self.state_changed.emit(self._state)

    def set_recent_tenders(self, tenders: Iterable[RecentTender]) -> None:
        """Заменяет список последних тендеров."""
        self._state.recent_tenders = list(tenders)
        self._state.last_updated = datetime.now()
        self.recent_tenders_changed.emit(self._state.recent_tenders)
        self.state_changed.emit(self._state)

    def set_ai_recommendations(
        self,
        recommendations: Iterable[AiRecommendation],
    ) -> None:
        """Заменяет список AI-рекомендаций."""
        self._state.ai_recommendations = list(recommendations)
        self._state.last_updated = datetime.now()
        self.ai_recommendations_changed.emit(self._state.ai_recommendations)
        self.state_changed.emit(self._state)

    def clear(self) -> None:
        """Очищает динамические данные, сохраняя KPI-структуру."""
        self._state.recent_tenders.clear()
        self._state.ai_recommendations.clear()
        self._state.last_updated = datetime.now()
        self.recent_tenders_changed.emit([])
        self.ai_recommendations_changed.emit([])
        self.state_changed.emit(self._state)


__all__ = [
    "AiRecommendation",
    "DashboardKpi",
    "DashboardState",
    "DashboardViewModel",
    "RecentTender",
]
