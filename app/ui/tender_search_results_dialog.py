"""Search-results dialog for Corteris tender profile runs."""

from __future__ import annotations

from html import escape
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
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.tenders.corteris_filter import (
    EvaluatedTender,
    TenderDirection,
)
from app.tenders.search_profile_runner import TenderSearchProfileRun
from app.ui.theme.colors import ThemeName, get_palette


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

    def __init__(
        self,
        run: TenderSearchProfileRun,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.run = run
        self._theme = ThemeName(theme)
        self._evaluated = tuple(run.result.filter_result.accepted)

        self.setWindowTitle(
            f"Corteris Tender AI — {run.profile.name}"
        )
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
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.itemSelectionChanged.connect(
            self._show_selected_details
        )
        self.table.cellDoubleClicked.connect(
            lambda _row, _column: self._open_selected_source()
        )
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

        self.details = QTextBrowser(details_frame)
        self.details.setObjectName("TenderResultsDetails")
        self.details.setOpenExternalLinks(False)
        self.details.anchorClicked.connect(
            QDesktopServices.openUrl
        )
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
        self.provider_status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
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
        self.open_source_button.clicked.connect(
            self._open_selected_source
        )

        self.documents_button = QPushButton(
            "Скачать документацию",
            self,
        )
        self.documents_button.clicked.connect(
            self._request_selected_documents
        )

        self.rerun_button = QPushButton(
            "Повторить поиск",
            self,
        )
        self.rerun_button.clicked.connect(
            lambda: self.rerun_requested.emit(run.profile.id)
        )

        self.profiles_button = QPushButton(
            "Профили поиска",
            self,
        )
        self.profiles_button.clicked.connect(
            self.profiles_requested.emit
        )

        action_row.addWidget(self.open_source_button)
        action_row.addWidget(self.documents_button)
        action_row.addWidget(self.rerun_button)
        action_row.addWidget(self.profiles_button)
        action_row.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).setText("Закрыть")
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
            self.run.profile.description
            or "Поиск по сохранённому профилю.",
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
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        row,
                    )
                self.table.setItem(row, column, item)

        if self._evaluated:
            self.table.selectRow(0)
            self._show_selected_details()
            self.open_source_button.setEnabled(True)
            self.documents_button.setEnabled(True)
        else:
            self.details.setHtml(
                "<h3>Подходящих закупок не найдено</h3>"
                "<p>Измените профиль, период, регионы или "
                "минимальную релевантность и повторите поиск.</p>"
            )
            self.open_source_button.setEnabled(False)
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
            self.documents_button.setEnabled(False)
            return

        self.open_source_button.setEnabled(True)
        self.documents_button.setEnabled(True)
        tender = evaluated.tender
        relevance = evaluated.relevance
        directions = ", ".join(
            _DIRECTION_LABELS.get(direction, direction.value)
            for direction in relevance.directions
        ) or "Не определено"
        strong_terms = ", ".join(
            relevance.matched_strong_terms
        ) or "—"
        reasons = "".join(
            f"<li>{escape(reason)}</li>"
            for reason in relevance.reasons
        ) or "<li>Дополнительные причины не сформированы.</li>"
        description = tender.description.strip() or (
            "Описание отсутствует в поисковой выдаче. "
            "Откройте официальную карточку закупки."
        )

        self.details.setHtml(
            f"<h2>{escape(tender.title)}</h2>"
            f"<p><b>Номер:</b> "
            f"{escape(tender.procurement_number)}</p>"
            f"<p><b>Заказчик:</b> "
            f"{escape(tender.customer.name)}</p>"
            f"<p><b>Регион:</b> "
            f"{escape(tender.region or tender.customer.region or '—')}</p>"
            f"<p><b>Цена:</b> {escape(_format_price(tender))}</p>"
            f"<p><b>Срок подачи:</b> "
            f"{escape(_format_deadline(tender.application_deadline))}</p>"
            f"<p><b>Закон:</b> {escape(tender.law or '—')}</p>"
            f"<p><b>Релевантность:</b> "
            f"{relevance.score}/100</p>"
            f"<p><b>Направления:</b> {escape(directions)}</p>"
            f"<p><b>Ключевые совпадения:</b> "
            f"{escape(strong_terms)}</p>"
            f"<h3>Описание</h3><p>{escape(description)}</p>"
            f"<h3>Почему закупка подходит</h3><ul>{reasons}</ul>"
            f"<p><a href=\"{escape(tender.source_url)}\">"
            "Открыть официальную карточку</a></p>"
        )

    def _provider_status_text(self) -> str:
        outcomes = self.run.result.provider_result.outcomes
        if not outcomes:
            return "Информация об источниках отсутствует."

        lines: list[str] = []
        for outcome in outcomes:
            status = outcome.status.value
            details = outcome.error_message or (
                f"результатов: {outcome.item_count}"
            )
            lines.append(
                f"• {outcome.display_name}: {status}; {details}"
            )
        return "\n".join(lines)

    def _request_selected_documents(self) -> None:
        evaluated = self.selected_evaluated()
        if evaluated is None:
            return
        self.documents_requested.emit(evaluated.tender)

    def _open_selected_source(self) -> None:
        evaluated = self.selected_evaluated()
        if evaluated is None:
            return
        QDesktopServices.openUrl(
            QUrl(evaluated.tender.source_url)
        )

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
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


def _format_price(tender) -> str:
    if tender.price is None:
        return "Не указана"
    amount = f"{tender.price.amount:,.2f}"
    amount = amount.replace(",", " ").replace(".00", "")
    currency = tender.price.currency or "RUB"
    symbol = "₽" if currency.upper() == "RUB" else currency.upper()
    return f"{amount} {symbol}"


def _format_deadline(value) -> str:
    if value is None:
        return "Не указан"
    return value.strftime("%d.%m.%Y %H:%M")


__all__ = ["TenderSearchResultsDialog"]
