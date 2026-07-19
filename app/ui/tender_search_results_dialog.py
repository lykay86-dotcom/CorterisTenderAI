"""Search-results dialog for Corteris tender profile runs."""

from __future__ import annotations

from datetime import datetime
from typing import Final

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.financial import CurrencyCode, FinancialValueState, MoneyAmount, format_money
from app.tenders.corteris_filter import (
    EvaluatedTender,
    TenderDirection,
)
from app.tenders.detail import (
    TenderDetailAssembler,
    TenderDetailState,
    TenderIdentity,
    TenderIdentityKind,
    validate_https_url,
)
from app.tenders.search_profile_runner import TenderSearchProfileRun
from app.tenders.models import UnifiedTender
from app.tenders.tender_registry import tender_registry_key
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.widgets.tender_detail import TenderDetailHost


_DIRECTION_LABELS: Final[dict[TenderDirection, str]] = {
    TenderDirection.VIDEO_SURVEILLANCE: "Видеонаблюдение",
    TenderDirection.OPS: "ОПС",
    TenderDirection.SKUD: "СКУД",
    TenderDirection.BARRIERS: "Шлагбаумы",
    TenderDirection.ANPR: "Распознавание номеров",
    TenderDirection.MAINTENANCE: "Обслуживание",
    TenderDirection.INTEGRATED_SECURITY: "Комплексная безопасность",
}


