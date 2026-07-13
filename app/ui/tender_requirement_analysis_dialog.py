"""UI for structured tender-requirement analysis results."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.tenders.requirement_analysis import (
    AnalysisRiskLevel,
    DocumentKind,
    FindingSeverity,
    RequirementCategory,
    RequirementFinding,
    TenderRequirementAnalysis,
)
from app.ui.theme.colors import ThemeName, get_palette


_RISK_LABELS = {
    AnalysisRiskLevel.LOW: "Низкий",
    AnalysisRiskLevel.MEDIUM: "Средний",
    AnalysisRiskLevel.HIGH: "Высокий",
    AnalysisRiskLevel.CRITICAL: "Критический",
}

_SEVERITY_LABELS = {
    FindingSeverity.INFO: "Информация",
    FindingSeverity.WARNING: "Внимание",
    FindingSeverity.CRITICAL: "Критично",
}

_CATEGORY_LABELS = {
    RequirementCategory.DOCUMENT: "Документы",
    RequirementCategory.LICENSE: "Лицензии и допуски",
    RequirementCategory.EXPERIENCE: "Опыт",
    RequirementCategory.SECURITY: "Обеспечение",
    RequirementCategory.DEADLINE: "Сроки",
    RequirementCategory.PAYMENT: "Оплата",
    RequirementCategory.WARRANTY: "Гарантия",
    RequirementCategory.PENALTY: "Штрафы и пени",
    RequirementCategory.CONTRACT: "Договорные риски",
    RequirementCategory.TECHNICAL: "Технические требования",
    RequirementCategory.STOP_FACTOR: "Стоп-факторы",
}

_DOCUMENT_KIND_LABELS = {
    DocumentKind.TECHNICAL_SPECIFICATION: "Техническое задание",
    DocumentKind.DRAFT_CONTRACT: "Проект контракта",
    DocumentKind.PROCUREMENT_NOTICE: "Извещение",
    DocumentKind.APPLICATION_REQUIREMENTS: "Требования к заявке",
    DocumentKind.ESTIMATE: "Смета / НМЦК",
    DocumentKind.APPLICATION_FORM: "Форма заявки",
    DocumentKind.INSTRUCTIONS: "Инструкции",
    DocumentKind.OTHER: "Прочее",
}


class TenderRequirementAnalysisDialog(QDialog):
    """Display evidence-backed analysis and request background reruns."""

    analysis_requested = Signal(str, bool)

    def __init__(
        self,
        registry_key: str,
        *,
        analysis: TenderRequirementAnalysis | None = None,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.registry_key = registry_key.strip()
        if not self.registry_key:
            raise ValueError("registry_key must not be empty")
        try:
            self._theme = ThemeName(theme)
        except (TypeError, ValueError, AttributeError):
            self._theme = ThemeName.DARK

        self._analysis: TenderRequirementAnalysis | None = None
        self._visible_findings: tuple[RequirementFinding, ...] = ()
        self._busy = False

        self.setWindowTitle("Corteris Tender AI — анализ требований тендера")
        self.setModal(False)
        self.resize(1480, 880)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        root.addWidget(self._build_summary())
        root.addWidget(self._build_filters())

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("TenderAnalysisTabs")
        self.tabs.addTab(self._build_findings_tab(), "Требования и риски")
        self.tabs.addTab(self._build_documents_tab(), "Документы")
        self.tabs.addTab(self._build_missing_tab(), "Недостающие документы")
        root.addWidget(self.tabs, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.run_button = QPushButton("Запустить анализ", self)
        self.run_button.setObjectName("PrimaryActionButton")
        self.run_button.clicked.connect(
            lambda: self.analysis_requested.emit(
                self.registry_key,
                False,
            )
        )

        self.force_button = QPushButton(
            "Повторно извлечь и проанализировать",
            self,
        )
        self.force_button.clicked.connect(
            lambda: self.analysis_requested.emit(
                self.registry_key,
                True,
            )
        )

        actions.addWidget(self.run_button)
        actions.addWidget(self.force_button)
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
        self.status_label.setObjectName("TenderAnalysisStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.status_label)

        self.apply_theme(self._theme)
        if analysis is not None:
            self.set_analysis(analysis)
        else:
            self._render_empty_state()

    @property
    def analysis(self) -> TenderRequirementAnalysis | None:
        return self._analysis

    @property
    def analysis_busy(self) -> bool:
        return self._busy

    @property
    def visible_findings(self) -> tuple[RequirementFinding, ...]:
        return self._visible_findings

    def _build_summary(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("TenderAnalysisSummary")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(22)

        heading = QVBoxLayout()
        title = QLabel("Анализ требований и рисков", frame)
        title.setObjectName("TenderAnalysisTitle")
        subtitle = QLabel(
            f"Локальная карточка: {self.registry_key}",
            frame,
        )
        subtitle.setObjectName("TenderAnalysisSubtitle")
        subtitle.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        heading.addWidget(title)
        heading.addWidget(subtitle)
        layout.addLayout(heading, 1)

        self.risk_metric = self._add_metric(layout, frame, "Риск")
        self.documents_metric = self._add_metric(layout, frame, "Документов")
        self.findings_metric = self._add_metric(layout, frame, "Требований")
        self.critical_metric = self._add_metric(layout, frame, "Критичных")
        self.missing_metric = self._add_metric(layout, frame, "Не хватает")
        return frame

    @staticmethod
    def _add_metric(
        layout: QHBoxLayout,
        parent: QWidget,
        caption: str,
    ) -> QLabel:
        column = QVBoxLayout()
        value = QLabel("—", parent)
        value.setObjectName("TenderAnalysisMetricValue")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(caption, parent)
        label.setObjectName("TenderAnalysisMetricLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(value)
        column.addWidget(label)
        layout.addLayout(column)
        return value

    def _build_filters(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("TenderAnalysisFilters")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self.search_edit = QLineEdit(frame)
        self.search_edit.setPlaceholderText("Поиск по требованию, значению, документу и фрагменту…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self.refresh_findings)

        self.category_combo = QComboBox(frame)
        self.category_combo.addItem("Все категории", "")
        for category in RequirementCategory:
            self.category_combo.addItem(
                _CATEGORY_LABELS.get(category, category.value),
                category.value,
            )
        self.category_combo.currentIndexChanged.connect(self.refresh_findings)

        self.severity_combo = QComboBox(frame)
        self.severity_combo.addItem("Любая важность", "")
        for severity in (
            FindingSeverity.CRITICAL,
            FindingSeverity.WARNING,
            FindingSeverity.INFO,
        ):
            self.severity_combo.addItem(
                _SEVERITY_LABELS[severity],
                severity.value,
            )
        self.severity_combo.currentIndexChanged.connect(self.refresh_findings)

        layout.addWidget(self.search_edit, 1)
        layout.addWidget(self.category_combo)
        layout.addWidget(self.severity_combo)
        return frame

    def _build_findings_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, tab)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

        table_frame = QFrame(splitter)
        table_frame.setObjectName("TenderAnalysisTableFrame")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(10, 10, 10, 10)

        self.findings_table = QTableWidget(table_frame)
        self.findings_table.setObjectName("TenderAnalysisFindingsTable")
        self.findings_table.setColumnCount(6)
        self.findings_table.setHorizontalHeaderLabels(
            (
                "Важность",
                "Категория",
                "Требование",
                "Значение",
                "Документ",
                "Доверие",
            )
        )
        self.findings_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.findings_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.findings_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.findings_table.setAlternatingRowColors(True)
        self.findings_table.verticalHeader().setVisible(False)
        self.findings_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.findings_table.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        self.findings_table.horizontalHeader().setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        self.findings_table.itemSelectionChanged.connect(self._show_selected_finding)
        table_layout.addWidget(self.findings_table, 1)
        splitter.addWidget(table_frame)

        details_frame = QFrame(splitter)
        details_frame.setObjectName("TenderAnalysisDetailsFrame")
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(10, 10, 10, 10)

        details_title = QLabel("Основание вывода", details_frame)
        details_title.setObjectName("TenderAnalysisSectionTitle")
        details_layout.addWidget(details_title)

        self.finding_details = QTextBrowser(details_frame)
        self.finding_details.setObjectName("TenderAnalysisDetails")
        details_layout.addWidget(self.finding_details, 1)
        splitter.addWidget(details_frame)
        splitter.setSizes([980, 500])
        return tab

    def _build_documents_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)

        self.documents_table = QTableWidget(tab)
        self.documents_table.setObjectName("TenderAnalysisDocumentsTable")
        self.documents_table.setColumnCount(5)
        self.documents_table.setHorizontalHeaderLabels(
            (
                "Тип",
                "Документ",
                "Символов",
                "Контрольная сумма",
                "Предупреждения",
            )
        )
        self.documents_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.documents_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.documents_table.setAlternatingRowColors(True)
        self.documents_table.verticalHeader().setVisible(False)
        self.documents_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.documents_table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        self.documents_table.horizontalHeader().setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )
        layout.addWidget(self.documents_table, 1)
        return tab

    def _build_missing_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)

        explanation = QLabel(
            "Список формируется по классификации загруженных документов. "
            "Отсутствие в списке не заменяет ручную проверку комплекта.",
            tab,
        )
        explanation.setWordWrap(True)
        explanation.setObjectName("TenderAnalysisSubtitle")
        layout.addWidget(explanation)

        self.missing_list = QListWidget(tab)
        self.missing_list.setObjectName("TenderAnalysisMissingList")
        layout.addWidget(self.missing_list, 1)
        return tab

    def set_analysis_busy(
        self,
        busy: bool,
        *,
        message: str = "",
    ) -> None:
        self._busy = bool(busy)
        self.run_button.setEnabled(not busy)
        self.force_button.setEnabled(not busy)
        self.search_edit.setEnabled(not busy)
        self.category_combo.setEnabled(not busy)
        self.severity_combo.setEnabled(not busy)
        self.tabs.setEnabled(not busy)
        if busy:
            self.set_status(message or "Извлечение текста и анализ требований выполняются в фоне…")

    def set_analysis(
        self,
        analysis: TenderRequirementAnalysis,
    ) -> None:
        if analysis.registry_key != self.registry_key:
            raise ValueError("analysis registry_key does not match dialog registry_key")
        self._analysis = analysis
        self.set_analysis_busy(False)

        risk = analysis.risk_level
        self.risk_metric.setText(_RISK_LABELS[risk])
        self.risk_metric.setProperty("risk", risk.value)
        self.risk_metric.style().unpolish(self.risk_metric)
        self.risk_metric.style().polish(self.risk_metric)
        self.documents_metric.setText(str(len(analysis.documents)))
        self.findings_metric.setText(str(len(analysis.findings)))
        self.critical_metric.setText(str(analysis.critical_count))
        self.missing_metric.setText(str(len(analysis.missing_documents)))

        self._populate_documents()
        self._populate_missing_documents()
        self.refresh_findings()

        status_parts = [
            f"Анализ завершён: {analysis.analyzed_at}",
            f"риск — {_RISK_LABELS[risk].casefold()}",
            f"требований — {len(analysis.findings)}",
        ]
        if analysis.warnings:
            status_parts.append("предупреждения: " + "; ".join(analysis.warnings))
        self.set_status("; ".join(status_parts))

    def set_analysis_error(self, message: str) -> None:
        self.set_analysis_busy(False)
        self.set_status(
            f"Не удалось выполнить анализ: {message}",
            error=True,
        )

    def refresh_findings(self) -> None:
        analysis = self._analysis
        if analysis is None:
            self._visible_findings = ()
            self.findings_table.setRowCount(0)
            self.finding_details.setHtml(
                "<h3>Анализ ещё не выполнен</h3>"
                "<p>Запустите анализ после загрузки тендерной документации.</p>"
            )
            return

        query = self.search_edit.text().strip().casefold()
        category = str(self.category_combo.currentData() or "")
        severity = str(self.severity_combo.currentData() or "")

        findings: list[RequirementFinding] = []
        for finding in analysis.findings:
            if category and finding.category.value != category:
                continue
            if severity and finding.severity.value != severity:
                continue
            if query:
                haystack = " ".join(
                    (
                        finding.title,
                        finding.value,
                        finding.source_name,
                        finding.snippet,
                        _CATEGORY_LABELS.get(
                            finding.category,
                            finding.category.value,
                        ),
                    )
                ).casefold()
                if query not in haystack:
                    continue
            findings.append(finding)

        self._visible_findings = tuple(findings)
        self.findings_table.setRowCount(len(findings))

        for row, finding in enumerate(findings):
            values = (
                _SEVERITY_LABELS[finding.severity],
                _CATEGORY_LABELS.get(
                    finding.category,
                    finding.category.value,
                ),
                finding.title,
                finding.value or "—",
                finding.source_name,
                f"{finding.confidence * 100:.0f}%",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.findings_table.setItem(row, column, item)

        if findings:
            self.findings_table.selectRow(0)
            self._show_selected_finding()
        else:
            self.finding_details.setHtml(
                "<h3>Совпадений по фильтру нет</h3>"
                "<p>Измените категорию, важность или строку поиска.</p>"
            )

    def selected_finding(self) -> RequirementFinding | None:
        row = self.findings_table.currentRow()
        if not 0 <= row < len(self._visible_findings):
            return None
        return self._visible_findings[row]

    def _show_selected_finding(self) -> None:
        finding = self.selected_finding()
        if finding is None:
            return

        self.finding_details.setHtml(
            f"<h2>{escape(finding.title)}</h2>"
            f"<p><b>Категория:</b> "
            f"{escape(_CATEGORY_LABELS.get(finding.category, finding.category.value))}</p>"
            f"<p><b>Важность:</b> "
            f"{escape(_SEVERITY_LABELS[finding.severity])}</p>"
            f"<p><b>Значение:</b> {escape(finding.value or '—')}</p>"
            f"<p><b>Документ:</b> {escape(finding.source_name)}</p>"
            f"<p><b>Доверие правила:</b> "
            f"{finding.confidence * 100:.0f}%</p>"
            f"<h3>Фрагмент документа</h3>"
            f"<p>{escape(finding.snippet)}</p>"
            f"<p><b>Код правила:</b> {escape(finding.pattern_key)}</p>"
            "<p><i>Результат является автоматической подсказкой и "
            "требует проверки специалистом.</i></p>"
        )

    def _populate_documents(self) -> None:
        analysis = self._analysis
        documents = analysis.documents if analysis is not None else ()
        self.documents_table.setRowCount(len(documents))

        for row, document in enumerate(documents):
            values = (
                _DOCUMENT_KIND_LABELS.get(
                    document.kind,
                    document.kind.value,
                ),
                document.source_name,
                f"{document.character_count:,}".replace(",", " "),
                document.checksum_sha256[:16] or "—",
                "; ".join(document.warnings) or "—",
            )
            for column, value in enumerate(values):
                self.documents_table.setItem(
                    row,
                    column,
                    QTableWidgetItem(value),
                )

    def _populate_missing_documents(self) -> None:
        self.missing_list.clear()
        analysis = self._analysis
        if analysis is None:
            self.missing_list.addItem("Анализ ещё не выполнен")
            return
        if not analysis.missing_documents:
            self.missing_list.addItem("Основные документы распознаны: ТЗ и проект контракта.")
            return
        for document in analysis.missing_documents:
            self.missing_list.addItem(document)

    def _render_empty_state(self) -> None:
        self.risk_metric.setText("—")
        self.documents_metric.setText("0")
        self.findings_metric.setText("0")
        self.critical_metric.setText("0")
        self.missing_metric.setText("—")
        self.refresh_findings()
        self._populate_documents()
        self._populate_missing_documents()
        self.set_status(
            "Анализ ещё не выполнен. Сначала загрузите документацию, "
            "затем нажмите «Запустить анализ»."
        )

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("error", error)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {palette.app_background};
                color: {palette.text_primary};
            }}
            QFrame#TenderAnalysisSummary,
            QFrame#TenderAnalysisFilters,
            QFrame#TenderAnalysisTableFrame,
            QFrame#TenderAnalysisDetailsFrame {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_default};
                border-radius: 9px;
            }}
            QLabel#TenderAnalysisTitle {{
                color: {palette.text_primary};
                font-size: 22px;
                font-weight: 700;
            }}
            QLabel#TenderAnalysisSubtitle,
            QLabel#TenderAnalysisMetricLabel {{
                color: {palette.text_secondary};
            }}
            QLabel#TenderAnalysisMetricValue {{
                color: {palette.brand_accent};
                font-size: 20px;
                font-weight: 700;
            }}
            QLabel#TenderAnalysisMetricValue[risk="low"] {{
                color: {palette.success};
            }}
            QLabel#TenderAnalysisMetricValue[risk="medium"] {{
                color: {palette.warning};
            }}
            QLabel#TenderAnalysisMetricValue[risk="high"],
            QLabel#TenderAnalysisMetricValue[risk="critical"] {{
                color: {palette.danger};
            }}
            QLabel#TenderAnalysisSectionTitle {{
                color: {palette.text_primary};
                font-size: 14px;
                font-weight: 700;
            }}
            QLabel#TenderAnalysisStatus {{
                color: {palette.text_secondary};
            }}
            QLabel#TenderAnalysisStatus[error="true"] {{
                color: {palette.danger};
            }}
            QLineEdit, QComboBox {{
                min-height: 32px;
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 3px 8px;
            }}
            QTableWidget#TenderAnalysisFindingsTable,
            QTableWidget#TenderAnalysisDocumentsTable,
            QListWidget#TenderAnalysisMissingList {{
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
            QTextBrowser#TenderAnalysisDetails {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 7px;
            }}
            QTabWidget::pane {{
                border: 1px solid {palette.border_default};
                border-radius: 8px;
                background-color: {palette.panel_background};
            }}
            QTabBar::tab {{
                color: {palette.text_secondary};
                background-color: {palette.elevated_background};
                border: 1px solid {palette.border_default};
                padding: 8px 14px;
            }}
            QTabBar::tab:selected {{
                color: {palette.text_primary};
                background-color: {palette.selected_background};
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


__all__ = ["TenderRequirementAnalysisDialog"]
