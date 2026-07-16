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

from app.tenders.business_profile import BusinessCapabilityProjection
from app.tenders.collector.company_capability import (
    CompanyCapabilityLoadResult,
    CompanyCapabilityLoadStatus,
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
        self.load_result: CompanyCapabilityLoadResult
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
        self.company_name.textChanged.connect(self._invalidate_confirmation)
        form.addRow("Компания", self.company_name)
        for name, label in _TEXT_FIELDS.items():
            edit = QLineEdit(content)
            edit.setPlaceholderText("Значения через ;")
            edit.textChanged.connect(self._invalidate_confirmation)
            self.text_fields[name] = edit
            form.addRow(label, edit)

        self.crew_count = QSpinBox(content)
        self.crew_count.setRange(-1, 10000)
        self.crew_count.setSpecialValueText("Не указано")
        self.crew_count.valueChanged.connect(self._invalidate_confirmation)
        form.addRow("Количество монтажных бригад", self.crew_count)

        for name, label in _MONEY_FIELDS.items():
            edit = QLineEdit(content)
            edit.setPlaceholderText("Не указано")
            edit.textChanged.connect(self._invalidate_confirmation)
            self.money_fields[name] = edit
            form.addRow(label, edit)

        self.base_currency = QLineEdit(content)
        self.base_currency.setMaxLength(3)
        self.base_currency.setPlaceholderText("RUB")
        self.base_currency.textChanged.connect(self._invalidate_confirmation)
        form.addRow("Базовая валюта (ISO 4217)", self.base_currency)

        self.payment_days = QSpinBox(content)
        self.payment_days.setRange(-1, 3650)
        self.payment_days.setSpecialValueText("Не указано")
        self.payment_days.valueChanged.connect(self._invalidate_confirmation)
        form.addRow("Допустимый срок оплаты, дней", self.payment_days)
        self.deferment_days = QSpinBox(content)
        self.deferment_days.setRange(-1, 3650)
        self.deferment_days.setSpecialValueText("Не указано")
        self.deferment_days.valueChanged.connect(self._invalidate_confirmation)
        form.addRow("Максимальная отсрочка, дней", self.deferment_days)

        self.designers = QComboBox(content)
        self.designers.addItem("Не указано", None)
        self.designers.addItem("Есть", True)
        self.designers.addItem("Нет", False)
        self.designers.currentIndexChanged.connect(self._invalidate_confirmation)
        form.addRow("Проектировщики", self.designers)

        self.evidence_note = QLineEdit(content)
        self.evidence_note.textChanged.connect(self._invalidate_confirmation)
        form.addRow("Основание подтверждения", self.evidence_note)
        self.confirmed_by = QLineEdit(content)
        self.confirmed_by.textChanged.connect(self._invalidate_confirmation)
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
        self.load_result = self.repository.load_result()
        profile = self.load_result.profile
        self.company_name.setText(profile.company_name)
        for name, edit in self.text_fields.items():
            edit.setText("; ".join(getattr(profile, name)))
        self.crew_count.setValue(
            profile.installation_crew_count if profile.installation_crew_count is not None else -1
        )
        for name, edit in self.money_fields.items():
            value = getattr(profile, name)
            edit.setText(str(value) if value is not None else "")
        self.base_currency.setText(profile.base_currency)
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
        self._show_profile_status(profile, load_result=self.load_result)

    def build_profile(self) -> CompanyCapabilityProfile:
        if not self.confirmation.isChecked():
            raise ValueError("Подтвердите достоверность сведений")
        values: dict[str, object] = {name: edit.text() for name, edit in self.text_fields.items()}
        values.update({name: _decimal_from_edit(edit) for name, edit in self.money_fields.items()})
        draft = CompanyCapabilityProfile(
            company_name=self.company_name.text().strip(),
            installation_crew_count=_int_from_spin(self.crew_count),
            acceptable_payment_days=_int_from_spin(self.payment_days),
            maximum_deferment_days=_int_from_spin(self.deferment_days),
            has_designers=self.designers.currentData(),
            base_currency=self.base_currency.text().strip(),
            **values,
        )
        return draft.confirm(
            confirmed_by=self.confirmed_by.text().strip(),
            confirmed_at=datetime.now(timezone.utc),
            evidence_note=self.evidence_note.text().strip(),
        )

    def save_profile(self) -> None:
        try:
            profile = self.build_profile()
            self.repository.save(profile)
            self.load_result = self.repository.load_result()
            stored = self.load_result.profile
        except Exception as exc:
            QMessageBox.warning(self, "Возможности компании", str(exc))
            return
        self.confirmation.setChecked(stored.is_confirmed)
        self._show_profile_status(stored, load_result=self.load_result)
        self.profile_saved.emit(stored)

    def _show_profile_status(
        self,
        profile: CompanyCapabilityProfile,
        *,
        load_result: CompanyCapabilityLoadResult | None = None,
    ) -> None:
        result = load_result
        if result is not None and result.status is CompanyCapabilityLoadStatus.CORRUPT:
            self.status.setText(
                "Файл профиля повреждён. Исходный файл сохранён без изменений; "
                "восстановите корректную копию перед сохранением."
            )
            return
        if result is not None and result.status is CompanyCapabilityLoadStatus.UNSUPPORTED_FUTURE:
            version = (
                str(result.source_schema_version)
                if result.source_schema_version is not None
                else "неизвестна"
            )
            self.status.setText(
                "Версия файла профиля "
                f"({version}) новее поддерживаемой. Файл сохранён без изменений."
            )
            return

        projection = BusinessCapabilityProjection.from_capability(profile)
        prefix = ""
        if result is not None and result.status is CompanyCapabilityLoadStatus.MIGRATED_V1:
            prefix = (
                "Профиль schema v1 безопасно загружен в памяти; "
                "явное сохранение обновит его до schema v2. "
            )
        if projection.is_configured and not projection.missing_sections:
            message = "Профиль подтверждён и заполнен."
        elif projection.is_configured:
            message = (
                "Профиль подтверждён. Не заполнено: " + ", ".join(projection.missing_sections) + "."
            )
        else:
            message = "Недостаточно данных о возможностях компании."
        self.status.setText(prefix + message)

    def _invalidate_confirmation(self, *_args: object) -> None:
        self.confirmation.setChecked(False)
        if hasattr(self, "status"):
            self.status.setText("Изменения требуют нового явного подтверждения.")


def _int_from_spin(spin: QSpinBox) -> int | None:
    return None if spin.value() < 0 else spin.value()


def _decimal_from_edit(edit: QLineEdit) -> Decimal | None:
    rendered = edit.text().strip().replace(" ", "").replace(",", ".")
    return None if not rendered else Decimal(rendered)


__all__ = ["CompanyCapabilityDialog"]
