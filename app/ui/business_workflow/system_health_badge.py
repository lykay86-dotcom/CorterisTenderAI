"""Compact system health indicator for page headers."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QWidget

from app.core.system_health import (
    SystemHealthSeverity,
    SystemHealthSnapshot,
)
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography
from app.ui.theme.tokens import BorderWidth, DESIGN_TOKENS, Radius, Spacing


class SystemHealthBadge(QPushButton):
    """Clickable status badge with accessible text and tooltip."""

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self._severity = SystemHealthSeverity.INFO
        self._busy = True
        self._snapshot: SystemHealthSnapshot | None = None

        self.setObjectName("SystemHealthBadge")
        self.setMinimumHeight(DESIGN_TOKENS.controls["small"].height)
        self.setMinimumWidth(156)
        self.setCursor(self.cursor())
        self.setToolTip("Открыть центр состояния системы")
        self.set_busy(True)
        self.apply_theme(self._theme)

    @property
    def severity(self) -> SystemHealthSeverity:
        return self._severity

    @property
    def snapshot(self) -> SystemHealthSnapshot | None:
        return self._snapshot

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        if self._busy and self._snapshot is None:
            self.setText("◌  Проверка системы…")
            self.setToolTip("Выполняется фоновая проверка состояния")
        elif not self._busy and self._snapshot is None:
            self.setText("●  Состояние системы")
            self.setToolTip("Открыть центр состояния системы")
        self.apply_theme(self._theme)

    def set_snapshot(
        self,
        snapshot: SystemHealthSnapshot,
    ) -> None:
        self._snapshot = snapshot
        self._severity = snapshot.severity
        self._busy = False

        icon = {
            SystemHealthSeverity.SUCCESS: "●",
            SystemHealthSeverity.INFO: "●",
            SystemHealthSeverity.WARNING: "▲",
            SystemHealthSeverity.ERROR: "!",
        }[snapshot.severity]

        label = {
            SystemHealthSeverity.SUCCESS: "Система исправна",
            SystemHealthSeverity.INFO: "Система работает",
            SystemHealthSeverity.WARNING: "Требуется внимание",
            SystemHealthSeverity.ERROR: "Ошибка системы",
        }[snapshot.severity]

        self.setText(f"{icon}  {label}")
        self.setToolTip(self._tooltip(snapshot))
        self.apply_theme(self._theme)

    def set_error(self, message: str) -> None:
        self._busy = False
        self._severity = SystemHealthSeverity.WARNING
        self.setText("▲  Проверка недоступна")
        self.setToolTip(f"Не удалось обновить состояние системы:\n{message}")
        self.apply_theme(self._theme)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        foreground, background = {
            SystemHealthSeverity.SUCCESS: (
                palette.success,
                palette.success_background,
            ),
            SystemHealthSeverity.INFO: (
                palette.info,
                palette.info_background,
            ),
            SystemHealthSeverity.WARNING: (
                palette.warning,
                palette.warning_background,
            ),
            SystemHealthSeverity.ERROR: (
                palette.danger,
                palette.danger_background,
            ),
        }[self._severity]

        if self._busy:
            foreground = palette.info
            background = palette.info_background

        self.setStyleSheet(
            f"""
            QPushButton#SystemHealthBadge {{
                color: {foreground};
                background-color: {background};
                border: {int(BorderWidth.DEFAULT)}px solid {foreground};
                border-radius: {int(Radius.PILL)}px;
                padding: {int(Spacing.XS)}px {int(Spacing.M)}px;
                text-align: center;
                {Typography.BUTTON.css()}
            }}
            QPushButton#SystemHealthBadge:hover {{
                border-color: {palette.brand_primary};
                background-color: {palette.hover_background};
            }}
            QPushButton#SystemHealthBadge:pressed {{
                background-color: {palette.selected_background};
            }}
            QPushButton#SystemHealthBadge:focus {{
                border: {int(BorderWidth.FOCUS)}px solid {palette.focus_ring};
            }}
            """
        )

    @staticmethod
    def _tooltip(snapshot: SystemHealthSnapshot) -> str:
        lines = [
            snapshot.status_label,
            (f"База: {snapshot.database.status_label}; записей: {snapshot.database.record_count}"),
            (f"Копии: {snapshot.backup_valid} исправных, {snapshot.backup_invalid} повреждённых"),
            ("Автокопирование: " + ("включено" if snapshot.auto_backup_enabled else "отключено")),
        ]
        if snapshot.issues:
            lines.append("")
            lines.extend(f"• {issue}" for issue in snapshot.issues[:4])
        lines.append("")
        lines.append("Нажмите, чтобы открыть центр состояния.")
        return "\n".join(lines)


__all__ = ["SystemHealthBadge"]