class TenderSearchResultsDialog(QDialog):
    """Display ranked tenders and provider diagnostics."""

    rerun_requested = Signal(str)
    profiles_requested = Signal()
    documents_requested = Signal(object)
    full_analysis_requested = Signal(object)
    registry_action_requested = Signal(str, str)

    def __init__(
        self,
        run: TenderSearchProfileRun,
        *,
        detail_assembler: TenderDetailAssembler | None = None,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.run = run
        self._theme = ThemeName(theme)
        self._detail_assembler = detail_assembler
        self._evaluated = tuple(run.result.filter_result.accepted)

        self.setWindowTitle(f"Corteris Tender AI — {run.profile.name}")
        self.setModal(False)
        self.resize(1380, 820)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        root.addWidget(self._build_summary())

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        table_frame = QFrame(splitter)
        table_frame.setObjectName("TenderResultsTableFrame")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        table_heading = QLabel("Релевантные закупки", table_frame)
        table_heading.setObjectName("TenderResultsSectionTitle")
        table_layout.addWidget(table_heading)

        self.table = QTableWidget(table_frame)
        self.table.setObjectName("TenderResultsTable")
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            (
                "Балл",
                "Направления",
                "Номер",
                "Закупка",
                "Заказчик",
                "Регион",
                "Цена",
                "Срок подачи",
                "Источник",
            )
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.itemSelectionChanged.connect(self._show_selected_details)
        table_layout.addWidget(self.table, 1)
        splitter.addWidget(table_frame)

        details_frame = QFrame(splitter)
        details_frame.setObjectName("TenderResultsDetailsFrame")
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setSpacing(8)

        details_heading = QLabel("Карточка закупки", details_frame)
        details_heading.setObjectName("TenderResultsSectionTitle")
        details_layout.addWidget(details_heading)

        self.details = TenderDetailHost(theme=self._theme, parent=details_frame)
        self.details.setObjectName("TenderResultsDetails")
        self.details.action_requested.connect(self._request_registry_detail_action)
        details_layout.addWidget(self.details, 1)

        provider_heading = QLabel(
            "Состояние источников",
            details_frame,
        )
        provider_heading.setObjectName("TenderResultsSectionTitle")
        details_layout.addWidget(provider_heading)

        self.provider_status = QLabel(
            self._provider_status_text(),
            details_frame,
        )
        self.provider_status.setObjectName("TenderProviderStatus")
        self.provider_status.setWordWrap(True)
        self.provider_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self.provider_status)
        splitter.addWidget(details_frame)
        splitter.setSizes([960, 420])

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.open_source_button = QPushButton(
            "Открыть закупку в источнике",
            self,
        )
        self.open_source_button.setObjectName("PrimaryActionButton")
        self.open_source_button.clicked.connect(self._open_selected_source)

        self.full_analysis_button = QPushButton(
            "Скачать документы и провести полный анализ",
            self,
        )
        self.full_analysis_button.setObjectName("PrimaryActionButton")
        self.full_analysis_button.clicked.connect(self._request_selected_full_analysis)

        self.documents_button = QPushButton(
            "Скачать документацию",
            self,
        )
        self.documents_button.clicked.connect(self._request_selected_documents)

        self.rerun_button = QPushButton(
            "Повторить поиск",
            self,
        )
        self.rerun_button.clicked.connect(lambda: self.rerun_requested.emit(run.profile.id))

        self.profiles_button = QPushButton(
            "Профили поиска",
            self,
        )
        self.profiles_button.clicked.connect(self.profiles_requested.emit)

        action_row.addWidget(self.open_source_button)
        action_row.addWidget(self.full_analysis_button)
        action_row.addWidget(self.documents_button)
        action_row.addWidget(self.rerun_button)
        action_row.addWidget(self.profiles_button)
        action_row.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)
        action_row.addWidget(buttons)
        root.addLayout(action_row)

        self._populate_table()
        self.apply_theme(self._theme)

    def _build_summary(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("TenderResultsSummary")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(20)

        title_column = QVBoxLayout()
        title = QLabel(self.run.profile.name, frame)
        title.setObjectName("TenderResultsTitle")
        description = QLabel(
            self.run.profile.description or "Поиск по сохранённому профилю.",
            frame,
        )
        description.setObjectName("TenderResultsSubtitle")
        description.setWordWrap(True)
        title_column.addWidget(title)
        title_column.addWidget(description)
        layout.addLayout(title_column, 1)

        provider_result = self.run.result.provider_result
        filter_result = self.run.result.filter_result
        metrics = (
            ("Найдено", str(provider_result.raw_item_count)),
            ("После объединения", str(len(provider_result.items))),
            ("Релевантно", str(filter_result.accepted_count)),
            ("Отсеяно", str(filter_result.rejected_count)),
            ("Дубли", str(provider_result.duplicate_count)),
        )
        for label, value in metrics:
            column = QVBoxLayout()
            metric_value = QLabel(value, frame)
            metric_value.setObjectName("TenderResultsMetricValue")
            metric_label = QLabel(label, frame)
            metric_label.setObjectName("TenderResultsMetricLabel")
            metric_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            metric_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(metric_value)
            column.addWidget(metric_label)
            layout.addLayout(column)

        return frame

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self._evaluated))

        for row, evaluated in enumerate(self._evaluated):
            tender = evaluated.tender
            relevance = evaluated.relevance
            directions = ", ".join(
                _DIRECTION_LABELS.get(direction, direction.value)
                for direction in relevance.directions
            )
            values = (
                str(relevance.score),
                directions or "—",
                tender.procurement_number,
                tender.title,
                tender.customer.name,
                tender.region or tender.customer.region or "—",
                _format_price(tender),
                _format_deadline(tender.application_deadline),
                tender.source.value,
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        row,
                    )
                self.table.setItem(row, column, item)

        if self._evaluated:
            self.table.selectRow(0)
            self._show_selected_details()
            self.open_source_button.setEnabled(True)
            self.full_analysis_button.setEnabled(True)
            self.documents_button.setEnabled(True)
        else:
            self.details.set_transient_preview(
                "Подходящих закупок не найдено. Измените профиль, период, "
                "регионы или минимальную релевантность и повторите поиск."
            )
            self.open_source_button.setEnabled(False)
            self.full_analysis_button.setEnabled(False)
            self.documents_button.setEnabled(False)

    def selected_evaluated(self) -> EvaluatedTender | None:
        row = self.table.currentRow()
        if not 0 <= row < len(self._evaluated):
            return None
        return self._evaluated[row]

    def _show_selected_details(self) -> None:
        evaluated = self.selected_evaluated()
        if evaluated is None:
            self.open_source_button.setEnabled(False)
            self.full_analysis_button.setEnabled(False)
            self.documents_button.setEnabled(False)
            return

        self.open_source_button.setEnabled(True)
        self.full_analysis_button.setEnabled(True)
        self.documents_button.setEnabled(True)
        tender = evaluated.tender
        safe_url = validate_https_url(tender.source_url)
        self.open_source_button.setEnabled(safe_url is not None)
        if self._detail_assembler is not None:
            identity = TenderIdentity(
                TenderIdentityKind.REGISTRY,
                tender_registry_key(tender),
            )
            snapshot = self._detail_assembler.assemble(identity)
            if snapshot.state not in {TenderDetailState.NOT_FOUND, TenderDetailState.ERROR}:
                self.details.set_entry_context(
                    f"Поисковая релевантность: {evaluated.relevance.score}/100 "
                    "(не решение об участии)"
                )
                self.details.set_snapshot(snapshot)
                return
        self.details.set_entry_context("")
        relevance = evaluated.relevance
        directions = (
            ", ".join(
                _DIRECTION_LABELS.get(direction, direction.value)
                for direction in relevance.directions
            )
            or "Не определено"
        )
        strong_terms = ", ".join(relevance.matched_strong_terms) or "—"
        reasons = "; ".join(relevance.reasons) or "Дополнительные причины не сформированы."
        description = tender.description.strip() or (
            "Описание отсутствует в поисковой выдаче. Откройте официальную карточку закупки."
        )

        self.details.set_transient_preview(
            "\n".join(
                (
                    tender.title,
                    f"Номер: {tender.procurement_number}",
                    f"Заказчик: {tender.customer.name}",
                    f"Регион: {tender.region or tender.customer.region or '—'}",
                    f"Цена: {_format_price(tender)}",
                    f"Срок подачи: {_format_deadline(tender.application_deadline)}",
                    f"Закон: {tender.law or '—'}",
                    f"Поисковая релевантность: {relevance.score}/100",
                    "Решение об участии: не загружено",
                    f"Направления: {directions}",
                    f"Ключевые совпадения: {strong_terms}",
                    f"Описание: {description}",
                    f"Почему результат релевантен: {reasons}",
                )
            )
        )

    def _provider_status_text(self) -> str:
        outcomes = self.run.result.provider_result.outcomes
        if not outcomes:
            return "Информация об источниках отсутствует."

        lines: list[str] = []
        for outcome in outcomes:
            status = outcome.status.value
            details = outcome.error_message or (f"результатов: {outcome.item_count}")
            lines.append(f"• {outcome.display_name}: {status}; {details}")
        return "\n".join(lines)

    def _request_registry_detail_action(self, action_id: str) -> None:
        snapshot = self.details.snapshot
        if snapshot is not None:
            self.registry_action_requested.emit(snapshot.identity.value, action_id)

    def _request_selected_full_analysis(self) -> None:
        evaluated = self.selected_evaluated()
        if evaluated is None:
            return
        self.full_analysis_requested.emit(evaluated.tender)

    def _request_selected_documents(self) -> None:
        evaluated = self.selected_evaluated()
        if evaluated is None:
            return
        self.documents_requested.emit(evaluated.tender)

    def _open_selected_source(self) -> None:
        evaluated = self.selected_evaluated()
        if evaluated is None:
            return
        safe_url = validate_https_url(evaluated.tender.source_url)
        if safe_url is not None:
            QDesktopServices.openUrl(QUrl(safe_url))

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        self.details.apply_theme(self._theme)
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {palette.app_background};
                color: {palette.text_primary};
            }}
            QFrame#TenderResultsSummary,
            QFrame#TenderResultsTableFrame,
            QFrame#TenderResultsDetailsFrame {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_default};
                border-radius: 9px;
            }}
            QLabel#TenderResultsTitle {{
                color: {palette.text_primary};
                font-size: 22px;
                font-weight: 700;
            }}
            QLabel#TenderResultsSubtitle,
            QLabel#TenderResultsMetricLabel,
            QLabel#TenderProviderStatus {{
                color: {palette.text_secondary};
            }}
            QLabel#TenderResultsMetricValue {{
                color: {palette.brand_accent};
                font-size: 22px;
                font-weight: 700;
            }}
            QLabel#TenderResultsSectionTitle {{
                color: {palette.text_primary};
                font-size: 14px;
                font-weight: 700;
            }}
            QTableWidget#TenderResultsTable {{
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
            QTextBrowser#TenderResultsDetails {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 7px;
            }}
            QPushButton {{
                min-height: 32px;
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
            QPushButton#PrimaryActionButton:hover {{
                background-color: {palette.brand_primary_hover};
            }}
            QSplitter::handle {{
                background-color: transparent;
                width: 8px;
            }}
            """
        )


def _format_price(tender: UnifiedTender) -> str:
    if tender.price is None:
        return "Не указана"
    currency = (
        CurrencyCode.RUB
        if tender.price.currency.strip().upper() == CurrencyCode.RUB.value
        else CurrencyCode.UNKNOWN
    )
    state = (
        FinancialValueState.AVAILABLE
        if currency is CurrencyCode.RUB
        else FinancialValueState.UNSUPPORTED_CURRENCY
    )
    return format_money(MoneyAmount(tender.price.amount, currency, state))


def _format_deadline(value: datetime | None) -> str:
    if value is None:
        return "Не указан"
    return value.strftime("%d.%m.%Y %H:%M")


__all__ = ["TenderSearchResultsDialog"]
