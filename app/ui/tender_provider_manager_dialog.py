"""Qt interface for enabling and checking tender sources."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable, Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.tenders.collector.provider_control import (
    ProviderDisplayState,
    ProviderUiState,
)
from app.tenders.collector.source_monitoring import (
    SourceAttentionLevel,
    SourceFreshness,
    SourceMonitoringSnapshot,
    SourceMonitoringState,
)
from app.tenders.collector.manual_provider_registration import (
    ManualProviderDraft,
    ManualProviderRegistration,
)
from app.tenders.collector.manual_provider_protocol import (
    ManualProviderAuthenticationKind,
    ManualProviderFtpsMode,
    ManualProviderPayloadFormat,
    ManualProviderProtocolDraft,
    ManualProviderProtocolFamily,
    ManualProviderProtocolPolicy,
    manual_provider_protocol_policies,
)
from app.tenders.collector.provider_settings import (
    ProviderConfiguration,
    ProviderSettingOrigin,
)
from app.tenders.collector.manual_adapter import (
    ManualAdapterDataFormat,
    ManualAdapterPreviewResult,
    ManualAdapterSpec,
    RecordSelectorSpec,
    SourceRequestSpec,
    create_manual_adapter_spec,
    parse_field_mapping_lines,
    parse_restricted_path,
)
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.tables import TableRevision, TableRole, TableRowId, TableState


class TenderProviderManagerDialog(QDialog):
    """Display source switches, health and explicit connection checks."""

    provider_enabled_changed = Signal(str, bool)
    provider_check_requested = Signal(str)
    provider_configuration_requested = Signal(str)
    provider_credentials_requested = Signal(str)
    manual_provider_add_requested = Signal()
    manual_provider_edit_requested = Signal(str)
    manual_provider_protocol_requested = Signal(str)
    manual_adapter_requested = Signal(str)
    check_all_requested = Signal()

    def __init__(
        self,
        states: Iterable[ProviderDisplayState] = (),
        *,
        monitoring_snapshot: SourceMonitoringSnapshot | None = None,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        try:
            self._theme = ThemeName(theme)
        except (ValueError, TypeError, AttributeError):
            self._theme = ThemeName.DARK

        self._states: tuple[ProviderDisplayState, ...] = ()
        self._monitoring: dict[str, SourceMonitoringState] = {
            item.provider_id: item
            for item in (monitoring_snapshot.sources if monitoring_snapshot is not None else ())
        }
        self._checking: set[str] = set()
        self._updating_table = False
        self._check_buttons: dict[str, QPushButton] = {}

        self.setWindowTitle("Corteris Tender Collector — источники")
        self.setModal(False)
        self.resize(1220, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        heading = QFrame(self)
        heading.setObjectName("ProviderHeading")
        heading_layout = QVBoxLayout(heading)
        heading_layout.setContentsMargins(14, 12, 14, 12)
        title = QLabel("Источники тендеров", heading)
        title.setObjectName("ProviderTitle")
        subtitle = QLabel(
            (
                "Включайте источники и проверяйте соединение вручную. "
                "Открытие окна не выполняет сетевых запросов."
            ),
            heading,
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("ProviderSubtitle")
        heading_layout.addWidget(title)
        heading_layout.addWidget(subtitle)
        root.addWidget(heading)

        self.table = QTableWidget(self)
        self.table.setObjectName("TenderProviderTable")
        self.table.setAccessibleName("Tender providers")
        self.table.setAccessibleDescription(
            "Provider status, availability and actions resolved by exact provider identity."
        )
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            (
                "Вкл.",
                "Подключение",
                "Сбор/circuit",
                "Checkpoint",
                "C19",
                "Источник",
                "Проверка",
                "Последний сбор",
                "Внимание",
            )
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            8,
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._render_selected_details)
        root.addWidget(self.table, 1)

        details_frame = QFrame(self)
        details_frame.setObjectName("ProviderDetailsFrame")
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(12, 10, 12, 10)
        details_title = QLabel(
            "Подробности выбранного источника",
            details_frame,
        )
        details_title.setObjectName("ProviderDetailsTitle")
        self.details = QTextBrowser(details_frame)
        self.details.setObjectName("ProviderDetails")
        self.details.setOpenExternalLinks(True)
        self.details.setMaximumHeight(170)
        details_layout.addWidget(details_title)
        details_layout.addWidget(self.details)
        root.addWidget(details_frame)

        actions = QHBoxLayout()
        self.add_manual_provider_button = QPushButton(
            "Добавить площадку вручную",
            self,
        )
        self.add_manual_provider_button.setObjectName("AddManualProviderButton")
        self.add_manual_provider_button.clicked.connect(self.manual_provider_add_requested.emit)
        self.edit_manual_provider_button = QPushButton(
            "Изменить регистрацию",
            self,
        )
        self.edit_manual_provider_button.setObjectName("EditManualProviderButton")
        self.edit_manual_provider_button.clicked.connect(
            lambda: self.manual_provider_edit_requested.emit(self.selected_provider_id())
        )
        self.manual_provider_protocol_button = QPushButton(
            "Настроить протокол",
            self,
        )
        self.manual_provider_protocol_button.setObjectName("ConfigureManualProviderProtocolButton")
        self.manual_provider_protocol_button.clicked.connect(
            lambda: self.manual_provider_protocol_requested.emit(self.selected_provider_id())
        )
        self.manual_adapter_button = QPushButton("Настроить адаптер", self)
        self.manual_adapter_button.setObjectName("ConfigureManualAdapterButton")
        self.manual_adapter_button.clicked.connect(
            lambda: self.manual_adapter_requested.emit(self.selected_provider_id())
        )
        self.configure_button = QPushButton("Настроить API", self)
        self.configure_button.setObjectName("ConfigureProviderButton")
        self.configure_button.clicked.connect(
            lambda: self.provider_configuration_requested.emit(self.selected_provider_id())
        )
        self.credentials_button = QPushButton("Управлять credential", self)
        self.credentials_button.setObjectName("ManageProviderCredentialButton")
        self.credentials_button.clicked.connect(
            lambda: self.provider_credentials_requested.emit(self.selected_provider_id())
        )
        self.check_all_button = QPushButton(
            "Проверить все включённые",
            self,
        )
        self.check_all_button.setObjectName("PrimaryActionButton")
        self.check_all_button.clicked.connect(self.check_all_requested.emit)
        self.refresh_button = QPushButton(
            "Обновить состояния",
            self,
        )
        actions.addWidget(self.add_manual_provider_button)
        actions.addWidget(self.edit_manual_provider_button)
        actions.addWidget(self.manual_provider_protocol_button)
        actions.addWidget(self.manual_adapter_button)
        actions.addWidget(self.configure_button)
        actions.addWidget(self.credentials_button)
        actions.addWidget(self.check_all_button)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        root.addLayout(actions)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("ProviderStatusMessage")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.apply_theme(self._theme)
        self.set_states(tuple(states))

    @property
    def states(self) -> tuple[ProviderDisplayState, ...]:
        return self._states

    def set_states(
        self,
        states: Iterable[ProviderDisplayState],
    ) -> None:
        selected_id = self.selected_provider_id()
        self._states = tuple(states)
        self._updating_table = True
        try:
            self.table.setRowCount(len(self._states))
            self._check_buttons.clear()
            for row, state in enumerate(self._states):
                self._populate_row(row, state)
        finally:
            self._updating_table = False

        selected_row = 0
        for row, state in enumerate(self._states):
            if state.provider_id == selected_id:
                selected_row = row
                break
        if self._states:
            self.table.selectRow(selected_row)
        self._render_selected_details()
        self._update_check_all_state()

    def set_monitoring_snapshot(self, snapshot: SourceMonitoringSnapshot) -> None:
        self._monitoring = {item.provider_id: item for item in snapshot.sources}
        self.set_states(self._states)

    def set_checking(
        self,
        provider_ids: Iterable[str],
        checking: bool,
    ) -> None:
        normalized = {item.strip().casefold() for item in provider_ids if item.strip()}
        if checking:
            self._checking.update(normalized)
        else:
            self._checking.difference_update(normalized)

        for provider_id, button in self._check_buttons.items():
            active = provider_id in self._checking
            state = self._state_by_id(provider_id)
            button.setEnabled(
                not active
                and state is not None
                and (state.enabled or state.registration_only)
                and state.health_check_available
            )
            button.setText(
                "Проверка…"
                if active
                else "Проверить подключение"
                if state is not None and state.registration_only
                else "Проверить"
            )
        self._update_check_all_state()

    def selected_provider_id(self) -> str:
        row = self.table.currentRow()
        if not 0 <= row < len(self._states):
            return ""
        return self._states[row].provider_id

    def set_status(
        self,
        message: str,
        *,
        error: bool = False,
    ) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("error", error)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _populate_row(
        self,
        row: int,
        state: ProviderDisplayState,
    ) -> None:
        enabled_item = QTableWidgetItem()
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if state.enabled_editable:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        enabled_item.setFlags(flags)
        enabled_item.setCheckState(
            Qt.CheckState.Checked if state.enabled else Qt.CheckState.Unchecked
        )
        enabled_item.setData(
            Qt.ItemDataRole.UserRole,
            state.provider_id,
        )
        self._set_common_row_roles(enabled_item, state)
        self.table.setItem(row, 0, enabled_item)

        monitoring = self._monitoring.get(state.provider_id)
        status_item = QTableWidgetItem(
            _connection_text(monitoring) if monitoring is not None else f"● {state.status_text}"
        )
        status_item.setForeground(
            QColor(
                self._attention_color(monitoring.attention)
                if monitoring is not None
                else self._status_color(state.ui_state)
            )
        )
        status_item.setData(
            Qt.ItemDataRole.UserRole,
            state.provider_id,
        )
        self._set_common_row_roles(status_item, state)
        status_item.setData(
            Qt.ItemDataRole.AccessibleTextRole,
            f"{state.display_name}: {state.status_text}",
        )
        self.table.setItem(row, 1, status_item)

        self.table.setItem(row, 2, QTableWidgetItem(_operational_text(monitoring)))
        self.table.setItem(row, 3, QTableWidgetItem(_checkpoint_text(monitoring)))
        self.table.setItem(row, 4, QTableWidgetItem(_verification_text(monitoring)))
        self.table.setItem(row, 5, QTableWidgetItem(state.display_name))
        last_collection = (
            monitoring.last_successful_collection_at.isoformat()
            if monitoring is not None and monitoring.last_successful_collection_at is not None
            else ""
        )
        self.table.setItem(row, 7, QTableWidgetItem(_format_timestamp(last_collection)))
        attention_item = QTableWidgetItem(_attention_text(monitoring))
        attention_item.setToolTip(
            "\n".join(reason.message for reason in monitoring.reasons)
            if monitoring is not None
            else ""
        )
        self.table.setItem(row, 8, attention_item)

        button = QPushButton(
            "Проверить подключение" if state.registration_only else "Проверить",
            self.table,
        )
        button.setObjectName(f"checkProvider_{state.provider_id}")
        button.setEnabled(
            (state.enabled or state.registration_only)
            and state.health_check_available
            and state.provider_id not in self._checking
        )
        button.clicked.connect(
            lambda _checked=False, provider_id=state.provider_id: (
                self.provider_check_requested.emit(provider_id)
            )
        )
        self._check_buttons[state.provider_id] = button
        self.table.setCellWidget(row, 6, button)

    @staticmethod
    def _set_common_row_roles(item: QTableWidgetItem, state: ProviderDisplayState) -> None:
        item.setData(TableRole.ROW_ID, TableRowId("provider", state.provider_id))
        item.setData(
            TableRole.ROW_REVISION,
            TableRevision(
                f"{state.provider_id}:{state.ui_state.value}:{int(state.enabled)}:"
                f"{state.last_checked_at or 'not_checked'}"
            ),
        )
        item.setData(TableRole.ACTION_IDS, ("check", "configure"))
        item.setData(
            TableRole.STATE,
            TableState.PARTIAL
            if state.ui_state in {ProviderUiState.LIMITED, ProviderUiState.ERROR}
            else TableState.READY,
        )

    def _on_item_changed(
        self,
        item: QTableWidgetItem,
    ) -> None:
        if self._updating_table or item.column() != 0:
            return
        provider_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not provider_id:
            return
        enabled = item.checkState() == Qt.CheckState.Checked
        self.provider_enabled_changed.emit(
            provider_id,
            enabled,
        )

    def _render_selected_details(self) -> None:
        provider_id = self.selected_provider_id()
        state = self._state_by_id(provider_id)
        if state is None:
            self.details.clear()
            self.configure_button.setEnabled(False)
            self.credentials_button.setEnabled(False)
            self.edit_manual_provider_button.setEnabled(False)
            self.manual_provider_protocol_button.setEnabled(False)
            self.manual_adapter_button.setEnabled(False)
            return

        self.configure_button.setEnabled(
            state.implementation_status == "commercial_access_pending"
            and state.configuration_editable
        )
        self.credentials_button.setEnabled(
            state.credential_available
            and (
                state.provider_id == "mos_supplier"
                or state.implementation_status == "commercial_access_pending"
            )
        )
        self.edit_manual_provider_button.setEnabled(state.registration_only)
        self.manual_provider_protocol_button.setEnabled(state.registration_only)
        self.manual_adapter_button.setEnabled(state.registration_only and state.protocol_configured)

        latency = f"{state.latency_ms} мс" if state.latency_ms is not None else "не измерена"
        configuration = "<br>".join(_escape_html(item) for item in state.configuration_details)
        monitoring = self._monitoring.get(state.provider_id)
        monitoring_details = _monitoring_details_html(monitoring)
        safe_error = "Ошибка скрыта безопасно." if state.last_error else "—"
        self.details.setHtml(
            (
                f"<b>{_escape_html(state.display_name)}</b><br>"
                f"ID: <code>{_escape_html(state.provider_id)}</code><br>"
                f"Состояние: {_escape_html(state.status_text)}<br>"
                f"Режим: {_escape_html(state.connection_mode)}<br>"
                f"Реализация: "
                f"{_escape_html(state.implementation_status)}<br>"
                f"Источник настройки: "
                f"{_escape_html(_origin_label(state.configuration_origin))}<br>"
                f"Credential: {_escape_html(state.credential_state.value if state.credential_state else 'не запрашивался')}<br>"
                f"Последняя проверка: "
                f"{_format_timestamp(state.last_checked_at)}<br>"
                f"Последний успех: "
                f"{_format_timestamp(state.last_success_at)}<br>"
                f"Задержка: {_escape_html(latency)}<br>"
                f"Последняя ошибка подключения: {_escape_html(safe_error)}<br>"
                f"{monitoring_details}<br><br>"
                f"{configuration}<br><br>"
                f'<a href="{_escape_html(state.homepage_url)}">'
                "Открыть сайт источника</a>"
            )
        )

    def _state_by_id(
        self,
        provider_id: str,
    ) -> ProviderDisplayState | None:
        for state in self._states:
            if state.provider_id == provider_id:
                return state
        return None

    def _update_check_all_state(self) -> None:
        enabled_count = sum(state.enabled for state in self._states)
        self.check_all_button.setEnabled(bool(enabled_count) and not self._checking)

    def _status_color(
        self,
        state: ProviderUiState,
    ) -> str:
        palette = get_palette(self._theme)
        return {
            ProviderUiState.WORKING: palette.success,
            ProviderUiState.LIMITED: palette.warning,
            ProviderUiState.ERROR: palette.danger,
            ProviderUiState.DISABLED: palette.neutral,
            ProviderUiState.NOT_CONFIGURED: palette.warning,
            ProviderUiState.UNKNOWN: palette.info,
            ProviderUiState.UNVERIFIED: palette.info,
        }[state]

    def _attention_color(self, level: SourceAttentionLevel) -> str:
        palette = get_palette(self._theme)
        return {
            SourceAttentionLevel.NONE: palette.success,
            SourceAttentionLevel.INFO: palette.info,
            SourceAttentionLevel.WARNING: palette.warning,
            SourceAttentionLevel.CRITICAL: palette.danger,
        }[level]

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
            QFrame#ProviderHeading,
            QFrame#ProviderDetailsFrame {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_default};
                border-radius: 9px;
            }}
            QLabel#ProviderTitle {{
                color: {palette.text_primary};
                font-size: 21px;
                font-weight: 700;
            }}
            QLabel#ProviderSubtitle,
            QLabel#ProviderStatusMessage {{
                color: {palette.text_secondary};
            }}
            QLabel#ProviderStatusMessage[error="true"] {{
                color: {palette.danger};
            }}
            QLabel#ProviderDetailsTitle {{
                color: {palette.text_primary};
                font-weight: 700;
            }}
            QTableWidget#TenderProviderTable {{
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
            QTextBrowser#ProviderDetails {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 6px;
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
            """
        )


