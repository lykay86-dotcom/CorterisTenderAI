"""Dialogs for creating business workflow records."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
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

from app.repositories.business_metrics import (
    BusinessRecordKind,
    BusinessStatus,
)
from app.ui.business_workflow.model import (
    KIND_LABELS,
    STATUS_LABELS,
    statuses_for_kind,
)
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography


class BusinessRecordDialog(QDialog):
    """Create one estimate, proposal or project record."""

    def __init__(
        self,
        *,
        initial_kind: BusinessRecordKind | str = (
            BusinessRecordKind.PROPOSAL
        ),
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self.setWindowTitle("Новая запись бизнес-процесса")
        self.setModal(True)
        self.resize(560, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(16)

        title = QLabel("Новая запись", self)
        title.setObjectName("BusinessDialogTitle")

        subtitle = QLabel(
            "Добавьте КП, смету или проект для синхронизации "
            "с Dashboard.",
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
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.kind_combo = QComboBox(self)
        for kind, label in KIND_LABELS.items():
            self.kind_combo.addItem(label, kind.value)

        self.tender_edit = QLineEdit(self)
        self.tender_edit.setPlaceholderText("ID или номер тендера")

        self.title_edit = QLineEdit(self)
        self.title_edit.setPlaceholderText(
            "Например: КП на систему видеонаблюдения"
        )

        self.status_combo = QComboBox(self)

        self.total_spin = self._money_spin()
        self.profit_spin = self._money_spin()

        self.margin_spin = QDoubleSpinBox(self)
        self.margin_spin.setRange(-100.0, 1000.0)
        self.margin_spin.setDecimals(2)
        self.margin_spin.setSuffix(" %")

        self.due_edit = QLineEdit(self)
        self.due_edit.setPlaceholderText("YYYY-MM-DD или ДД.ММ.ГГГГ")

        self.file_edit = QLineEdit(self)
        self.file_edit.setPlaceholderText(
            "Путь к сформированному документу"
        )
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
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.button(
            QDialogButtonBox.StandardButton.Save
        ).setText("Сохранить")
        self.buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText("Отмена")
        self.buttons.accepted.connect(self._validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.kind_combo.currentIndexChanged.connect(
            self._refresh_statuses
        )
        self._set_initial_kind(initial_kind)
        self.apply_theme(self._theme)

    def payload(self) -> dict[str, object]:
        return {
            "kind": BusinessRecordKind(
                str(self.kind_combo.currentData())
            ),
            "tender_id": self.tender_edit.text().strip(),
            "title": self.title_edit.text().strip(),
            "status": BusinessStatus(
                str(self.status_combo.currentData())
            ),
            "total": Decimal(str(self.total_spin.value())),
            "profit": Decimal(str(self.profit_spin.value())),
            "margin_percent": Decimal(
                str(self.margin_spin.value())
            ),
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
            QLineEdit, QComboBox, QDoubleSpinBox {{
                min-height: 34px;
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 4px 8px;
                {Typography.BODY_S.css()}
            }}
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{
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
    def _money_spin() -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 10_000_000_000)
        spin.setDecimals(2)
        spin.setSingleStep(10_000)
        spin.setSuffix(" ₽")
        return spin

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
        kind = BusinessRecordKind(
            str(self.kind_combo.currentData())
        )
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
        index = self.status_combo.findData(
            current or preferred.value
        )
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

        self.accept()


__all__ = ["BusinessRecordDialog"]
