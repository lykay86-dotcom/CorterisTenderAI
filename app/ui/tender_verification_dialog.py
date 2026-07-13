"""Field-level provenance and conflict-resolution dialog."""

from __future__ import annotations

from datetime import datetime
from html import escape

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.tenders.collector.verification import (
    FieldCandidate,
    FieldResolutionAction,
)
from app.tenders.collector.verification_review import (
    STATUS_LABELS,
    TRUST_LABELS,
    TenderVerificationReview,
    VerificationFieldReview,
)
from app.ui.theme.colors import ThemeName, get_palette


class TenderVerificationDialog(QDialog):
    """Compare field values and record explicit manual resolutions."""

    resolve_requested = Signal(str, str, str, str)
    clear_requested = Signal(str, str, str)
    refresh_requested = Signal(str)

    def __init__(
        self,
        review: TenderVerificationReview,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = ThemeName(theme)
        self._review = review
        self._fields: tuple[VerificationFieldReview, ...] = ()
        self.setWindowTitle("Corteris Tender AI — достоверность и источники")
        self.resize(1240, 800)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        summary = QFrame(self)
        summary.setObjectName("VerificationSummary")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        self.status_value = QLabel("—", summary)
        self.status_value.setObjectName("VerificationStatusValue")
        self.summary_text = QLabel("", summary)
        self.summary_text.setWordWrap(True)
        self.summary_text.setObjectName("VerificationSummaryText")
        summary_layout.addWidget(self.status_value)
        summary_layout.addWidget(self.summary_text, 1)
        root.addWidget(summary)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        left = QFrame(splitter)
        left.setObjectName("VerificationPanel")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.addWidget(QLabel("Критичные поля", left))
        self.fields_table = QTableWidget(left)
        self.fields_table.setColumnCount(5)
        self.fields_table.setHorizontalHeaderLabels(
            ("Поле", "Выбрано", "Источник", "Доверие", "Состояние")
        )
        self.fields_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.fields_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.fields_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.fields_table.verticalHeader().setVisible(False)
        self.fields_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.fields_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.fields_table.itemSelectionChanged.connect(self._render_selected_field)
        left_layout.addWidget(self.fields_table, 1)
        splitter.addWidget(left)

        right = QFrame(splitter)
        right.setObjectName("VerificationPanel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 10, 10, 10)
        self.field_title = QLabel("Источники поля", right)
        self.field_title.setObjectName("VerificationSectionTitle")
        right_layout.addWidget(self.field_title)

        self.candidates_table = QTableWidget(right)
        self.candidates_table.setColumnCount(8)
        self.candidates_table.setHorizontalHeaderLabels(
            (
                "Выбор",
                "Значение",
                "Источник",
                "Уровень",
                "Офиц.",
                "Проверено",
                "Доверие",
                "Получено",
            )
        )
        self.candidates_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.candidates_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.candidates_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.candidates_table.verticalHeader().setVisible(False)
        self.candidates_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.candidates_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.candidates_table.itemSelectionChanged.connect(self._render_candidate_details)
        right_layout.addWidget(self.candidates_table, 1)

        self.candidate_details = QTextBrowser(right)
        self.candidate_details.setObjectName("VerificationDetails")
        self.candidate_details.setOpenExternalLinks(False)
        self.candidate_details.anchorClicked.connect(QDesktopServices.openUrl)
        self.candidate_details.setMaximumHeight(150)
        right_layout.addWidget(self.candidate_details)

        note_row = QHBoxLayout()
        note_row.addWidget(QLabel("Комментарий:", right))
        self.note_edit = QLineEdit(right)
        self.note_edit.setPlaceholderText("Почему выбрано это значение — необязательно")
        note_row.addWidget(self.note_edit, 1)
        right_layout.addLayout(note_row)

        field_actions = QHBoxLayout()
        self.select_button = QPushButton("Выбрать значение", right)
        self.select_button.setObjectName("PrimaryActionButton")
        self.select_button.clicked.connect(self._emit_resolution)
        self.clear_button = QPushButton("Снять ручной выбор", right)
        self.clear_button.clicked.connect(self._emit_clear)
        self.open_source_button = QPushButton("Открыть источник", right)
        self.open_source_button.clicked.connect(self._open_selected_source)
        field_actions.addWidget(self.select_button)
        field_actions.addWidget(self.clear_button)
        field_actions.addWidget(self.open_source_button)
        field_actions.addStretch(1)
        right_layout.addLayout(field_actions)
        splitter.addWidget(right)
        splitter.setSizes([500, 740])

        history_title = QLabel("Журнал ручных решений", self)
        history_title.setObjectName("VerificationSectionTitle")
        root.addWidget(history_title)
        self.history_table = QTableWidget(self)
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels(
            (
                "Дата",
                "Поле",
                "Действие",
                "Источник",
                "Пользователь",
                "Комментарий",
                "ID решения",
            )
        )
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )
        self.history_table.setMaximumHeight(190)
        root.addWidget(self.history_table)

        actions = QHBoxLayout()
        self.refresh_button = QPushButton("Обновить", self)
        self.refresh_button.clicked.connect(
            lambda: self.refresh_requested.emit(self._review.registry_key)
        )
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        root.addLayout(actions)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("VerificationStatusMessage")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.apply_theme(self._theme)
        self.set_review(review)

    @property
    def review(self) -> TenderVerificationReview:
        return self._review

    def set_review(self, review: TenderVerificationReview) -> None:
        selected_field = self.selected_field_name()
        self._review = review
        self._fields = review.fields
        state = review.state
        status = (
            STATUS_LABELS.get(state.status, state.status.value)
            if state is not None
            else "Не проверено"
        )
        self.status_value.setText(status)
        self.status_value.setProperty(
            "verificationStatus",
            state.status.value if state is not None else "unverified",
        )
        self.status_value.style().unpolish(self.status_value)
        self.status_value.style().polish(self.status_value)
        if state is None:
            self.summary_text.setText("Для этой записи ещё нет результатов проверки полей.")
        else:
            self.summary_text.setText(
                f"Подтверждено {state.verified_field_count} из "
                f"{state.critical_field_count}; официальных полей: "
                f"{state.official_field_count}; конфликтов: "
                f"{state.conflict_count}, нерешённых: "
                f"{state.unresolved_conflict_count}; минимальная "
                f"достоверность: {state.minimum_confidence:.0%}."
            )
        self._populate_fields(selected_field)
        self._populate_history()

    def selected_field_name(self) -> str:
        row = self.fields_table.currentRow()
        if not 0 <= row < len(self._fields):
            return ""
        return self._fields[row].field_name

    def selected_candidate(self) -> FieldCandidate | None:
        field = self._selected_field()
        if field is None:
            return None
        row = self.candidates_table.currentRow()
        if not 0 <= row < len(field.candidates):
            return None
        return field.candidates[row]

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("error", error)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _populate_fields(self, selected_name: str) -> None:
        self.fields_table.setRowCount(len(self._fields))
        selected_row = 0
        palette = get_palette(self._theme)
        for row, field in enumerate(self._fields):
            selected = field.selected_candidate
            conflict = field.conflict
            state_text = (
                "Решено вручную"
                if field.manually_selected
                else (
                    "Конфликт"
                    if conflict is not None and conflict.unresolved
                    else ("Есть расхождения" if conflict is not None else "OK")
                )
            )
            values = (
                field.label,
                _format_value(selected.value if selected is not None else None),
                selected.source_id if selected is not None else "—",
                (
                    TRUST_LABELS.get(selected.trust_level, str(selected.trust_level))
                    if selected is not None
                    else "—"
                ),
                state_text,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, field.field_name)
                if column == 4:
                    if field.manually_selected:
                        item.setForeground(QColor(palette.info))
                    elif conflict is not None and conflict.unresolved:
                        item.setForeground(QColor(palette.danger))
                    elif conflict is not None:
                        item.setForeground(QColor(palette.warning))
                    else:
                        item.setForeground(QColor(palette.success))
                self.fields_table.setItem(row, column, item)
            if field.field_name == selected_name:
                selected_row = row
        if self._fields:
            self.fields_table.selectRow(selected_row)
            self._render_selected_field()

    def _populate_history(self) -> None:
        self.history_table.setRowCount(len(self._review.resolutions))
        for row, item in enumerate(self._review.resolutions):
            action = (
                "Выбрано значение"
                if item.action == FieldResolutionAction.SELECTED
                else "Снят ручной выбор"
            )
            values = (
                _format_timestamp(item.resolved_at),
                next(
                    (field.label for field in self._fields if field.field_name == item.field_name),
                    item.field_name,
                ),
                action,
                item.selected_source_id or "—",
                item.resolved_by,
                item.note or "—",
                item.resolution_id,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                self.history_table.setItem(row, column, cell)

    def _selected_field(self) -> VerificationFieldReview | None:
        row = self.fields_table.currentRow()
        if not 0 <= row < len(self._fields):
            return None
        return self._fields[row]

    def _render_selected_field(self) -> None:
        field = self._selected_field()
        if field is None:
            self.candidates_table.setRowCount(0)
            return
        self.field_title.setText(f"Источники поля: {field.label}")
        self.candidates_table.setRowCount(len(field.candidates))
        selected_row = 0
        for row, candidate in enumerate(field.candidates):
            marker = (
                "✓ вручную" if candidate.manual_override else ("✓" if candidate.selected else "")
            )
            values = (
                marker,
                _format_value(candidate.value),
                candidate.source_id,
                TRUST_LABELS.get(candidate.trust_level, str(candidate.trust_level)),
                "Да" if candidate.official else "Нет",
                "Да" if candidate.verified else "Нет",
                f"{candidate.confidence:.0%}",
                _format_timestamp(candidate.retrieved_at),
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, candidate.candidate_id)
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.candidates_table.setItem(row, column, cell)
            if candidate.selected:
                selected_row = row
        if field.candidates:
            self.candidates_table.selectRow(selected_row)
        self.select_button.setEnabled(bool(field.candidates))
        self.clear_button.setEnabled(field.manually_selected)
        self._render_candidate_details()

    def _render_candidate_details(self) -> None:
        candidate = self.selected_candidate()
        if candidate is None:
            self.candidate_details.clear()
            self.open_source_button.setEnabled(False)
            return
        self.open_source_button.setEnabled(bool(candidate.source_url))
        self.candidate_details.setHtml(
            f"<p><b>Значение:</b> {escape(_format_value(candidate.value))}</p>"
            f"<p><b>Источник:</b> {escape(candidate.source_id)}</p>"
            f"<p><b>Уровень:</b> "
            f"{escape(TRUST_LABELS.get(candidate.trust_level, str(candidate.trust_level)))}</p>"
            f"<p><b>Достоверность:</b> {candidate.confidence:.0%}; "
            f"официальный: {'да' if candidate.official else 'нет'}; "
            f"проверен: {'да' if candidate.verified else 'нет'}.</p>"
            + (
                f'<p><a href="{escape(candidate.source_url)}">Открыть источник</a></p>'
                if candidate.source_url
                else ""
            )
        )

    def _emit_resolution(self) -> None:
        field = self._selected_field()
        candidate = self.selected_candidate()
        if field is None or candidate is None:
            self.set_status("Выберите поле и значение.", error=True)
            return
        self.resolve_requested.emit(
            self._review.registry_key,
            field.field_name,
            candidate.candidate_id,
            self.note_edit.text().strip(),
        )

    def _emit_clear(self) -> None:
        field = self._selected_field()
        if field is None or not field.manually_selected:
            return
        self.clear_requested.emit(
            self._review.registry_key,
            field.field_name,
            self.note_edit.text().strip(),
        )

    def _open_selected_source(self) -> None:
        candidate = self.selected_candidate()
        if candidate is not None and candidate.source_url:
            QDesktopServices.openUrl(QUrl(candidate.source_url))

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"""
            QDialog {{
                color: {palette.text_primary};
                background-color: {palette.app_background};
            }}
            QFrame#VerificationSummary,
            QFrame#VerificationPanel {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_default};
                border-radius: 9px;
            }}
            QLabel#VerificationStatusValue {{
                color: {palette.text_secondary};
                font-size: 18px;
                font-weight: 800;
            }}
            QLabel#VerificationStatusValue[verificationStatus="verified_eis"],
            QLabel#VerificationStatusValue[verificationStatus="verified_platform"],
            QLabel#VerificationStatusValue[verificationStatus="verified_documentation"],
            QLabel#VerificationStatusValue[verificationStatus="verified_official_api"] {{
                color: {palette.success};
            }}
            QLabel#VerificationStatusValue[verificationStatus="conflict"] {{
                color: {palette.danger};
            }}
            QLabel#VerificationStatusValue[verificationStatus="incomplete"],
            QLabel#VerificationStatusValue[verificationStatus="aggregator_only"] {{
                color: {palette.warning};
            }}
            QLabel#VerificationSummaryText,
            QLabel#VerificationStatusMessage {{
                color: {palette.text_secondary};
            }}
            QLabel#VerificationStatusMessage[error="true"] {{
                color: {palette.danger};
            }}
            QLabel#VerificationSectionTitle {{
                font-size: 14px;
                font-weight: 700;
            }}
            QTableWidget, QTextBrowser#VerificationDetails, QLineEdit {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 6px;
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
            QPushButton {{
                min-height: 31px;
                color: {palette.text_primary};
                background-color: {palette.elevated_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 4px 10px;
                font-weight: 600;
            }}
            QPushButton#PrimaryActionButton {{
                color: {palette.text_on_brand};
                background-color: {palette.brand_primary};
                border-color: {palette.brand_primary};
            }}
            """
        )


def _format_value(value: object) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, dict):
        if "amount" in value:
            amount = str(value.get("amount", ""))
            currency = str(value.get("currency", "RUB"))
            return f"{amount} {currency}".strip()
        return "; ".join(f"{key}: {item}" for key, item in value.items())
    return str(value)


def _format_timestamp(value: str) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone().strftime("%d.%m.%Y %H:%M")


__all__ = ["TenderVerificationDialog"]
