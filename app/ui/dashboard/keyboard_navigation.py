"""Keyboard navigation and shortcuts for Dashboard 1.0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget


@dataclass(frozen=True, slots=True)
class DashboardShortcutSpec:
    """One keyboard shortcut exposed by the Dashboard."""

    key: str
    sequence: str
    description: str


DEFAULT_DASHBOARD_SHORTCUTS: tuple[DashboardShortcutSpec, ...] = (
    DashboardShortcutSpec("find_tenders", "Ctrl+F", "Найти тендеры"),
    DashboardShortcutSpec(
        "analyze_documents",
        "Ctrl+A",
        "Запустить AI-анализ документов",
    ),
    DashboardShortcutSpec(
        "create_proposal",
        "Ctrl+K",
        "Создать коммерческое предложение",
    ),
    DashboardShortcutSpec(
        "create_estimate",
        "Ctrl+S",
        "Создать смету",
    ),
    DashboardShortcutSpec(
        "refresh_dashboard",
        "Ctrl+R",
        "Обновить рабочий стол",
    ),
    DashboardShortcutSpec(
        "focus_kpis",
        "Alt+1",
        "Перейти к показателям",
    ),
    DashboardShortcutSpec(
        "focus_tenders",
        "Alt+2",
        "Перейти к таблице тендеров",
    ),
    DashboardShortcutSpec(
        "focus_advisor",
        "Alt+3",
        "Перейти к AI Advisor",
    ),
    DashboardShortcutSpec(
        "focus_quick_actions",
        "Alt+4",
        "Перейти к быстрым действиям",
    ),
    DashboardShortcutSpec(
        "focus_activity",
        "Alt+5",
        "Перейти к ленте событий",
    ),
    DashboardShortcutSpec(
        "dismiss_status",
        "Escape",
        "Закрыть статусное сообщение",
    ),
)


class DashboardShortcutManager(QObject):
    """Owns QShortcut objects and emits semantic action keys."""

    action_requested = Signal(str)

    def __init__(
        self,
        host: QWidget,
        shortcuts: Iterable[DashboardShortcutSpec] = DEFAULT_DASHBOARD_SHORTCUTS,
    ) -> None:
        super().__init__(host)

        self._specs = tuple(shortcuts)
        self._shortcuts: dict[str, QShortcut] = {}

        seen_sequences: set[str] = set()
        for spec in self._specs:
            if spec.key in self._shortcuts:
                raise ValueError(f"Duplicate dashboard shortcut key: {spec.key}")

            normalized_sequence = QKeySequence(spec.sequence).toString()
            if normalized_sequence in seen_sequences:
                raise ValueError(f"Duplicate dashboard shortcut: {spec.sequence}")
            seen_sequences.add(normalized_sequence)

            shortcut = QShortcut(host)
            shortcut.setKey(QKeySequence(spec.sequence))
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(lambda key=spec.key: self.action_requested.emit(key))
            self._shortcuts[spec.key] = shortcut

    @property
    def specs(self) -> tuple[DashboardShortcutSpec, ...]:
        return self._specs

    def trigger(self, key: str) -> None:
        """Programmatically request an action."""
        if key not in self._shortcuts:
            raise KeyError(key)
        self.action_requested.emit(key)

    def set_enabled(self, key: str, enabled: bool) -> None:
        shortcut = self._shortcuts.get(key)
        if shortcut is None:
            raise KeyError(key)
        shortcut.setEnabled(bool(enabled))


__all__ = [
    "DEFAULT_DASHBOARD_SHORTCUTS",
    "DashboardShortcutManager",
    "DashboardShortcutSpec",
]
