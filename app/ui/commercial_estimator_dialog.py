"""C18 commercial-estimate editor with explicit evidence and missing data."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html import escape

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.tenders.commercial_estimator import (
    CommercialCostCategory,
    CommercialCostLine,
    CommercialEstimateDraft,
    CommercialEstimateRepository,
    CommercialEstimateResult,
    CommercialEstimator,
    CommercialEvidence,
    REQUIRED_COST_CATEGORIES,
)
from app.tenders.models import UnifiedTender


class CommercialEstimatorDialog(QDialog):
    def __init__(
        self,
        registry_key: str,
        repository: CommercialEstimateRepository,
        *,
        tender: UnifiedTender | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.registry_key = registry_key.strip()
        self.repository = repository
        self.tender = tender
        self.estimator = CommercialEstimator()
        self.setWindowTitle("Corteris Tender AI — коммерческий расчёт C18")
        self.resize(1050, 720)

        root = QVBoxLayout(self)
        reference = (
            f"Справочная НМЦК: {tender.price.amount} {tender.price.currency}. "
            if tender is not None and tender.price is not None
            else "Справочная НМЦК отсутствует. "
        )
        note = QLabel(
            reference
            + "НМЦК не подставляется как цена предложения. Заполняйте только "
            "подтверждённые суммы; неизвестные значения оставляйте пустыми.",
            self,
        )
        note.setWordWrap(True)
        root.addWidget(note)

        self.table = QTableWidget(len(REQUIRED_COST_CATEGORIES), 4, self)
        self.table.setHorizontalHeaderLabels(
            ("Статья", "Сумма, RUB", "Источник/основание", "Подтверждённый ноль")
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._amounts: dict[CommercialCostCategory, QLineEdit] = {}
        self._sources: dict[CommercialCostCategory, QLineEdit] = {}
        self._zeros: dict[CommercialCostCategory, QCheckBox] = {}
        for row, category in enumerate(REQUIRED_COST_CATEGORIES):
            self.table.setItem(row, 0, QTableWidgetItem(_category_label(category)))
            amount = QLineEdit(self.table)
            amount.setPlaceholderText("неизвестно")
            source = QLineEdit(self.table)
            source.setPlaceholderText("счёт поставщика, смета, расчёт…")
            zero = QCheckBox(self.table)
            zero.toggled.connect(lambda checked, field=amount: field.setEnabled(not checked))
            self.table.setCellWidget(row, 1, amount)
            self.table.setCellWidget(row, 2, source)
            self.table.setCellWidget(row, 3, zero)
            self._amounts[category] = amount
            self._sources[category] = source
            self._zeros[category] = zero
        root.addWidget(self.table, 1)

        commercial = QHBoxLayout()
        self.revenue = QLineEdit(self)
        self.revenue.setPlaceholderText("Предложенная цена, RUB")
        self.revenue_source = QLineEdit(self)
        self.revenue_source.setPlaceholderText("Основание предложенной цены")
        self.advance = QLineEdit(self)
        self.advance.setPlaceholderText("Аванс, %")
        self.payment_days = QSpinBox(self)
        self.payment_days.setRange(-1, 3650)
        self.payment_days.setSpecialValueText("неизвестно")
        self.payment_days.setValue(-1)
        self.payment_source = QLineEdit(self)
        self.payment_source.setPlaceholderText("Документ с условиями оплаты")
        self.target_margin = QLineEdit(self)
        self.target_margin.setPlaceholderText("Целевая маржа, %")
        for widget in (
            self.revenue, self.revenue_source, self.advance,
            self.payment_days, self.payment_source, self.target_margin,
        ):
            commercial.addWidget(widget)
        root.addLayout(commercial)

        self.result_view = QTextBrowser(self)
        root.addWidget(self.result_view, 1)

        actions = QHBoxLayout()
        calculate = QPushButton("Рассчитать и сохранить", self)
        close = QPushButton("Закрыть", self)
        calculate.clicked.connect(self.calculate_and_save)
        close.clicked.connect(self.close)
        actions.addStretch(1)
        actions.addWidget(calculate)
        actions.addWidget(close)
        root.addLayout(actions)
        self.load_latest()

    def load_latest(self) -> None:
        latest = self.repository.latest(self.registry_key)
        if latest is None:
            self.result_view.setHtml(
                "<p>Расчёт ещё не создан. Все неизвестные данные останутся "
                "в списке недостающих сведений.</p>"
            )
            return
        draft, result = latest
        for line in draft.lines:
            if line.category in self._amounts and line.unit_cost is not None:
                self._amounts[line.category].setText(str(line.total))
                self._sources[line.category].setText(
                    line.evidence.source if line.evidence else ""
                )
        for category in draft.confirmed_zero_categories:
            self._zeros[category].setChecked(True)
        self.revenue.setText(_text_decimal(draft.proposed_revenue))
        self.revenue_source.setText(
            draft.revenue_evidence.source if draft.revenue_evidence else ""
        )
        self.advance.setText(_text_decimal(draft.advance_percent))
        self.payment_days.setValue(
            draft.payment_delay_days if draft.payment_delay_days is not None else -1
        )
        self.payment_source.setText(
            draft.payment_evidence.source if draft.payment_evidence else ""
        )
        self.target_margin.setText(_text_decimal(draft.target_margin_percent))
        self._show_result(result)

    def build_draft(self) -> CommercialEstimateDraft:
        lines = []
        zeroes = []
        zero_evidence = []
        for category in REQUIRED_COST_CATEGORIES:
            if self._zeros[category].isChecked():
                if not self._sources[category].text().strip():
                    raise ValueError(
                        f"Для нулевой статьи «{_category_label(category)}» укажите основание."
                    )
                zeroes.append(category)
                zero_evidence.append((
                    category,
                    CommercialEvidence(self._sources[category].text().strip()),
                ))
                continue
            amount = _optional_decimal(self._amounts[category].text())
            source = self._sources[category].text().strip()
            if amount is not None and not source:
                raise ValueError(
                    f"Для статьи «{_category_label(category)}» укажите источник суммы."
                )
            if amount is not None or source:
                lines.append(CommercialCostLine(
                    line_id=category.value,
                    category=category,
                    description=_category_label(category),
                    quantity=Decimal("1"),
                    unit_cost=amount,
                    evidence=CommercialEvidence(source) if source else None,
                ))
        revenue = _optional_decimal(self.revenue.text())
        revenue_source = self.revenue_source.text().strip()
        advance = _optional_decimal(self.advance.text())
        payment_days = self.payment_days.value()
        payment_source = self.payment_source.text().strip()
        return CommercialEstimateDraft(
            registry_key=self.registry_key,
            lines=tuple(lines),
            confirmed_zero_categories=tuple(zeroes),
            confirmed_zero_evidence=tuple(zero_evidence),
            proposed_revenue=revenue,
            revenue_evidence=CommercialEvidence(revenue_source) if revenue is not None else None,
            advance_percent=advance,
            payment_delay_days=payment_days if payment_days >= 0 else None,
            payment_evidence=(
                CommercialEvidence(payment_source)
                if advance is not None or payment_days >= 0
                else None
            ),
            target_margin_percent=_optional_decimal(self.target_margin.text()),
        )

    def calculate_and_save(self) -> None:
        try:
            draft = self.build_draft()
            result = self.repository.save(draft, self.estimator.calculate(draft))
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Коммерческий расчёт", str(exc))
            return
        self._show_result(result)

    def _show_result(self, result: CommercialEstimateResult) -> None:
        missing = "".join(f"<li>{escape(item)}</li>" for item in result.missing_data) or "<li>Нет</li>"
        warnings = "".join(f"<li>{escape(item)}</li>" for item in result.warnings) or "<li>Нет</li>"
        self.result_view.setHtml(
            f"<h2>{escape(result.status.value)}</h2>"
            f"<p><b>Подтверждённые затраты:</b> {result.known_cost} RUB</p>"
            f"<p><b>Полная себестоимость:</b> {_display(result.total_cost)}</p>"
            f"<p><b>Выручка:</b> {_display(result.proposed_revenue)}</p>"
            f"<p><b>Прибыль:</b> {_display(result.profit)}</p>"
            f"<p><b>Маржа:</b> {_display(result.margin_percent, suffix='%')}</p>"
            f"<p><b>Потребность в финансировании:</b> {_display(result.financing_exposure)}</p>"
            f"<h3>Недостающие данные</h3><ul>{missing}</ul>"
            f"<h3>Предупреждения</h3><ul>{warnings}</ul>"
        )


def _optional_decimal(value: str) -> Decimal | None:
    rendered = value.strip().replace(" ", "").replace(",", ".")
    if not rendered:
        return None
    try:
        return Decimal(rendered)
    except InvalidOperation as exc:
        raise ValueError(f"Некорректное число: {value}") from exc


def _text_decimal(value: Decimal | None) -> str:
    return str(value) if value is not None else ""


def _display(value: Decimal | None, *, suffix: str = " RUB") -> str:
    return f"{value}{suffix}" if value is not None else "не рассчитано"


def _category_label(category: CommercialCostCategory) -> str:
    return {
        CommercialCostCategory.EQUIPMENT: "Оборудование",
        CommercialCostCategory.INSTALLATION: "Монтаж",
        CommercialCostCategory.LOGISTICS: "Логистика",
        CommercialCostCategory.TRAVEL: "Командировки",
        CommercialCostCategory.WARRANTY: "Гарантия",
        CommercialCostCategory.SUBCONTRACT: "Субподряд",
        CommercialCostCategory.WORKING_CAPITAL: "Оборотный капитал",
        CommercialCostCategory.BANK_GUARANTEE: "Банковская гарантия",
    }[category]


__all__ = ["CommercialEstimatorDialog"]