class ManualProviderRegistrationDialog(QDialog):
    """Presentation-only editor for inert manual provider metadata."""

    def __init__(
        self,
        registration: ManualProviderRegistration | None = None,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._accepted_once = False
        self.setWindowTitle(
            "Изменить регистрацию площадки"
            if registration is not None
            else "Добавить площадку вручную"
        )
        self.setModal(True)
        self.setObjectName("ManualProviderRegistrationDialog")

        root = QVBoxLayout(self)
        notice = QLabel(
            "Сохраняются только декларативные metadata. "
            "Для запуска потребуется отдельный выбор протокола.",
            self,
        )
        notice.setObjectName("ManualProviderRegistrationNotice")
        notice.setWordWrap(True)
        root.addWidget(notice)

        form = QFormLayout()
        self.display_name_edit = QLineEdit(self)
        self.display_name_edit.setObjectName("ManualProviderDisplayName")
        self.display_name_edit.setAccessibleName("Название площадки")
        self.display_name_edit.setMaxLength(160)
        self.display_name_edit.setPlaceholderText("Название площадки")
        form.addRow("Название площадки", self.display_name_edit)

        self.homepage_url_edit = QLineEdit(self)
        self.homepage_url_edit.setObjectName("ManualProviderHomepageUrl")
        self.homepage_url_edit.setAccessibleName("Официальный сайт площадки")
        self.homepage_url_edit.setMaxLength(2048)
        self.homepage_url_edit.setPlaceholderText("https://example.ru")
        form.addRow("Официальный сайт", self.homepage_url_edit)

        self.endpoint_url_edit = QLineEdit(self)
        self.endpoint_url_edit.setObjectName("ManualProviderEndpointUrl")
        self.endpoint_url_edit.setAccessibleName("Endpoint metadata")
        self.endpoint_url_edit.setMaxLength(2048)
        self.endpoint_url_edit.setPlaceholderText("Необязательно")
        form.addRow("Endpoint metadata", self.endpoint_url_edit)
        root.addLayout(form)

        if registration is not None:
            self.display_name_edit.setText(registration.display_name)
            self.homepage_url_edit.setText(registration.homepage_url)
            self.endpoint_url_edit.setText(registration.endpoint_url)

        self.validation_label = QLabel("", self)
        self.validation_label.setObjectName("ManualProviderValidationMessage")
        self.validation_label.setWordWrap(True)
        root.addWidget(self.validation_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText("Сохранить")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        self.buttons.accepted.connect(self._accept_valid)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        for editor in (
            self.display_name_edit,
            self.homepage_url_edit,
            self.endpoint_url_edit,
        ):
            editor.textChanged.connect(self._refresh_validation)
        self._refresh_validation()

    def draft(self) -> ManualProviderDraft:
        return ManualProviderDraft(
            display_name=self.display_name_edit.text(),
            homepage_url=self.homepage_url_edit.text(),
            endpoint_url=self.endpoint_url_edit.text(),
        )

    def _refresh_validation(self) -> None:
        if self._accepted_once:
            self.save_button.setEnabled(False)
            return
        try:
            self.draft()
        except (TypeError, ValueError):
            self.save_button.setEnabled(False)
            self.validation_label.setText(
                "Укажите безопасные название и HTTP(S) адрес без credentials/query/fragment."
            )
            return
        self.validation_label.clear()
        self.save_button.setEnabled(True)

    def _accept_valid(self) -> None:
        if self._accepted_once:
            return
        try:
            self.draft()
        except (TypeError, ValueError):
            self._refresh_validation()
            return
        self._accepted_once = True
        self.save_button.setEnabled(False)
        self.accept()


class ManualProviderProtocolDialogOperation(StrEnum):
    SAVE = "save"
    CLEAR = "clear"


class ManualProviderProtocolDialog(QDialog):
    """Controlled editor for inert, non-secret manual protocol metadata."""

    def __init__(
        self,
        registration: ManualProviderRegistration,
        *,
        policies: Iterable[ManualProviderProtocolPolicy] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._registration = registration
        self._policies = tuple(policies or manual_provider_protocol_policies())
        self._policy_by_family = {item.family: item for item in self._policies}
        self._accepted_once = False
        self.operation = ManualProviderProtocolDialogOperation.SAVE
        self.setWindowTitle(f"Протокол — {registration.display_name}")
        self.setModal(True)
        self.setObjectName("ManualProviderProtocolDialog")

        root = QVBoxLayout(self)
        notice = QLabel(
            "Выбор сохраняет только декларативные non-secret metadata. "
            "Соединение не проверяется, а источник останется недоступен для запуска "
            "до создания отдельного адаптера.",
            self,
        )
        notice.setObjectName("ManualProviderProtocolNotice")
        notice.setWordWrap(True)
        root.addWidget(notice)

        form = QFormLayout()
        self.family_combo = QComboBox(self)
        self.family_combo.setObjectName("ManualProviderProtocolFamily")
        self.family_combo.setAccessibleName("Семейство протокола")
        for policy in self._policies:
            self.family_combo.addItem(policy.display_name, policy.family)
        form.addRow("Протокол", self.family_combo)

        self.endpoint_edit = QLineEdit(self)
        self.endpoint_edit.setObjectName("ManualProviderProtocolEndpoint")
        self.endpoint_edit.setAccessibleName("Endpoint протокола")
        self.endpoint_edit.setMaxLength(2048)
        form.addRow("Endpoint", self.endpoint_edit)

        self.payload_combo = QComboBox(self)
        self.payload_combo.setObjectName("ManualProviderPayloadFormat")
        self.payload_combo.setAccessibleName("Формат данных")
        form.addRow("Формат", self.payload_combo)

        self.authentication_combo = QComboBox(self)
        self.authentication_combo.setObjectName("ManualProviderAuthenticationKind")
        self.authentication_combo.setAccessibleName("Требование аутентификации")
        form.addRow("Аутентификация", self.authentication_combo)

        self.ftps_mode_combo = QComboBox(self)
        self.ftps_mode_combo.setObjectName("ManualProviderFtpsMode")
        self.ftps_mode_combo.setAccessibleName("Режим FTPS")
        self.ftps_mode_combo.addItem("Implicit TLS (990)", ManualProviderFtpsMode.IMPLICIT)
        self.ftps_mode_combo.addItem("Explicit AUTH TLS (21)", ManualProviderFtpsMode.EXPLICIT)
        self.ftps_mode_label = QLabel("Режим FTPS", self)
        form.addRow(self.ftps_mode_label, self.ftps_mode_combo)
        root.addLayout(form)

        self.warning_label = QLabel("", self)
        self.warning_label.setObjectName("ManualProviderProtocolWarning")
        self.warning_label.setWordWrap(True)
        root.addWidget(self.warning_label)

        self.validation_label = QLabel("", self)
        self.validation_label.setObjectName("ManualProviderProtocolValidation")
        self.validation_label.setWordWrap(True)
        root.addWidget(self.validation_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText(
            "Изменить" if registration.protocol_selection is not None else "Сохранить"
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        self.clear_button = self.buttons.addButton(
            "Сбросить выбор",
            QDialogButtonBox.ButtonRole.DestructiveRole,
        )
        self.clear_button.setObjectName("ClearManualProviderProtocolButton")
        self.clear_button.setEnabled(registration.protocol_selection is not None)
        self.buttons.accepted.connect(self._accept_valid)
        self.buttons.rejected.connect(self.reject)
        self.clear_button.clicked.connect(self._accept_clear)
        root.addWidget(self.buttons)

        selected = registration.protocol_selection
        if selected is not None:
            index = self.family_combo.findData(selected.family)
            if index >= 0:
                self.family_combo.setCurrentIndex(index)
        self._refresh_policy_controls()
        if selected is not None:
            self.endpoint_edit.setText(selected.endpoint_url)
            payload_index = self.payload_combo.findData(selected.payload_format)
            if payload_index >= 0:
                self.payload_combo.setCurrentIndex(payload_index)
            auth_index = self.authentication_combo.findData(selected.authentication_kind)
            if auth_index >= 0:
                self.authentication_combo.setCurrentIndex(auth_index)
            mode_index = self.ftps_mode_combo.findData(selected.ftps_mode)
            if mode_index >= 0:
                self.ftps_mode_combo.setCurrentIndex(mode_index)

        self.family_combo.currentIndexChanged.connect(self._refresh_policy_controls)
        self.endpoint_edit.textChanged.connect(self._refresh_validation)
        self.payload_combo.currentIndexChanged.connect(self._refresh_validation)
        self.authentication_combo.currentIndexChanged.connect(self._refresh_validation)
        self.ftps_mode_combo.currentIndexChanged.connect(self._refresh_validation)
        self._refresh_validation()

    @property
    def expected_updated_at(self) -> datetime:
        return self._registration.updated_at

    def draft(self) -> ManualProviderProtocolDraft:
        raw_family = self.family_combo.currentData()
        raw_payload = self.payload_combo.currentData()
        raw_authentication = self.authentication_combo.currentData()
        raw_ftps_mode = self.ftps_mode_combo.currentData()
        try:
            family = ManualProviderProtocolFamily(str(raw_family))
            payload = (
                ManualProviderPayloadFormat(str(raw_payload)) if raw_payload is not None else None
            )
            authentication = ManualProviderAuthenticationKind(str(raw_authentication))
            ftps_mode = (
                ManualProviderFtpsMode(str(raw_ftps_mode))
                if family is ManualProviderProtocolFamily.FTPS
                else None
            )
        except (TypeError, ValueError):
            raise ValueError("manual provider protocol selection is invalid")
        return ManualProviderProtocolDraft(
            family=family,
            endpoint_url=self.endpoint_edit.text(),
            payload_format=payload,
            authentication_kind=authentication,
            ftps_mode=ftps_mode,
        )

    def _refresh_policy_controls(self) -> None:
        family = self.family_combo.currentData()
        policy = self._policy_by_family.get(family)
        if policy is None:
            self.save_button.setEnabled(False)
            return
        self.endpoint_edit.setPlaceholderText(policy.endpoint_placeholder)
        self.warning_label.setText(policy.warning)
        ftps_visible = policy.family is ManualProviderProtocolFamily.FTPS
        self.ftps_mode_combo.setVisible(ftps_visible)
        self.ftps_mode_label.setVisible(ftps_visible)

        previous_payload = self.payload_combo.currentData()
        self.payload_combo.blockSignals(True)
        self.payload_combo.clear()
        if policy.allowed_payload_formats:
            for payload_value in policy.allowed_payload_formats:
                self.payload_combo.addItem(payload_value.value.upper(), payload_value)
        else:
            self.payload_combo.addItem("Не применяется", None)
        payload_index = self.payload_combo.findData(previous_payload)
        if payload_index >= 0:
            self.payload_combo.setCurrentIndex(payload_index)
        self.payload_combo.setEnabled(bool(policy.allowed_payload_formats))
        self.payload_combo.blockSignals(False)

        previous_auth = self.authentication_combo.currentData()
        self.authentication_combo.blockSignals(True)
        self.authentication_combo.clear()
        auth_labels = {
            ManualProviderAuthenticationKind.NONE: "Не требуется",
            ManualProviderAuthenticationKind.API_KEY: "API key потребуется позже",
            ManualProviderAuthenticationKind.USERNAME_PASSWORD: (
                "Username/password потребуются позже"
            ),
        }
        for auth_value in policy.allowed_authentication_kinds:
            self.authentication_combo.addItem(auth_labels[auth_value], auth_value)
        auth_index = self.authentication_combo.findData(previous_auth)
        if auth_index >= 0:
            self.authentication_combo.setCurrentIndex(auth_index)
        self.authentication_combo.blockSignals(False)
        self._refresh_validation()

    def _refresh_validation(self) -> None:
        if self._accepted_once:
            self.save_button.setEnabled(False)
            return
        try:
            self.draft()
        except (TypeError, ValueError):
            self.save_button.setEnabled(False)
            self.validation_label.setText(
                "Проверьте endpoint и параметры, разрешённые выбранным семейством."
            )
            return
        self.validation_label.setText(
            "Протокол можно сохранить; для запуска всё ещё потребуется адаптер."
        )
        self.save_button.setEnabled(True)

    def _accept_valid(self) -> None:
        if self._accepted_once:
            return
        try:
            self.draft()
        except (TypeError, ValueError):
            self._refresh_validation()
            return
        self._accepted_once = True
        self.operation = ManualProviderProtocolDialogOperation.SAVE
        self.accept()

    def _accept_clear(self) -> None:
        if self._accepted_once or self._registration.protocol_selection is None:
            return
        self._accepted_once = True
        self.operation = ManualProviderProtocolDialogOperation.CLEAR
        self.accept()


class ManualAdapterWizardDialog(QDialog):
    """Restricted declarative adapter editor with explicit offline preview."""

    SUCCESS_MESSAGE = "Адаптер настроен. Требуется проверка подключения."

    def __init__(
        self,
        registration: ManualProviderRegistration | None = None,
        *,
        preview_command: (
            Callable[[ManualAdapterSpec, str], ManualAdapterPreviewResult] | None
        ) = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._registration = registration
        self._preview_command = preview_command
        self._accepted_once = False
        self.setWindowTitle("Безопасный мастер адаптера")
        self.setModal(True)
        self.setObjectName("ManualAdapterWizardDialog")
        root = QVBoxLayout(self)

        source_name = registration.display_name if registration is not None else "Тестовый источник"
        protocol = registration.protocol_selection if registration is not None else None
        self.source_notice = QLabel(
            f"Источник: {source_name}. Протокол: {protocol.family.value.upper() if protocol else 'не выбран'}.",
            self,
        )
        self.source_notice.setWordWrap(True)
        root.addWidget(self.source_notice)

        form = QFormLayout()
        self.format_combo = QComboBox(self)
        self.format_combo.setAccessibleName("Формат входных данных")
        formats_by_protocol = {
            ManualProviderProtocolFamily.API: (
                ManualAdapterDataFormat.JSON,
                ManualAdapterDataFormat.XML,
            ),
            ManualProviderProtocolFamily.RSS: (
                ManualAdapterDataFormat.RSS,
                ManualAdapterDataFormat.ATOM,
            ),
            ManualProviderProtocolFamily.FTP: (
                ManualAdapterDataFormat.JSON,
                ManualAdapterDataFormat.XML,
                ManualAdapterDataFormat.CSV,
            ),
            ManualProviderProtocolFamily.FTPS: (
                ManualAdapterDataFormat.JSON,
                ManualAdapterDataFormat.XML,
                ManualAdapterDataFormat.CSV,
            ),
        }
        allowed_formats = (
            formats_by_protocol[protocol.family]
            if protocol is not None
            else tuple(ManualAdapterDataFormat)
        )
        for data_format in allowed_formats:
            self.format_combo.addItem(data_format.value.upper(), data_format)
        form.addRow("Формат", self.format_combo)

        self.filename_suffix_edit = QLineEdit(self)
        self.filename_suffix_edit.setPlaceholderText(".json (обязательно для FTP/FTPS)")
        self.filename_suffix_edit.setAccessibleName("Суффикс имени файла")
        form.addRow("Суффикс файла", self.filename_suffix_edit)

        self.record_selector_edit = QLineEdit(self)
        self.record_selector_edit.setPlaceholderText("items или rss.channel.item")
        self.record_selector_edit.setAccessibleName("Путь к записям")
        form.addRow("Путь к записям", self.record_selector_edit)
        root.addLayout(form)

        mapping_help = QLabel(
            "Сопоставление: одна строка target=source.path. Добавьте ! после target для обязательного поля.",
            self,
        )
        mapping_help.setWordWrap(True)
        root.addWidget(mapping_help)
        self.mapping_edit = QPlainTextEdit(self)
        self.mapping_edit.setAccessibleName("Сопоставление канонических полей")
        self.mapping_edit.setPlaceholderText("!title=name\nexternal_id=id\nprice.amount=price")
        self.mapping_edit.setMaximumBlockCount(64)
        root.addWidget(self.mapping_edit)

        self.preview_notice = QLabel(
            "Offline sample — подключение не проверено. Сеть и credentials не используются.",
            self,
        )
        self.preview_notice.setWordWrap(True)
        root.addWidget(self.preview_notice)
        self.sample_edit = QPlainTextEdit(self)
        self.sample_edit.setAccessibleName("Локальный sample")
        self.sample_edit.setPlaceholderText("Вставьте ограниченный локальный sample")
        root.addWidget(self.sample_edit)
        self.preview_button = QPushButton("Проверить offline sample", self)
        self.preview_button.clicked.connect(self._run_offline_preview)
        root.addWidget(self.preview_button)

        self.validation_label = QLabel("", self)
        self.validation_label.setWordWrap(True)
        root.addWidget(self.validation_label)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText("Сохранить адаптер")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        self.buttons.accepted.connect(self._accept_valid)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        if registration is not None and registration.adapter_spec is not None:
            self._load_spec(registration.adapter_spec)
        for widget in (
            self.filename_suffix_edit,
            self.record_selector_edit,
            self.mapping_edit,
        ):
            widget.textChanged.connect(self._refresh_validation)
        self.format_combo.currentIndexChanged.connect(self._refresh_validation)
        self._refresh_validation()

    @classmethod
    def empty_for_test(cls) -> "ManualAdapterWizardDialog":
        return cls()

    @property
    def expected_updated_at(self) -> datetime:
        if self._registration is None:
            raise ValueError("manual registration is required")
        return self._registration.updated_at

    def specification(self, *, timestamp: datetime | None = None) -> ManualAdapterSpec:
        registration = self._registration
        if registration is None or registration.protocol_selection is None:
            raise ValueError("manual protocol is required")
        current = registration.adapter_spec
        return create_manual_adapter_spec(
            provider_id=registration.provider_id,
            protocol_family=registration.protocol_selection.family,
            source=SourceRequestSpec(
                data_format=ManualAdapterDataFormat(str(self.format_combo.currentData())),
                filename_suffix=self.filename_suffix_edit.text(),
            ),
            record_selector=RecordSelectorSpec(
                parse_restricted_path(self.record_selector_edit.text())
            ),
            field_mappings=parse_field_mapping_lines(self.mapping_edit.toPlainText()),
            limits=current.limits if current is not None else None,
            revision=registration.next_adapter_revision,
            timestamp=timestamp or datetime.now(timezone.utc),
            created_at=(
                current.created_at
                if current is not None
                else (
                    registration.adapter_spec_history[-1].created_at
                    if registration.adapter_spec_history
                    else None
                )
            ),
        )

    def _load_spec(self, spec: ManualAdapterSpec) -> None:
        index = self.format_combo.findData(spec.source.data_format)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
        self.filename_suffix_edit.setText(spec.source.filename_suffix)
        self.record_selector_edit.setText(".".join(spec.record_selector.path))
        self.mapping_edit.setPlainText(
            "\n".join(
                f"{'!' if item.required else ''}{item.target_field.value}={'.'.join(item.source_path)}"
                for item in spec.field_mappings
            )
        )

    def _run_offline_preview(self) -> None:
        if self._preview_command is None:
            self.validation_label.setText("Offline preview недоступен без application command.")
            return
        try:
            result = self._preview_command(self.specification(), self.sample_edit.toPlainText())
        except (TypeError, ValueError):
            self.validation_label.setText("Исправьте спецификацию перед offline preview.")
            return
        if result.has_errors:
            self.validation_label.setText("Offline preview отклонён: проверьте mapping и sample.")
        else:
            self.validation_label.setText(
                f"Offline preview: записей {len(result.records)}. Подключение не проверено."
            )

    def _refresh_validation(self) -> None:
        if self._accepted_once:
            self.save_button.setEnabled(False)
            return
        try:
            self.specification()
        except (TypeError, ValueError):
            self.save_button.setEnabled(False)
            self.validation_label.setText("Заполните поддерживаемый формат, selector и mapping.")
            return
        self.save_button.setEnabled(True)
        self.validation_label.setText("Спецификация валидна; подключение останется непроверенным.")

    def _accept_valid(self) -> None:
        try:
            self.specification()
        except (TypeError, ValueError):
            self._refresh_validation()
            return
        self._accepted_once = True
        self.save_button.setEnabled(False)
        self.accept()


class TenderProviderConfigurationDialog(QDialog):
    """Presentation-only editor for known non-secret provider fields."""

    def __init__(
        self,
        state: ProviderDisplayState,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self.setWindowTitle(f"Настройка источника — {state.display_name}")
        self.setModal(True)
        self.setObjectName("TenderProviderConfigurationDialog")

        root = QVBoxLayout(self)
        self.origin_label = QLabel(
            f"Источник значения: {_origin_label(state.configuration_origin)}",
            self,
        )
        self.origin_label.setObjectName("ProviderConfigurationOrigin")
        root.addWidget(self.origin_label)

        form = QFormLayout()
        self.access_confirmed_checkbox = QCheckBox(
            "Разрешённый способ API-доступа подтверждён",
            self,
        )
        self.access_confirmed_checkbox.setObjectName("ProviderAccessConfirmed")
        self.access_confirmed_checkbox.setChecked(state.configuration.access_confirmed)
        form.addRow("Доступ", self.access_confirmed_checkbox)

        self.api_base_url_edit = QLineEdit(self)
        self.api_base_url_edit.setObjectName("ProviderApiBaseUrl")
        self.api_base_url_edit.setPlaceholderText("https://api.example.ru/v1")
        self.api_base_url_edit.setText(state.configuration.api_base_url)
        form.addRow("Проверенный API endpoint", self.api_base_url_edit)
        root.addLayout(form)

        self.validation_label = QLabel("", self)
        self.validation_label.setObjectName("ProviderConfigurationValidation")
        self.validation_label.setWordWrap(True)
        root.addWidget(self.validation_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        editable = state.configuration_editable
        self.access_confirmed_checkbox.setEnabled(editable)
        self.api_base_url_edit.setEnabled(editable)
        buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(editable)

    def configuration(self) -> ProviderConfiguration:
        return ProviderConfiguration(
            access_confirmed=self.access_confirmed_checkbox.isChecked(),
            api_base_url=self.api_base_url_edit.text(),
        )

    def _validate_and_accept(self) -> None:
        try:
            self.configuration()
        except (TypeError, ValueError) as exc:
            self.validation_label.setText(str(exc))
            return
        self.accept()


def _connection_text(value: SourceMonitoringState | None) -> str:
    if value is None:
        return "—"
    status = {
        "available": "Доступно",
        "degraded": "Ограничено",
        "unavailable": "Недоступно",
        "not_configured": "Не настроено",
        "unknown": "Неизвестно",
    }[value.connection.status.value]
    return f"{status} · {_freshness_text(value.connection.freshness)}"


def _operational_text(value: SourceMonitoringState | None) -> str:
    if value is None:
        return "—"
    status = {
        "available": "Успешно",
        "degraded": "Сбой",
        "cooldown": "Cooldown",
        "unavailable": "Недоступно",
        "not_configured": "Не настроено",
        "disabled": "Отключено",
        "unknown": "Нет запусков",
    }[value.operational.status.value]
    if value.operational.cooldown_remaining_seconds > 0:
        status += f" · {round(value.operational.cooldown_remaining_seconds)} сек."
    return status


def _checkpoint_text(value: SourceMonitoringState | None) -> str:
    if value is None:
        return "—"
    checkpoint = value.checkpoint
    if not checkpoint.supported:
        return "Не поддерживается"
    if not checkpoint.present:
        return "Нет данных"
    return f"{checkpoint.scope_key} · {_freshness_text(checkpoint.freshness)}"


def _verification_text(value: SourceMonitoringState | None) -> str:
    if value is None:
        return "—"
    if value.verification.qualifies_as_working:
        return "WORKING · актуально"
    return {
        "working": "WORKING · устарело",
        "failed": "FAILED",
        "not_configured": "Не настроено",
        "unverified": "Не проверено",
    }[value.verification.status.value]


def _attention_text(value: SourceMonitoringState | None) -> str:
    if value is None or value.attention is SourceAttentionLevel.NONE:
        return "Нет"
    return {
        SourceAttentionLevel.INFO: "Информация",
        SourceAttentionLevel.WARNING: "Требует внимания",
        SourceAttentionLevel.CRITICAL: "Критично",
    }[value.attention]


def _freshness_text(value: SourceFreshness) -> str:
    return {
        SourceFreshness.CURRENT: "актуально",
        SourceFreshness.STALE: "устарело",
        SourceFreshness.UNKNOWN: "неизвестно",
        SourceFreshness.INVALID: "некорректно",
        SourceFreshness.NOT_APPLICABLE: "не применяется",
    }[value]


def _monitoring_details_html(value: SourceMonitoringState | None) -> str:
    if value is None:
        return "Мониторинг: нет локального snapshot."
    observed = value.operational.observed_at.isoformat() if value.operational.observed_at else ""
    reasons = "; ".join(reason.message for reason in value.reasons) or "нет"
    return (
        "<b>Мониторинг источника</b><br>"
        f"Подключение: {_escape_html(_connection_text(value))}<br>"
        f"Сбор/circuit: {_escape_html(_operational_text(value))}<br>"
        f"Последнее наблюдение сбора: {_format_timestamp(observed)}<br>"
        f"Checkpoint: {_escape_html(_checkpoint_text(value))}<br>"
        f"C19: {_escape_html(_verification_text(value))}<br>"
        f"Расписание: {'активно' if value.schedule.active else 'неактивно'}<br>"
        f"Причины: {_escape_html(reasons)}"
    )


def _format_timestamp(value: str) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone().strftime("%d.%m.%Y %H:%M")


def _escape_html(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _origin_label(origin: ProviderSettingOrigin) -> str:
    return {
        ProviderSettingOrigin.DEFAULT: "значение по умолчанию",
        ProviderSettingOrigin.PERSISTED: "локальные настройки",
        ProviderSettingOrigin.LEGACY_MIGRATED: "совместимые legacy-настройки",
        ProviderSettingOrigin.ENVIRONMENT: "переменные окружения (только чтение)",
    }[origin]


__all__ = [
    "ManualAdapterWizardDialog",
    "ManualProviderProtocolDialog",
    "ManualProviderProtocolDialogOperation",
    "ManualProviderRegistrationDialog",
    "TenderProviderConfigurationDialog",
    "TenderProviderManagerDialog",
]
