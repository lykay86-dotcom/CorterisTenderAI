"""Editor for the confirmed Corteris company capability profile."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.tenders.collector.company_capability import (
    CompanyCapabilityProfile,
    CompanyCapabilityProfileRepository,
)


_TEXT_FIELDS = {
    "business_directions": "Направления деятельности",
    "self_install_regions": "Регионы самостоятельного монтажа",
    "partner_regions": "Регионы с партнёрами",
    "licenses": "Лицензии",
    "license_work_types": "Виды работ в лицензиях",
    "sro_memberships": "СРО",
    "employee_qualifications": "Квалификации сотрудников",
    "completed_contracts": "Выполненные контракты",
    "confirmed_experience": "Подтверждённый опыт",
    "equipment": "Оборудование",
    "brands": "Бренды",
    "suppliers": "Поставщики",
    "stock_items": "Складские позиции",
    "self_performed_directions": "Работы своими силами",
    "subcontracted_directions": "Работы через субподряд",
    "undesired_object_types": "Нежелательные объекты",
    "regional_partners": "Региональные партнёры",
}

_MONEY_FIELDS = {
    "max_project_amount": "Максимальная сумма проекта",
    "working_capital": "Доступный оборотный капитал",
    "max_bid_security": "Максимальное обеспечение заявки",
    "max_contract_security": "Максимальное обеспечение контракта",
    "bank_guarantee_limit": "Лимит банковской гарантии",
    "minimum_margin_percent": "Минимальная маржинальность, %",
}


class CompanyCapabilityDialog(QDialog):
    profile_saved = Signal(object)

    def __init__(
        self,
        repository: CompanyCapabilityProfileRepository,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.text_fields: dict[str, QLineEdit] = {}
        self.money_fields: dict[str, QLineEdit] = {}
        self.setWindowTitle("Corteris Tender AI — возможности компании")
        self.resize(820, 760)

        root = QVBoxLayout(self)
        info = QLabel(
            "Сохраняйте только подтверждённые сведения. Пустые поля будут "
            "учтены рейтингом как недостаток данных.",
            self,
        )
        info.setWordWrap(True)
        root.addWidget(info)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        form = QFormLayout(content)

        self.company_name = QLineEdit(content)
        form.addRow("Компания", self.company_name)
        for name, label in _TEXT_FIELDS.items():
            edit = QLineEdit(content)
            edit.setPlaceholderText("Значения через ;")
            self.text_fields[name] = edit
            form.addRow(label, edit)

        self.crew_count = QSpinBox(content)
        self.crew_count.setRange(-1, 10000)
        self.crew_count.setSpecialValueText("Не указано")
        form.addRow("Количество монтажных бригад", self.crew_count)

        for name, label in _MONEY_FIELDS.items():
            edit = QLineEdit(content)
            edit.setPlaceholderText("Не указано")
            self.money_fields[name] = edit
            form.addRow(label, edit)

        self.payment_days = QSpinBox(content)
        self.payment_days.setRange(-1, 3650)
        self.payment_days.setSpecialValueText("Не указано")
        form.addRow("Допустимый срок оплаты, дней", self.payment_days)
        self.deferment_days = QSpinBox(content)
        self.deferment_days.setRange(-1, 3650)
        self.deferment_days.setSpecialValueText("Не указано")
        form.addRow("Максимальная отсрочка, дней", self.deferment_days)

        self.designers = QComboBox(content)
        self.designers.addItem("Не указано", None)
        self.designers.addItem("Есть", True)
        self.designers.addItem("Нет", False)
        form.addRow("Проектировщики", self.designers)

        self.evidence_note = QLineEdit(content)
        form.addRow("Основание подтверждения", self.evidence_note)
        self.confirmed_by = QLineEdit(content)
        form.addRow("Подтвердил", self.confirmed_by)
        self.confirmation = QCheckBox(
            "Подтверждаю, что сохранённые сведения проверены",
            content,
        )
        form.addRow("", self.confirmation)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.status = QLabel("", self)
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрыть")
        buttons.accepted.connect(self.save_profile)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.load_profile()

    def load_profile(self) -> None:
        profile = self.repository.load()
        self.company_name.setText(profile.company_name)
        for name, edit in self.text_fields.items():
            edit.setText("; ".join(getattr(profile, name)))
        self.crew_count.setValue(
            profile.installation_crew_count if profile.installation_crew_count is not None else -1
        )
        for name, edit in self.money_fields.items():
            value = getattr(profile, name)
            edit.setText(str(value) if value is not None else "")
        self.payment_days.setValue(
            profile.acceptable_payment_days if profile.acceptable_payment_days is not None else -1
        )
        self.deferment_days.setValue(
            profile.maximum_deferment_days if profile.maximum_deferment_days is not None else -1
        )
        index = self.designers.findData(profile.has_designers)
        self.designers.setCurrentIndex(max(0, index))
        self.evidence_note.setText(profile.evidence_note)
        self.confirmed_by.setText(profile.confirmed_by)
        self.confirmation.setChecked(profile.is_confirmed)
        self._show_profile_status(profile)

    def build_profile(self) -> CompanyCapabilityProfile:
        if not self.confirmation.isChecked():
            raise ValueError("Подтвердите достоверность сведений")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        values: dict[str, object] = {name: edit.text() for name, edit in self.text_fields.items()}
        values.update({name: _decimal_from_edit(edit) for name, edit in self.money_fields.items()})
        return CompanyCapabilityProfile(
            company_name=self.company_name.text().strip(),
            installation_crew_count=_int_from_spin(self.crew_count),
            acceptable_payment_days=_int_from_spin(self.payment_days),
            maximum_deferment_days=_int_from_spin(self.deferment_days),
            has_designers=self.designers.currentData(),
            evidence_note=self.evidence_note.text().strip(),
            confirmed_by=self.confirmed_by.text().strip(),
            confirmed_at=now,
            updated_at=now,
            **values,
        )

    def save_profile(self) -> None:
        try:
            profile = self.build_profile()
            self.repository.save(profile)
            stored = self.repository.load()
        except Exception as exc:
            QMessageBox.warning(self, "Возможности компании", str(exc))
            return
        self._show_profile_status(stored)
        self.profile_saved.emit(stored)

    def _show_profile_status(self, profile: CompanyCapabilityProfile) -> None:
        if profile.is_configured and not profile.missing_sections:
            self.status.setText("Профиль подтверждён и заполнен.")
        elif profile.is_configured:
            self.status.setText(
                "Профиль подтверждён. Не заполнено: " + ", ".join(profile.missing_sections) + "."
            )
        else:
            self.status.setText("Недостаточно данных о возможностях компании.")


def _int_from_spin(spin: QSpinBox) -> int | None:
    return None if spin.value() < 0 else spin.value()


def _decimal_from_edit(edit: QLineEdit) -> Decimal | None:
    rendered = edit.text().strip().replace(" ", "").replace(",", ".")
    return None if not rendered else Decimal(rendered)


__all__ = ["CompanyCapabilityDialog"]
