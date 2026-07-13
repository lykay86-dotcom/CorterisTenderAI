"""ViewModel for Dashboard AI Advisor."""

from __future__ import annotations
from dataclasses import dataclass, field, replace
from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True, slots=True)
class AiAdvisorMetrics:
    new_tenders: int = 0
    recommended: int = 0
    attention: int = 0


@dataclass(frozen=True, slots=True)
class AiAdvisorFocus:
    title: str = "Запустите поиск тендеров, чтобы получить рекомендацию"
    number: str = ""
    amount: str = ""
    score: int | None = None


@dataclass(frozen=True, slots=True)
class AiAdvisorAction:
    text: str = "Найти тендеры"
    key: str = "find_tenders"
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class AiAdvisorState:
    status: str = "online"
    status_text: str = ""
    metrics: AiAdvisorMetrics = field(default_factory=AiAdvisorMetrics)
    focus: AiAdvisorFocus = field(default_factory=AiAdvisorFocus)
    reasons: tuple[str, ...] = ()
    warning: str = ""
    action: AiAdvisorAction = field(default_factory=AiAdvisorAction)


class AiAdvisorViewModel(QObject):
    state_changed = Signal(object)
    status_changed = Signal(str, str)
    metrics_changed = Signal(object)
    focus_changed = Signal(object)
    reasons_changed = Signal(object)
    warning_changed = Signal(str)
    action_changed = Signal(object)
    action_requested = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = AiAdvisorState()

    @property
    def state(self) -> AiAdvisorState:
        return self._state

    def set_status(self, status: str, text: str = "") -> None:
        self._state = replace(self._state, status=status, status_text=text)
        self.status_changed.emit(status, text)
        self.state_changed.emit(self._state)

    def set_metrics(self, *, new_tenders: int, recommended: int, attention: int) -> None:
        metrics = AiAdvisorMetrics(
            max(0, int(new_tenders)),
            max(0, int(recommended)),
            max(0, int(attention)),
        )
        self._state = replace(self._state, metrics=metrics)
        self.metrics_changed.emit(metrics)
        self.state_changed.emit(self._state)

    def set_focus(
        self,
        *,
        title: str,
        number: str = "",
        amount: str = "",
        score: int | None = None,
    ) -> None:
        normalized = None if score is None else max(0, min(int(score), 100))
        focus = AiAdvisorFocus(
            title.strip() or "Приоритетный тендер не выбран",
            number.strip(),
            amount.strip(),
            normalized,
        )
        self._state = replace(self._state, focus=focus)
        self.focus_changed.emit(focus)
        self.state_changed.emit(self._state)

    def set_reasons(self, reasons: list[str] | tuple[str, ...]) -> None:
        normalized = tuple(x.strip() for x in reasons if x and x.strip())[:4]
        self._state = replace(self._state, reasons=normalized)
        self.reasons_changed.emit(normalized)
        self.state_changed.emit(self._state)

    def set_warning(self, warning: str = "") -> None:
        normalized = warning.strip()
        self._state = replace(self._state, warning=normalized)
        self.warning_changed.emit(normalized)
        self.state_changed.emit(self._state)

    def set_action(self, *, text: str, key: str, enabled: bool = True) -> None:
        action = AiAdvisorAction(text.strip() or "Продолжить", key.strip(), bool(enabled))
        self._state = replace(self._state, action=action)
        self.action_changed.emit(action)
        self.state_changed.emit(self._state)

    def request_action(self) -> None:
        if self._state.action.enabled and self._state.action.key:
            self.action_requested.emit(self._state.action.key)

    def set_empty_state(self) -> None:
        self._state = AiAdvisorState()
        self.status_changed.emit(self._state.status, self._state.status_text)
        self.metrics_changed.emit(self._state.metrics)
        self.focus_changed.emit(self._state.focus)
        self.reasons_changed.emit(self._state.reasons)
        self.warning_changed.emit(self._state.warning)
        self.action_changed.emit(self._state.action)
        self.state_changed.emit(self._state)


__all__ = [
    "AiAdvisorAction",
    "AiAdvisorFocus",
    "AiAdvisorMetrics",
    "AiAdvisorState",
    "AiAdvisorViewModel",
]
