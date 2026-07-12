"""Unified Qt window for launching and monitoring Tender Collector."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.tenders.collector.models import (
    CollectionRunStatus,
    CollectorRunResult,
)
from app.tenders.collector.progress import (
    CollectorProgressEvent,
    CollectorProgressPhase,
)
from app.tenders.collector.provider_control import (
    ProviderDisplayState,
    ProviderUiState,
)
from app.tenders.search_profiles import TenderSearchProfile
from app.ui.theme.colors import ThemeName, get_palette


class TenderCollectorDialog(QDialog):
    """Select a profile and sources, then display live collection state."""

    start_requested = Signal(str, object)
    stop_requested = Signal()
    sources_requested = Signal()
    registry_requested = Signal()

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

        self._profiles: tuple[TenderSearchProfile, ...] = ()
        self._provider_states: tuple[ProviderDisplayState, ...] = ()
        self._provider_rows: dict[str, int] = {}
        self._completed_providers: set[str] = set()
        self._running = False

        self.setWindowTitle("Corteris Tender Collector")
        self.setModal(False)
        self.resize(1120, 760)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        heading = QFrame(self)
        heading.setObjectName("CollectorHeading")
        heading_layout = QVBoxLayout(heading)
        heading_layout.setContentsMargins(14, 12, 14, 12)
        title = QLabel("Автоматический сбор тендеров", heading)
        title.setObjectName("CollectorTitle")
        subtitle = QLabel(
            (
                "Поиск по включённым источникам, удаление дублей, "
                "определение изменений и сохранение в общий реестр."
            ),
            heading,
        )
        subtitle.setObjectName("CollectorSubtitle")
        subtitle.setWordWrap(True)
        heading_layout.addWidget(title)
        heading_layout.addWidget(subtitle)
        root.addWidget(heading)

        setup_frame = QFrame(self)
        setup_frame.setObjectName("CollectorSetupFrame")
        setup_layout = QGridLayout(setup_frame)
        setup_layout.setContentsMargins(14, 12, 14, 12)
        setup_layout.setHorizontalSpacing(10)
        setup_layout.setVerticalSpacing(8)

        setup_layout.addWidget(QLabel("Профиль поиска", setup_frame), 0, 0)
        self.profile_combo = QComboBox(setup_frame)
        self.profile_combo.setObjectName("CollectorProfileCombo")
        self.profile_combo.currentIndexChanged.connect(
            self._render_profile_summary
        )
        setup_layout.addWidget(self.profile_combo, 0, 1, 1, 2)

        self.sources_button = QPushButton(
            "Настроить источники…",
            setup_frame,
        )
        self.sources_button.clicked.connect(
            lambda _checked=False: self.sources_requested.emit()
        )
        setup_layout.addWidget(self.sources_button, 0, 3)

        self.profile_summary = QLabel("", setup_frame)
        self.profile_summary.setObjectName("CollectorProfileSummary")
        self.profile_summary.setWordWrap(True)
        setup_layout.addWidget(self.profile_summary, 1, 0, 1, 4)
        setup_layout.setColumnStretch(1, 1)
        root.addWidget(setup_frame)

        metrics = QHBoxLayout()
        metrics.setSpacing(10)
        self.new_value = self._add_metric(metrics, "Новые")
        self.changed_value = self._add_metric(metrics, "Изменённые")
        self.duplicate_value = self._add_metric(metrics, "Дубли")
        self.saved_value = self._add_metric(metrics, "Сохранено")
        root.addLayout(metrics)

        self.provider_table = QTableWidget(self)
        self.provider_table.setObjectName("CollectorProviderProgressTable")
        self.provider_table.setColumnCount(6)
        self.provider_table.setHorizontalHeaderLabels(
            (
                "Использовать",
                "Источник",
                "Состояние",
                "Найдено",
                "Время",
                "Ошибка / сообщение",
            )
        )
        self.provider_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.provider_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.provider_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.provider_table.setAlternatingRowColors(True)
        self.provider_table.verticalHeader().setVisible(False)
        header = self.provider_table.horizontalHeader()
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.provider_table, 1)

        progress_frame = QFrame(self)
        progress_frame.setObjectName("CollectorProgressFrame")
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(12, 10, 12, 10)
        progress_layout.setSpacing(6)
        self.progress_bar = QProgressBar(progress_frame)
        self.progress_bar.setObjectName("CollectorProgressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.status_label = QLabel(
            "Выберите профиль и источники.",
            progress_frame,
        )
        self.status_label.setObjectName("CollectorStatus")
        self.status_label.setWordWrap(True)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        root.addWidget(progress_frame)

        actions = QHBoxLayout()
        self.start_button = QPushButton("Запустить сбор", self)
        self.start_button.setObjectName("PrimaryActionButton")
        self.start_button.clicked.connect(self._request_start)
        self.stop_button = QPushButton("Остановить", self)
        self.stop_button.setObjectName("DangerActionButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(
            lambda _checked=False: self.stop_requested.emit()
        )
        self.registry_button = QPushButton("Открыть реестр", self)
        self.registry_button.clicked.connect(
            lambda _checked=False: self.registry_requested.emit()
        )
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        actions.addWidget(self.registry_button)
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

        self.apply_theme(self._theme)

    @property
    def running(self) -> bool:
        return self._running

    def set_profiles(
        self,
        profiles: Iterable[TenderSearchProfile],
        *,
        select_id: str = "",
    ) -> None:
        current_id = select_id or self.selected_profile_id()
        self._profiles = tuple(profile for profile in profiles if profile.enabled)
        self.profile_combo.blockSignals(True)
        try:
            self.profile_combo.clear()
            selected_index = 0
            for index, profile in enumerate(self._profiles):
                self.profile_combo.addItem(profile.name, profile.id)
                if profile.id == current_id:
                    selected_index = index
            if self._profiles:
                self.profile_combo.setCurrentIndex(selected_index)
        finally:
            self.profile_combo.blockSignals(False)
        self._render_profile_summary()
        self._update_start_enabled()

    def set_provider_states(
        self,
        states: Iterable[ProviderDisplayState],
        *,
        preserve_selection: bool = True,
    ) -> None:
        selected = set(self.selected_provider_ids()) if preserve_selection else set()
        self._provider_states = tuple(states)
        self._provider_rows.clear()
        self.provider_table.setRowCount(len(self._provider_states))

        for row, state in enumerate(self._provider_states):
            self._provider_rows[state.provider_id] = row
            use_item = QTableWidgetItem()
            flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable
            if state.enabled and not self._running:
                flags |= Qt.ItemFlag.ItemIsEnabled
            use_item.setFlags(flags)
            default_checked = state.enabled and (
                not selected or state.provider_id in selected
            )
            use_item.setCheckState(
                Qt.CheckState.Checked
                if default_checked
                else Qt.CheckState.Unchecked
            )
            use_item.setData(Qt.ItemDataRole.UserRole, state.provider_id)
            use_item.setToolTip(
                "Источник отключён в настройках."
                if not state.enabled
                else "Включить источник в текущий запуск."
            )
            self.provider_table.setItem(row, 0, use_item)
            self.provider_table.setItem(
                row,
                1,
                QTableWidgetItem(state.display_name),
            )
            status_item = QTableWidgetItem(state.status_text)
            status_item.setForeground(
                QColor(self._provider_ui_color(state.ui_state))
            )
            self.provider_table.setItem(row, 2, status_item)
            self.provider_table.setItem(row, 3, QTableWidgetItem("—"))
            self.provider_table.setItem(row, 4, QTableWidgetItem("—"))
            message = state.last_error or state.connection_mode
            message_item = QTableWidgetItem(message or "—")
            message_item.setToolTip(message)
            self.provider_table.setItem(row, 5, message_item)

        self._update_start_enabled()

    def selected_profile_id(self) -> str:
        value = self.profile_combo.currentData()
        return str(value or "").strip().casefold()

    def selected_provider_ids(self) -> tuple[str, ...]:
        result: list[str] = []
        for row in range(self.provider_table.rowCount()):
            item = self.provider_table.item(row, 0)
            if item is None or item.checkState() != Qt.CheckState.Checked:
                continue
            provider_id = str(
                item.data(Qt.ItemDataRole.UserRole) or ""
            ).strip().casefold()
            if provider_id:
                result.append(provider_id)
        return tuple(result)

    def begin_run(
        self,
        profile_name: str,
        provider_ids: Iterable[str],
    ) -> None:
        selected = {
            item.strip().casefold()
            for item in provider_ids
            if item.strip()
        }
        self._completed_providers.clear()
        self._set_metric_values(0, 0, 0, 0)
        self.progress_bar.setValue(1)
        self.set_status(
            f"Запуск сбора по профилю «{profile_name}»…"
        )
        for provider_id, row in self._provider_rows.items():
            if provider_id in selected:
                self._set_provider_row(
                    provider_id,
                    status="Ожидает запуска",
                    found="0",
                    elapsed="—",
                    message="",
                    color=self._palette().info,
                )
        self.set_running(True)

    def set_running(self, running: bool) -> None:
        self._running = bool(running)
        self.profile_combo.setEnabled(not self._running)
        self.sources_button.setEnabled(not self._running)
        self.start_button.setEnabled(not self._running)
        self.stop_button.setEnabled(self._running)
        for row in range(self.provider_table.rowCount()):
            item = self.provider_table.item(row, 0)
            if item is None:
                continue
            state = self._provider_states[row]
            flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable
            if state.enabled and not self._running:
                flags |= Qt.ItemFlag.ItemIsEnabled
            item.setFlags(flags)
        self._update_start_enabled()

    def mark_cancel_requested(self) -> None:
        self.stop_button.setEnabled(False)
        self.set_status(
            "Остановка запрошена. Завершаются активные запросы…"
        )

    def apply_progress(self, event: CollectorProgressEvent) -> None:
        if event.phase == CollectorProgressPhase.PREPARING:
            self.progress_bar.setValue(max(self.progress_bar.value(), 3))
        elif event.phase == CollectorProgressPhase.PROVIDER_QUEUED:
            self._set_provider_row(
                event.provider_id,
                status="В очереди",
                message=event.message,
                color=self._palette().info,
            )
        elif event.phase == CollectorProgressPhase.PROVIDER_RUNNING:
            self._set_provider_row(
                event.provider_id,
                status="Выполняется",
                message=event.message,
                color=self._palette().warning,
            )
        elif event.phase == CollectorProgressPhase.PROVIDER_COMPLETED:
            self._completed_providers.add(event.provider_id)
            self._set_provider_outcome(
                event.provider_id,
                event.provider_status,
                event.item_count,
                event.elapsed_ms,
                event.message,
            )
            total = max(1, event.total_providers)
            provider_progress = 5 + round(
                len(self._completed_providers) / total * 65
            )
            self.progress_bar.setValue(
                max(self.progress_bar.value(), provider_progress)
            )
        elif event.phase == CollectorProgressPhase.NORMALIZING:
            self.progress_bar.setValue(max(self.progress_bar.value(), 76))
        elif event.phase == CollectorProgressPhase.DEDUPLICATING:
            self.progress_bar.setValue(max(self.progress_bar.value(), 80))
        elif event.phase == CollectorProgressPhase.VERIFYING:
            self.progress_bar.setValue(max(self.progress_bar.value(), 86))
        elif event.phase == CollectorProgressPhase.CHECKING_FRESHNESS:
            self.progress_bar.setValue(max(self.progress_bar.value(), 89))
        elif event.phase == CollectorProgressPhase.RANKING:
            self.progress_bar.setValue(max(self.progress_bar.value(), 92))
        elif event.phase == CollectorProgressPhase.SAVING:
            self.progress_bar.setValue(max(self.progress_bar.value(), 95))
            self.duplicate_value.setText(str(event.duplicate_count))
        elif event.phase in {
            CollectorProgressPhase.COMPLETED,
            CollectorProgressPhase.CANCELLED,
        }:
            self.progress_bar.setValue(100)
            self._set_metric_values(
                event.new_count,
                event.changed_count,
                event.duplicate_count,
                event.merged_count,
            )
        elif event.phase == CollectorProgressPhase.FAILED:
            self.progress_bar.setValue(100)

        if event.message:
            self.set_status(
                event.message,
                error=event.phase == CollectorProgressPhase.FAILED,
            )

    def set_result(self, result: CollectorRunResult) -> None:
        persistence = result.persistence
        self._set_metric_values(
            persistence.new_count,
            persistence.changed_count,
            persistence.duplicate_count,
            persistence.merged_count,
        )
        for outcome in result.batch_result.outcomes:
            self._set_provider_outcome(
                outcome.provider_id,
                outcome.status.value,
                outcome.item_count,
                outcome.elapsed_ms,
                outcome.error_message or "; ".join(outcome.warnings),
            )

        self.progress_bar.setValue(100)
        if result.status == CollectionRunStatus.CANCELLED:
            message = (
                "Сбор остановлен. Уже полученные результаты сохранены: "
                f"{persistence.merged_count}."
            )
        elif result.status == CollectionRunStatus.PARTIAL:
            message = (
                "Сбор завершён с ошибками отдельных источников. "
                f"Новых: {persistence.new_count}, изменённых: "
                f"{persistence.changed_count}, дублей: "
                f"{persistence.duplicate_count}, требуется перепроверка: "
                f"{persistence.reverification_due_count}, рекомендовано: "
                f"{persistence.recommended_count}."
            )
        else:
            message = (
                "Сбор завершён. "
                f"Новых: {persistence.new_count}, изменённых: "
                f"{persistence.changed_count}, дублей: "
                f"{persistence.duplicate_count}, рекомендовано: "
                f"{persistence.recommended_count}."
            )
        self.set_status(message)
        self.set_running(False)

    def set_error(self, message: str) -> None:
        self.progress_bar.setValue(100)
        self.set_status(message, error=True)
        self.set_running(False)

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("error", bool(error))
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _request_start(self) -> None:
        profile_id = self.selected_profile_id()
        provider_ids = self.selected_provider_ids()
        if not profile_id:
            self.set_status("Не выбран профиль поиска.", error=True)
            return
        if not provider_ids:
            self.set_status(
                "Выберите хотя бы один включённый источник.",
                error=True,
            )
            return
        self.start_requested.emit(profile_id, provider_ids)

    def _render_profile_summary(self, _index: int = -1) -> None:
        profile = self._selected_profile()
        if profile is None:
            self.profile_summary.setText("Нет доступных профилей поиска.")
            return
        date_from = (
            (date.today() - timedelta(days=profile.lookback_days)).strftime(
                "%d.%m.%Y"
            )
            if profile.lookback_days is not None
            else "без ограничения"
        )
        keywords = ", ".join(profile.keywords[:6])
        if len(profile.keywords) > 6:
            keywords += "…"
        laws = ", ".join(profile.laws) or "все"
        self.profile_summary.setText(
            f"Ключевые слова: {keywords or 'по направлениям профиля'} · "
            f"Законы: {laws} · Публикация с: {date_from} · "
            f"Лимит источника: {profile.page_size}"
        )

    def _selected_profile(self) -> TenderSearchProfile | None:
        profile_id = self.selected_profile_id()
        for profile in self._profiles:
            if profile.id == profile_id:
                return profile
        return None

    def _set_provider_outcome(
        self,
        provider_id: str,
        status: str,
        item_count: int,
        elapsed_ms: int,
        message: str,
    ) -> None:
        labels = {
            "success": ("Успешно", self._palette().success),
            "empty": ("Нет результатов", self._palette().neutral),
            "not_configured": ("Не настроен", self._palette().warning),
            "unsupported": ("Не поддерживается", self._palette().warning),
            "failed": ("Ошибка", self._palette().danger),
            "timed_out": ("Тайм-аут", self._palette().danger),
            "cancelled": ("Остановлен", self._palette().neutral),
            "skipped": ("Пропущен", self._palette().neutral),
            "circuit_open": (
                "Временно отключён",
                self._palette().warning,
            ),
        }
        label, color = labels.get(
            status,
            (status or "Завершён", self._palette().info),
        )
        self._set_provider_row(
            provider_id,
            status=label,
            found=str(max(0, item_count)),
            elapsed=(
                f"{elapsed_ms / 1000:.1f} с"
                if elapsed_ms >= 1000
                else f"{elapsed_ms} мс"
            ),
            message=message,
            color=color,
        )

    def _set_provider_row(
        self,
        provider_id: str,
        *,
        status: str | None = None,
        found: str | None = None,
        elapsed: str | None = None,
        message: str | None = None,
        color: str | None = None,
    ) -> None:
        row = self._provider_rows.get(provider_id.strip().casefold())
        if row is None:
            return
        if status is not None:
            item = self.provider_table.item(row, 2)
            item.setText(status)
            if color:
                item.setForeground(QColor(color))
        if found is not None:
            self.provider_table.item(row, 3).setText(found)
        if elapsed is not None:
            self.provider_table.item(row, 4).setText(elapsed)
        if message is not None:
            item = self.provider_table.item(row, 5)
            item.setText(message or "—")
            item.setToolTip(message)

    def _set_metric_values(
        self,
        new_count: int,
        changed_count: int,
        duplicate_count: int,
        saved_count: int,
    ) -> None:
        self.new_value.setText(str(max(0, new_count)))
        self.changed_value.setText(str(max(0, changed_count)))
        self.duplicate_value.setText(str(max(0, duplicate_count)))
        self.saved_value.setText(str(max(0, saved_count)))

    def _add_metric(self, layout: QHBoxLayout, title: str) -> QLabel:
        frame = QFrame(self)
        frame.setObjectName("CollectorMetricCard")
        column = QVBoxLayout(frame)
        column.setContentsMargins(12, 9, 12, 9)
        value = QLabel("0", frame)
        value.setObjectName("CollectorMetricValue")
        caption = QLabel(title, frame)
        caption.setObjectName("CollectorMetricCaption")
        column.addWidget(value)
        column.addWidget(caption)
        layout.addWidget(frame, 1)
        return value

    def _update_start_enabled(self) -> None:
        if self._running:
            self.start_button.setEnabled(False)
            return
        self.start_button.setEnabled(
            bool(self._profiles)
            and any(state.enabled for state in self._provider_states)
        )

    def _provider_ui_color(self, state: ProviderUiState) -> str:
        palette = self._palette()
        return {
            ProviderUiState.WORKING: palette.success,
            ProviderUiState.LIMITED: palette.warning,
            ProviderUiState.ERROR: palette.danger,
            ProviderUiState.DISABLED: palette.neutral,
            ProviderUiState.NOT_CONFIGURED: palette.warning,
            ProviderUiState.UNKNOWN: palette.info,
            ProviderUiState.UNVERIFIED: palette.info,
        }[state]

    def _palette(self):
        return get_palette(self._theme)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = self._palette()
        self.setStyleSheet(
            f"""
            QDialog {{
                color: {palette.text_primary};
                background-color: {palette.app_background};
            }}
            QFrame#CollectorHeading,
            QFrame#CollectorSetupFrame,
            QFrame#CollectorProgressFrame,
            QFrame#CollectorMetricCard {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_default};
                border-radius: 9px;
            }}
            QLabel#CollectorTitle {{
                color: {palette.text_primary};
                font-size: 21px;
                font-weight: 700;
            }}
            QLabel#CollectorSubtitle,
            QLabel#CollectorProfileSummary,
            QLabel#CollectorMetricCaption,
            QLabel#CollectorStatus {{
                color: {palette.text_secondary};
            }}
            QLabel#CollectorStatus[error="true"] {{
                color: {palette.danger};
            }}
            QLabel#CollectorMetricValue {{
                color: {palette.brand_accent};
                font-size: 24px;
                font-weight: 700;
            }}
            QComboBox {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                min-height: 31px;
                padding: 3px 8px;
            }}
            QTableWidget#CollectorProviderProgressTable {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                alternate-background-color: {palette.panel_background};
                border: 1px solid {palette.border_default};
                gridline-color: {palette.divider};
                selection-background-color: {palette.selected_background};
                selection-color: {palette.text_primary};
            }}
            QHeaderView::section {{
                color: {palette.text_secondary};
                background-color: {palette.elevated_background};
                border: none;
                border-right: 1px solid {palette.divider};
                border-bottom: 1px solid {palette.divider};
                padding: 7px;
                font-weight: 600;
            }}
            QProgressBar {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 6px;
                min-height: 19px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {palette.brand_primary};
                border-radius: 5px;
            }}
            QPushButton {{
                min-height: 31px;
                color: {palette.text_primary};
                background-color: {palette.elevated_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 4px 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {palette.hover_background};
            }}
            QPushButton:disabled {{
                color: {palette.text_disabled};
                background-color: {palette.neutral_background};
            }}
            QPushButton#PrimaryActionButton {{
                color: {palette.text_on_brand};
                background-color: {palette.brand_primary};
                border-color: {palette.brand_primary};
            }}
            QPushButton#DangerActionButton {{
                color: {palette.text_on_danger};
                background-color: {palette.danger};
                border-color: {palette.danger};
            }}
            """
        )


__all__ = ["TenderCollectorDialog"]
