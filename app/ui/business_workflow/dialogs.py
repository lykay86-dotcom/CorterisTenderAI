"""Dialogs for creating business workflow records."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.financial import (
    MAX_MARGIN,
    MAX_MONEY,
    canonical_money,
    canonical_percentage,
    derive_margin,
    parse_money,
)
from app.repositories.business_metrics import (
    BusinessRecordKind,
    BusinessStatus,
    BusinessWorkflowRecord,
)
from app.ui.business_workflow.model import (
    KIND_LABELS,
    STATUS_LABELS,
    statuses_for_kind,
)
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography


class DecimalValueEdit(QLineEdit):
    """Fixed-point editor that never exposes a binary floating-point value."""

    valueChanged = Signal(object)

    def __init__(
        self,
        *,
        maximum: Decimal,
        percentage: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._minimum = Decimal("0")
        self._maximum = maximum
        self._percentage = percentage
        self._decimals = 2
        self.setText("0.00")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.textChanged.connect(self._emit_value_changed)
        self.editingFinished.connect(self._canonicalize)

    def value(self) -> Decimal:
        source = self.text().strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
        try:
            value = Decimal(source)
        except Exception as exc:
            raise ValueError("invalid decimal value") from exc
        if not value.is_finite() or value < self._minimum or value > self._maximum:
            raise ValueError("decimal value is out of range")
        if max(0, -value.as_tuple().exponent) > self._decimals:
            raise ValueError("decimal value has too many fractional digits")
        return value

    def setValue(self, value: Decimal | int | str) -> None:  # noqa: N802
        if isinstance(value, float):
            raise TypeError("binary float is not accepted by DecimalValueEdit")
        parsed = Decimal(str(value))
        if not parsed.is_finite() or parsed < self._minimum or parsed > self._maximum:
            raise ValueError("decimal value is out of range")
        text = canonical_percentage(parsed) if self._percentage else canonical_money(parsed)
        self.setText(text)

    def decimals(self) -> int:
        return self._decimals

    def _emit_value_changed(self) -> None:
        try:
            value = self.value()
        except ValueError:
            return
        self.valueChanged.emit(value)

    def _canonicalize(self) -> None:
        try:
            self.setValue(self.value())
        except ValueError:
            return


class BusinessRecordDialog(QDialog):
    """Create one estimate, proposal or project record."""

    def __init__(
        self,
        *,
        initial_kind: BusinessRecordKind | str = (BusinessRecordKind.PROPOSAL),
        record: BusinessWorkflowRecord | None = None,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self._record = record
        self.setWindowTitle(
            "Редактирование записи" if record is not None else "Новая запись бизнес-процесса"
        )
        self.setModal(True)
        self.resize(560, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(16)

        title = QLabel(
            "Редактирование записи" if record is not None else "Новая запись",
            self,
        )
        title.setObjectName("BusinessDialogTitle")

        subtitle = QLabel(
            (
                "Измените название, финансовые показатели, срок или связанный файл."
                if record is not None
                else "Добавьте КП, смету или проект для синхронизации с Dashboard."
            ),
            self,
        )
        subtitle.setObjectName("BusinessDialogSubtitle")
        subtitle.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(subtitle)

        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.kind_combo = QComboBox(self)
        for kind, label in KIND_LABELS.items():
            self.kind_combo.addItem(label, kind.value)

        self.tender_edit = QLineEdit(self)
        self.tender_edit.setPlaceholderText("ID или номер тендера")

        self.title_edit = QLineEdit(self)
        self.title_edit.setPlaceholderText("Например: КП на систему видеонаблюдения")

        self.status_combo = QComboBox(self)

        self.total_spin = self._money_spin()
        self.profit_spin = self._money_spin()

        self.margin_spin = DecimalValueEdit(
            maximum=MAX_MARGIN,
            percentage=True,
            parent=self,
        )
        self.margin_spin.setReadOnly(True)
        self.margin_spin.setAccessibleName("Derived margin percentage points")

        self.due_edit = QLineEdit(self)
        self.due_edit.setPlaceholderText("YYYY-MM-DD или ДД.ММ.ГГГГ")

        self.file_edit = QLineEdit(self)
        self.file_edit.setPlaceholderText("Путь к сформированному документу")
        browse = QToolButton(self)
        browse.setText("…")
        browse.setToolTip("Выбрать файл")
        browse.clicked.connect(self._browse_file)

        file_row = QHBoxLayout()
        file_row.setContentsMargins(0, 0, 0, 0)
        file_row.setSpacing(6)
        file_row.addWidget(self.file_edit, 1)
        file_row.addWidget(browse)

        form.addRow("Тип:", self.kind_combo)
        form.addRow("Тендер:", self.tender_edit)
        form.addRow("Наименование:", self.title_edit)
        form.addRow("Статус:", self.status_combo)
        form.addRow("Сумма:", self.total_spin)
        form.addRow("Прибыль:", self.profit_spin)
        form.addRow("Маржа:", self.margin_spin)
        form.addRow("Срок:", self.due_edit)
        form.addRow("Файл:", file_row)

        root.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            "Сохранить изменения" if record is not None else "Сохранить"
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        self.buttons.accepted.connect(self._validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.kind_combo.currentIndexChanged.connect(self._refresh_statuses)
        self.total_spin.valueChanged.connect(self._recalculate_margin)
        self.profit_spin.valueChanged.connect(self._recalculate_margin)

        if record is not None:
            self._load_record(record)
        else:
            self._set_initial_kind(initial_kind)

        self.apply_theme(self._theme)

    @property
    def record(self) -> BusinessWorkflowRecord | None:
        return self._record

    @property
    def edit_mode(self) -> bool:
        return self._record is not None

    def payload(self) -> dict[str, object]:
        return {
            "kind": BusinessRecordKind(str(self.kind_combo.currentData())),
            "tender_id": self.tender_edit.text().strip(),
            "title": self.title_edit.text().strip(),
            "status": BusinessStatus(str(self.status_combo.currentData())),
            "total": self.total_spin.value(),
            "profit": self.profit_spin.value(),
            "margin_percent": self.margin_spin.value(),
            "due_date": self.due_edit.text().strip(),
            "file_path": self.file_edit.text().strip(),
        }

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {palette.panel_background};
                color: {palette.text_primary};
            }}
            QLabel#BusinessDialogTitle {{
                color: {palette.text_primary};
                {Typography.H2.css()}
            }}
            QLabel#BusinessDialogSubtitle {{
                color: {palette.text_muted};
                {Typography.BODY_S.css()}
            }}
            QLabel {{
                color: {palette.text_secondary};
                {Typography.BODY_S.css()}
            }}
            QLineEdit, QComboBox {{
                min-height: 34px;
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 4px 8px;
                {Typography.BODY_S.css()}
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 2px solid {palette.focus_ring};
            }}
            QToolButton {{
                min-width: 34px;
                min-height: 34px;
                color: {palette.text_primary};
                background-color: {palette.elevated_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
            }}
            QDialogButtonBox QPushButton {{
                min-height: 34px;
                padding: 4px 14px;
            }}
            """
        )

    @staticmethod
    def _money_spin() -> DecimalValueEdit:
        editor = DecimalValueEdit(maximum=MAX_MONEY)
        editor.setAccessibleName("Money amount in RUB")
        editor.setPlaceholderText("0.00 RUB")
        return editor

    def _load_record(
        self,
        record: BusinessWorkflowRecord,
    ) -> None:
        self._set_initial_kind(record.kind)

        self.kind_combo.setEnabled(False)
        self.tender_edit.setEnabled(False)
        self.status_combo.setEnabled(False)

        self.tender_edit.setText(record.tender_id)
        self.title_edit.setText(record.title)

        status_index = self.status_combo.findData(record.status)
        if status_index >= 0:
            self.status_combo.setCurrentIndex(status_index)

        for spin, value in (
            (self.total_spin, record.total),
            (self.profit_spin, record.profit),
            (self.margin_spin, record.margin_percent),
        ):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)

        self.due_edit.setText(record.due_date)
        self.file_edit.setText(record.file_path)
        self.file_edit.setEnabled(record.kind == BusinessRecordKind.PROPOSAL.value)

        if not record.margin_percent:
            self._recalculate_margin()

    def _recalculate_margin(self) -> None:
        try:
            total = self.total_spin.value()
            profit = self.profit_spin.value()
        except ValueError:
            return
        result = derive_margin(parse_money(total), parse_money(profit))
        margin = result.value if result.value is not None else Decimal("0")
        self.margin_spin.blockSignals(True)
        self.margin_spin.setValue(margin)
        self.margin_spin.blockSignals(False)

    def _set_initial_kind(
        self,
        kind: BusinessRecordKind | str,
    ) -> None:
        target = BusinessRecordKind(kind).value
        index = self.kind_combo.findData(target)
        if index >= 0:
            self.kind_combo.setCurrentIndex(index)
        self._refresh_statuses()

    def _refresh_statuses(self) -> None:
        kind = BusinessRecordKind(str(self.kind_combo.currentData()))
        current = self.status_combo.currentData()
        self.status_combo.clear()

        for status in statuses_for_kind(kind):
            self.status_combo.addItem(
                STATUS_LABELS[status],
                status.value,
            )

        preferred = {
            BusinessRecordKind.ESTIMATE: BusinessStatus.DRAFT,
            BusinessRecordKind.PROPOSAL: BusinessStatus.DRAFT,
            BusinessRecordKind.PROJECT: BusinessStatus.PLANNED,
        }[kind]
        index = self.status_combo.findData(current or preferred.value)
        self.status_combo.setCurrentIndex(max(0, index))

        is_proposal = kind == BusinessRecordKind.PROPOSAL
        self.file_edit.setEnabled(is_proposal)

    def _browse_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите документ",
            str(Path.home()),
            "Документы (*.docx *.xlsx *.pdf);;Все файлы (*.*)",
        )
        if filename:
            self.file_edit.setText(filename)

    def _validate_and_accept(self) -> None:
        if not self.tender_edit.text().strip():
            QMessageBox.warning(
                self,
                "Не заполнено поле",
                "Укажите ID или номер тендера.",
            )
            self.tender_edit.setFocus()
            return

        if not self.title_edit.text().strip():
            QMessageBox.warning(
                self,
                "Не заполнено поле",
                "Укажите наименование записи.",
            )
            self.title_edit.setFocus()
            return

        try:
            self.payload()
        except ValueError as exc:
            QMessageBox.warning(
                self,
                "Некорректное финансовое значение",
                str(exc),
            )
            return

        self.accept()


__all__ = ["BusinessRecordDialog", "DecimalValueEdit"]
