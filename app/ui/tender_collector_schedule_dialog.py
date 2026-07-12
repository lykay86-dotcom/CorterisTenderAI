"""Qt dialog for automatic Tender Collector scheduling."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from app.tenders.collector.provider_control import (
    ProviderDisplayState,
)
from app.tenders.collector.scheduler import (
    CollectorScheduleFrequency,
    CollectorScheduleSettings,
    CollectorScheduleState,
)
from app.tenders.search_profiles import TenderSearchProfile
from app.ui.theme.colors import ThemeName, get_palette


class TenderCollectorScheduleDialog(QDialog):
    """Edit the persistent in-process collector schedule."""

    save_requested = Signal(object)
    run_now_requested = Signal(str, object)
    notifications_requested = Signal()

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        try:
            self._theme = ThemeName(theme)
        except (TypeError, ValueError, AttributeError):
            self._theme = ThemeName.DARK

        self.setWindowTitle(
            "Corteris Tender Collector — планировщик"
        )
        self.resize(820, 690)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        title = QLabel(
            "Автоматический поиск тендеров",
            self,
        )
        title.setObjectName("ScheduleTitle")
        subtitle = QLabel(
            (
                "Планировщик работает, пока приложение "
                "CorterisTenderAI запущено. Второй сбор "
                "не запускается поверх уже выполняющегося."
            ),
            self,
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("ScheduleSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        form_frame = QFrame(self)
        form_frame.setObjectName("ScheduleFrame")
        form = QFormLayout(form_frame)
        form.setContentsMargins(14, 12, 14, 12)
        form.setSpacing(10)

        self.enabled = QCheckBox(
            "Включить автоматический запуск",
            form_frame,
        )
        form.addRow("", self.enabled)

        self.profile = QComboBox(form_frame)
        self.profile.setObjectName("ScheduleProfile")
        form.addRow("Поисковый профиль:", self.profile)

        self.frequency = QComboBox(form_frame)
        self.frequency.addItem(
            "Каждые 30 минут",
            CollectorScheduleFrequency.EVERY_30_MINUTES,
        )
        self.frequency.addItem(
            "Каждый час",
            CollectorScheduleFrequency.HOURLY,
        )
        self.frequency.addItem(
            "Каждые 3 часа",
            CollectorScheduleFrequency.EVERY_3_HOURS,
        )
        self.frequency.addItem(
            "Один раз в день",
            CollectorScheduleFrequency.DAILY,
        )
        form.addRow("Периодичность:", self.frequency)

        self.daily_time = QTimeEdit(
            QTime(9, 0),
            form_frame,
        )
        self.daily_time.setDisplayFormat("HH:mm")
        form.addRow("Время ежедневного запуска:", self.daily_time)

        self.run_on_startup = QCheckBox(
            "Запускать один раз при старте программы",
            form_frame,
        )
        form.addRow("", self.run_on_startup)
        root.addWidget(form_frame)

        sources_title = QLabel(
            "Источники для планового запуска",
            self,
        )
        sources_title.setObjectName("ScheduleSectionTitle")
        root.addWidget(sources_title)

        self.sources = QTableWidget(self)
        self.sources.setColumnCount(3)
        self.sources.setHorizontalHeaderLabels(
            ("Вкл.", "Источник", "Состояние")
        )
        self.sources.verticalHeader().setVisible(False)
        self.sources.horizontalHeader().setStretchLastSection(
            True
        )
        self.sources.setMinimumHeight(190)
        root.addWidget(self.sources, 1)

        notifications_frame = QFrame(self)
        notifications_frame.setObjectName("ScheduleFrame")
        notifications_layout = QVBoxLayout(
            notifications_frame
        )
        notifications_layout.setContentsMargins(
            14,
            10,
            14,
            10,
        )
        self.notify_new = QCheckBox(
            "Уведомлять о новых тендерах",
            notifications_frame,
        )
        self.notify_changed = QCheckBox(
            "Уведомлять об изменённых тендерах",
            notifications_frame,
        )
        self.notify_failures = QCheckBox(
            "Уведомлять об ошибках и частичных запусках",
            notifications_frame,
        )
        notifications_layout.addWidget(self.notify_new)
        notifications_layout.addWidget(
            self.notify_changed
        )
        notifications_layout.addWidget(
            self.notify_failures
        )
        root.addWidget(notifications_frame)

        self.state_label = QLabel("", self)
        self.state_label.setObjectName("ScheduleState")
        self.state_label.setWordWrap(True)
        root.addWidget(self.state_label)

        actions = QHBoxLayout()
        self.save_button = QPushButton(
            "Сохранить расписание",
            self,
        )
        self.save_button.setObjectName(
            "SchedulePrimaryButton"
        )
        self.run_now_button = QPushButton(
            "Запустить сейчас",
            self,
        )
        self.notifications_button = QPushButton(
            "Уведомления",
            self,
        )
        actions.addWidget(self.save_button)
        actions.addWidget(self.run_now_button)
        actions.addWidget(self.notifications_button)
        actions.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).setText("Закрыть")
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        root.addLayout(actions)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("ScheduleStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.frequency.currentIndexChanged.connect(
            self._update_daily_time_state
        )
        self.enabled.toggled.connect(
            self._update_enabled_state
        )
        self.save_button.clicked.connect(
            self._emit_save
        )
        self.run_now_button.clicked.connect(
            self._emit_run_now
        )
        self.notifications_button.clicked.connect(
            self.notifications_requested.emit
        )

        self.apply_theme(self._theme)
        self._update_enabled_state()

    def set_configuration(
        self,
        settings: CollectorScheduleSettings,
        state: CollectorScheduleState,
        profiles: Iterable[TenderSearchProfile],
        providers: Iterable[ProviderDisplayState],
    ) -> None:
        self.profile.clear()
        for profile in profiles:
            if not profile.enabled:
                continue
            self.profile.addItem(profile.name, profile.id)
        selected_profile = self.profile.findData(
            settings.profile_id
        )
        if selected_profile >= 0:
            self.profile.setCurrentIndex(selected_profile)

        self.sources.setRowCount(0)
        selected_sources = set(settings.provider_ids)
        for provider in providers:
            row = self.sources.rowCount()
            self.sources.insertRow(row)
            checkbox = QTableWidgetItem()
            flags = (
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            if provider.enabled:
                flags |= Qt.ItemFlag.ItemIsUserCheckable
            checkbox.setFlags(flags)
            checked = (
                provider.provider_id in selected_sources
                or (
                    not selected_sources
                    and provider.enabled
                )
            )
            checkbox.setCheckState(
                Qt.CheckState.Checked
                if checked and provider.enabled
                else Qt.CheckState.Unchecked
            )
            checkbox.setData(
                Qt.ItemDataRole.UserRole,
                provider.provider_id,
            )
            self.sources.setItem(row, 0, checkbox)
            self.sources.setItem(
                row,
                1,
                QTableWidgetItem(provider.display_name),
            )
            self.sources.setItem(
                row,
                2,
                QTableWidgetItem(provider.status_text),
            )

        self.enabled.setChecked(settings.enabled)
        frequency_index = self.frequency.findData(
            settings.frequency
        )
        if frequency_index >= 0:
            self.frequency.setCurrentIndex(
                frequency_index
            )
        parsed_time = QTime.fromString(
            settings.daily_time,
            "HH:mm",
        )
        if parsed_time.isValid():
            self.daily_time.setTime(parsed_time)
        self.run_on_startup.setChecked(
            settings.run_on_startup
        )
        self.notify_new.setChecked(settings.notify_new)
        self.notify_changed.setChecked(
            settings.notify_changed
        )
        self.notify_failures.setChecked(
            settings.notify_failures
        )
        self.state_label.setText(
            _render_state(state)
        )
        self._update_enabled_state()

    def selected_provider_ids(self) -> tuple[str, ...]:
        result: list[str] = []
        for row in range(self.sources.rowCount()):
            item = self.sources.item(row, 0)
            if (
                item is not None
                and item.checkState()
                == Qt.CheckState.Checked
            ):
                provider_id = str(
                    item.data(
                        Qt.ItemDataRole.UserRole
                    )
                    or ""
                ).strip()
                if provider_id:
                    result.append(provider_id)
        return tuple(result)

    def build_settings(
        self,
    ) -> CollectorScheduleSettings:
        profile_id = str(
            self.profile.currentData() or ""
        )
        frequency = self.frequency.currentData()
        return CollectorScheduleSettings(
            enabled=self.enabled.isChecked(),
            profile_id=profile_id,
            provider_ids=self.selected_provider_ids(),
            frequency=frequency,
            daily_time=self.daily_time.time().toString(
                "HH:mm"
            ),
            run_on_startup=(
                self.run_on_startup.isChecked()
            ),
            notify_new=self.notify_new.isChecked(),
            notify_changed=(
                self.notify_changed.isChecked()
            ),
            notify_failures=(
                self.notify_failures.isChecked()
            ),
        )

    def set_status(
        self,
        message: str,
        *,
        error: bool = False,
    ) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("error", error)
        self.status_label.style().unpolish(
            self.status_label
        )
        self.status_label.style().polish(
            self.status_label
        )

    def _emit_save(self) -> None:
        try:
            settings = self.build_settings()
        except ValueError as exc:
            self.set_status(str(exc), error=True)
            return
        self.save_requested.emit(settings)

    def _emit_run_now(self) -> None:
        profile_id = str(
            self.profile.currentData() or ""
        ).strip()
        providers = self.selected_provider_ids()
        if not profile_id:
            self.set_status(
                "Выберите поисковый профиль.",
                error=True,
            )
            return
        if not providers:
            self.set_status(
                "Выберите хотя бы один включённый источник.",
                error=True,
            )
            return
        self.run_now_requested.emit(
            profile_id,
            providers,
        )

    def _update_daily_time_state(self) -> None:
        self.daily_time.setEnabled(
            self.frequency.currentData()
            == CollectorScheduleFrequency.DAILY
            and self.enabled.isChecked()
        )

    def _update_enabled_state(self) -> None:
        enabled = self.enabled.isChecked()
        self.profile.setEnabled(enabled)
        self.frequency.setEnabled(enabled)
        self.sources.setEnabled(enabled)
        self.run_on_startup.setEnabled(enabled)
        self.notify_new.setEnabled(enabled)
        self.notify_changed.setEnabled(enabled)
        self.notify_failures.setEnabled(enabled)
        self._update_daily_time_state()

    def apply_theme(
        self,
        theme: ThemeName | str,
    ) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"""
            QDialog {{
                color: {palette.text_primary};
                background-color: {palette.app_background};
            }}
            QLabel#ScheduleTitle {{
                font-size: 21px;
                font-weight: 700;
            }}
            QLabel#ScheduleSubtitle,
            QLabel#ScheduleState,
            QLabel#ScheduleStatus {{
                color: {palette.text_secondary};
            }}
            QLabel#ScheduleStatus[error="true"] {{
                color: {palette.danger};
            }}
            QLabel#ScheduleSectionTitle {{
                font-weight: 700;
            }}
            QFrame#ScheduleFrame {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_default};
                border-radius: 8px;
            }}
            QComboBox, QTimeEdit, QTableWidget {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 6px;
                padding: 4px;
            }}
            QPushButton {{
                min-height: 31px;
                color: {palette.text_primary};
                background-color: {palette.elevated_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 4px 10px;
                font-weight: 600;
            }}
            QPushButton#SchedulePrimaryButton {{
                color: {palette.text_on_brand};
                background-color: {palette.brand_primary};
                border-color: {palette.brand_primary};
            }}
            """
        )


def _render_state(
    state: CollectorScheduleState,
) -> str:
    return (
        f"Следующий запуск: "
        f"{_format_time(state.next_run_at)}   ·   "
        f"Последний запуск: "
        f"{_format_time(state.last_started_at)}   ·   "
        f"Последнее завершение: "
        f"{_format_time(state.last_completed_at)}   ·   "
        f"Статус: {state.last_status}"
        + (
            f"\nПоследняя ошибка: {state.last_error}"
            if state.last_error
            else ""
        )
    )


def _format_time(value: str) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return value
    return parsed.astimezone().strftime(
        "%d.%m.%Y %H:%M"
    )


__all__ = ["TenderCollectorScheduleDialog"]
