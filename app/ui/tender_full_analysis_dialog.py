"""Progress and result dialog for the complete tender analysis workflow."""

from __future__ import annotations

from html import escape
import re

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.tenders.full_analysis import (
    FullAnalysisProgress,
    FullAnalysisStage,
    FullAnalysisStatus,
    TenderFullAnalysisResult,
)
from app.core.ai.schemas import (
    AiAnalysisStatus,
    AiApplicationRequirementsStatus,
    AiDocumentAnalysis,
    AiDocumentationCompletenessStatus,
    AiDraftContractStatus,
    AiCompetitionReviewPriority,
    AiCompetitionStatus,
    AiFinancialReviewPriority,
    AiFinancialRiskStatus,
    AiLegalReviewPriority,
    AiLegalRiskStatus,
    AiTechnicalSpecificationStatus,
    _APPLICATION_REQUIREMENTS_FINDING_FIELDS,
)
from app.core.ai.competition_review import competition_source_findings
from app.core.ai.documentation_completeness import (
    AI_DOCUMENTATION_COMPLETENESS_DISCLAIMER,
)
from app.core.document_classification import DocumentKind
from app.core.ai.financial_risk import financial_risk_source_findings
from app.core.ai.legal_risk import legal_risk_source_findings
from app.ui.theme.colors import ThemeName, get_palette
from app.reporting.tender_ai_analysis import TenderAiAnalysisExporter


_STAGE_LABELS = {
    FullAnalysisStage.LOADING: "Карточка закупки",
    FullAnalysisStage.DOWNLOADING: "Скачивание документов",
    FullAnalysisStage.EXTRACTING_ARCHIVES: "Распаковка архивов",
    FullAnalysisStage.EXTRACTING_TEXT: "Извлечение текста",
    FullAnalysisStage.ANALYZING_REQUIREMENTS: "Анализ требований",
    FullAnalysisStage.RUNNING_LEGACY_ANALYSIS: "AnalysisEngine",
    FullAnalysisStage.SCORING: "Оценка участия",
    FullAnalysisStage.RUNNING_AI: "AI-анализ документации",
    FullAnalysisStage.COMPLETED: "Завершение",
}


class TenderFullAnalysisDialog(QDialog):
    cancel_requested = Signal(str)
    citation_requested = Signal(str, str)
    documents_requested = Signal(str)
    requirements_requested = Signal(str)
    score_requested = Signal(str)

    def __init__(
        self,
        registry_key: str,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.registry_key = registry_key.strip()
        self._theme = ThemeName(theme)
        self._result: TenderFullAnalysisResult | None = None
        self._citation_targets: dict[str, str] = {}
        self.setWindowTitle("Скачать документы и провести полный анализ")
        self.resize(980, 760)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        header = QFrame(self)
        header.setObjectName("FullAnalysisHeader")
        header_layout = QVBoxLayout(header)
        self.title_label = QLabel("Полный анализ тендера", header)
        self.title_label.setObjectName("FullAnalysisTitle")
        self.message_label = QLabel("Готово к запуску", header)
        self.message_label.setWordWrap(True)
        self.progress = QProgressBar(header)
        self.progress.setRange(0, 100)
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.message_label)
        header_layout.addWidget(self.progress)
        root.addWidget(header)

        self.stages = QTableWidget(self)
        self.stages.setColumnCount(3)
        self.stages.setHorizontalHeaderLabels(("Этап", "Состояние", "Подробности"))
        self.stages.verticalHeader().setVisible(False)
        self.stages.horizontalHeader().setStretchLastSection(True)
        self.stages.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._stage_rows = {}
        for stage, label in _STAGE_LABELS.items():
            row = self.stages.rowCount()
            self.stages.insertRow(row)
            self.stages.setItem(row, 0, QTableWidgetItem(label))
            self.stages.setItem(row, 1, QTableWidgetItem("Ожидание"))
            self.stages.setItem(row, 2, QTableWidgetItem("—"))
            self._stage_rows[stage] = row
        self.summary = QTextBrowser(self)
        self.summary.setObjectName("FullAnalysisSummary")
        self.ai_summary = QTextBrowser(self)
        self.ai_summary.setObjectName("TenderAiSummary")
        self.ai_analysis = QTextBrowser(self)
        self.ai_analysis.setObjectName("TenderAiDocumentAnalysis")
        self.ai_analysis.setOpenExternalLinks(False)
        self.ai_analysis.anchorClicked.connect(self._open_citation)
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self.stages, "Analysis stages")
        self.tabs.addTab(self.summary, "Analysis details")
        self.tabs.addTab(self.ai_summary, "AI summary")
        self.tabs.addTab(self.ai_analysis, "AI-анализ")
        root.addWidget(self.tabs, 1)

        actions = QHBoxLayout()
        self.cancel_button = QPushButton("Остановить", self)
        self.cancel_button.clicked.connect(
            lambda _checked=False: self.cancel_requested.emit(self.registry_key)
        )
        self.documents_button = QPushButton("Документы", self)
        self.documents_button.clicked.connect(
            lambda _checked=False: self.documents_requested.emit(self.registry_key)
        )
        self.requirements_button = QPushButton("Требования", self)
        self.requirements_button.clicked.connect(
            lambda _checked=False: self.requirements_requested.emit(self.registry_key)
        )
        self.score_button = QPushButton("Оценка участия", self)
        self.score_button.clicked.connect(
            lambda _checked=False: self.score_requested.emit(self.registry_key)
        )
        self.export_ai_button = QPushButton("Экспорт AI-анализа", self)
        self.export_ai_button.clicked.connect(self._export_ai_analysis)
        self.export_ai_button.setEnabled(False)
        for button in (self.documents_button, self.requirements_button, self.score_button):
            button.setEnabled(False)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.documents_button)
        actions.addWidget(self.requirements_button)
        actions.addWidget(self.score_button)
        actions.addWidget(self.export_ai_button)
        actions.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        root.addLayout(actions)

        self.apply_theme(self._theme)

    @property
    def result(self) -> TenderFullAnalysisResult | None:
        return self._result

    def begin(self) -> None:
        self._result = None
        self._citation_targets = {}
        self.progress.setValue(0)
        self.message_label.setText("Запуск полного анализа…")
        self.cancel_button.setEnabled(True)
        for row in self._stage_rows.values():
            self.stages.item(row, 1).setText("Ожидание")
            self.stages.item(row, 2).setText("—")
        self.summary.setHtml("<p>Документы будут скачаны и обработаны в фоновом потоке.</p>")

    def update_progress(self, event: FullAnalysisProgress) -> None:
        self.progress.setValue(event.percent)
        self.message_label.setText(event.message)
        row = self._stage_rows.get(event.stage)
        if row is not None:
            self.stages.item(row, 1).setText("Выполняется")
            details = event.message
            if event.total_items:
                details += f" ({event.current_item}/{event.total_items})"
            self.stages.item(row, 2).setText(details)
            for previous_stage, previous_row in self._stage_rows.items():
                if previous_row < row and self.stages.item(previous_row, 1).text() == "Выполняется":
                    self.stages.item(previous_row, 1).setText("Готово")

    def set_result(self, result: TenderFullAnalysisResult) -> None:
        self._result = result
        self.cancel_button.setEnabled(False)
        self.progress.setValue(
            100 if result.status != FullAnalysisStatus.CANCELLED else self.progress.value()
        )
        self.message_label.setText(
            "Полный анализ завершён."
            if result.status == FullAnalysisStatus.COMPLETED
            else (
                "Анализ завершён с предупреждениями."
                if result.status == FullAnalysisStatus.PARTIAL
                else "Анализ остановлен пользователем."
            )
        )
        for row in self._stage_rows.values():
            if self.stages.item(row, 1).text() in {"Ожидание", "Выполняется"}:
                self.stages.item(row, 1).setText(
                    "Отменено" if result.status == FullAnalysisStatus.CANCELLED else "Готово"
                )
        self.documents_button.setEnabled(result.download is not None)
        self.requirements_button.setEnabled(result.requirements is not None)
        self.score_button.setEnabled(result.score is not None)
        self.summary.setHtml(_render_result(result))
        self.ai_summary.setHtml(_render_ai_summary(result))
        self._citation_targets = _current_citation_targets(result.ai_document_analysis)
        self.ai_analysis.setHtml(_render_ai_document_analysis(result))
        self.export_ai_button.setEnabled(result.ai_document_analysis is not None)

    def _open_citation(self, url: QUrl) -> None:
        if (
            url.scheme() != "corteris-citation"
            or url.host() != "open"
            or url.userInfo()
            or url.port() != -1
            or url.hasQuery()
            or url.hasFragment()
        ):
            return
        path = url.path()
        if not re.fullmatch(r"/cit_[0-9a-f]{32}", path):
            return
        document_id = self._citation_targets.get(path[1:])
        if document_id is not None:
            self.citation_requested.emit(self.registry_key, document_id)

    def _export_ai_analysis(self) -> None:
        analysis = self._result.ai_document_analysis if self._result else None
        if analysis is None:
            return
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Экспорт AI-анализа",
            f"{self.registry_key.replace(':', '_')}_ai_analysis.html",
            "HTML (*.html);;JSON (*.json)",
        )
        if not path:
            return
        try:
            TenderAiAnalysisExporter().export(analysis, path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Ошибка экспорта", str(exc))

    def set_error(self, message: str) -> None:
        self.cancel_button.setEnabled(False)
        self.message_label.setText(f"Ошибка: {message}")
        self.summary.setHtml(f"<h3>Полный анализ не завершён</h3><p>{escape(message)}</p>")

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.setStyleSheet(f"""
            QDialog {{ color: {palette.text_primary}; background: {palette.app_background}; }}
            QFrame#FullAnalysisHeader {{ background: {palette.card_background}; border: 1px solid {palette.border_default}; border-radius: 9px; }}
            QLabel#FullAnalysisTitle {{ font-size: 21px; font-weight: 700; }}
            QTableWidget, QTextBrowser#FullAnalysisSummary, QTextBrowser#TenderAiSummary, QTextBrowser#TenderAiDocumentAnalysis {{ color: {palette.text_primary}; background: {palette.input_background}; border: 1px solid {palette.border_default}; }}
            QPushButton {{ min-height: 32px; color: {palette.text_primary}; background: {palette.elevated_background}; border: 1px solid {palette.border_default}; border-radius: 7px; padding: 4px 10px; font-weight: 600; }}
        """)


def _render_result(result: TenderFullAnalysisResult) -> str:
    download = result.download
    archives = result.archives
    text = result.text
    score = result.score
    requirements = result.requirements
    commercial = result.commercial_estimate
    summary = result.summary
    summary_html = "<p>Offline-резюме не сформировано.</p>"
    if summary is not None:
        facts = (
            "".join(
                f"<li><b>{escape(item.label)}:</b> {escape(item.value)}</li>"
                for item in summary.facts
            )
            or "<li>Нет подтверждённых фактов.</li>"
        )
        risks = (
            "".join(f"<li>{escape(item)}</li>" for item in summary.risks) or "<li>Не выявлено.</li>"
        )
        missing = (
            "".join(f"<li>{escape(item)}</li>" for item in summary.missing_information)
            or "<li>Не выявлено.</li>"
        )
        summary_html = (
            f"<h3>Краткое резюме: {escape(summary.headline)}</h3>"
            f"<p><b>Источник:</b> {escape(summary.source.value)}</p>"
            f"<h4>Подтверждённые факты</h4><ul>{facts}</ul>"
            f"<h4>Риски</h4><ul>{risks}</ul>"
            f"<h4>Не хватает данных</h4><ul>{missing}</ul>"
        )
    warnings = "".join(f"<li>{escape(item)}</li>" for item in result.warnings) or "<li>Нет</li>"
    return (
        f"<h2>{escape(result.procurement_number or result.registry_key)}</h2>"
        f"<p><b>Статус:</b> {escape(result.status.value)}</p>"
        f"<p><b>Документы:</b> {download.total_count if download else 0}; "
        f"скачано: {download.downloaded_count if download else 0}; "
        f"ошибок: {download.failed_count if download else 0}</p>"
        f"<p><b>Распаковано файлов:</b> {archives.extracted_count if archives else 0}; "
        f"заблокировано: {archives.blocked_count if archives else 0}</p>"
        f"<p><b>Извлечено текста:</b> {text.total_character_count if text else 0} символов</p>"
        f"<p><b>Риск требований:</b> {escape(requirements.risk_level.value) if requirements else '—'}</p>"
        f"<p><b>Итоговая оценка:</b> {score.total_score if score else '—'}/100 — "
        f"{escape(score.recommendation_text) if score else 'не рассчитана'}</p>"
        f"<p><b>Коммерческий расчёт:</b> "
        f"{escape(commercial.status.value) if commercial else 'не создан'}; "
        f"прибыль: {commercial.profit if commercial and commercial.profit is not None else 'не рассчитана'}"
        f"</p>"
        f"<p><b>Существующий AnalysisEngine:</b> {'выполнен' if result.legacy else 'не выполнен или недоступен'}</p>"
        f"{summary_html}"
        f"<h3>Предупреждения</h3><ul>{warnings}</ul>"
    )


def _render_ai_summary(result: TenderFullAnalysisResult) -> str:
    summary = result.summary
    if summary is None:
        return "<h3>AI summary is unavailable</h3><p>Run full analysis first.</p>"
    facts = (
        "".join(
            "<li><b>{label}:</b> {value} <small>({source}; confidence {confidence:.0%}; {provenance})</small></li>".format(
                label=escape(item.label),
                value=escape(item.value),
                source=escape(item.source),
                confidence=item.confidence,
                provenance=escape(item.provenance),
            )
            for item in summary.facts
        )
        or "<li>No confirmed facts.</li>"
    )
    risks = (
        "".join(f"<li>{escape(item)}</li>" for item in summary.risks) or "<li>None detected.</li>"
    )
    stops = (
        "".join(f"<li>{escape(item)}</li>" for item in summary.stop_factors)
        or "<li>None detected.</li>"
    )
    missing = (
        "".join(f"<li>{escape(item)}</li>" for item in summary.missing_information)
        or "<li>None.</li>"
    )
    return (
        f"<h2>{escape(summary.headline)}</h2>"
        f"<p><b>Recommendation:</b> {escape(summary.recommendation)} (confidence {summary.recommendation_confidence:.0%})</p>"
        f"<p><b>Explanation:</b> {escape(summary.ai_explanation)}</p>"
        f"<p><b>Financial result:</b> {escape(summary.financial_summary)}</p>"
        f"<p><b>Company profile:</b> {escape(summary.company_profile)}</p>"
        f"<h3>Facts and provenance</h3><ul>{facts}</ul>"
        f"<h3>Risks</h3><ul>{risks}</ul>"
        f"<h3>Stop factors</h3><ul>{stops}</ul>"
        f"<h3>Missing data</h3><ul>{missing}</ul>"
    )


def _render_documentation_completeness(analysis: AiDocumentAnalysis) -> str:
    assessment = analysis.documentation_completeness_assessment
    status = {
        AiDocumentationCompletenessStatus.COMPLETE: (
            "Локально известный комплект готов для текущего анализа"
        ),
        AiDocumentationCompletenessStatus.PARTIAL: (
            "Комплект обработан частично; требуется устранить проблемы"
        ),
        AiDocumentationCompletenessStatus.NO_DOCUMENTS: "Документы для проверки не найдены",
        AiDocumentationCompletenessStatus.UNAVAILABLE: ("Оценка полноты документации недоступна"),
    }.get(assessment.status, "Оценка полноты документации недоступна")
    coverage = "".join(
        f"<li>{escape(kind.value)}: "
        f"{sum(item.document_kind is kind for item in analysis.documentation_inventory)}</li>"
        for kind in DocumentKind
    )
    inventory = (
        "".join(
            "<li>"
            f"<b>{escape(item.display_name or item.document_id)}</b> · "
            f"{escape(item.document_kind.value)} · загрузка {escape(item.download_status)} · "
            f"извлечение {escape(item.extraction_status)} · "
            f"в контексте {'да' if item.included_in_context else 'нет'} · "
            f"усечён {'да' if item.context_truncated else 'нет'}"
            "</li>"
            for item in analysis.documentation_inventory
        )
        or "<li>Локальные документы не найдены.</li>"
    )
    issues = (
        "".join(
            "<li>"
            f"<b>{escape(item.title)}</b> · {escape(item.scope.value)}"
            f" · документы: {escape(', '.join(item.document_ids) or '—')}<br>"
            f"Действие: {escape(item.recommended_action)}"
            "</li>"
            for item in assessment.issues
        )
        or "<li>Локальные проблемы не выявлены.</li>"
    )
    warnings = (
        "".join(f"<li>{escape(item)}</li>" for item in assessment.warnings) or "<li>Нет.</li>"
    )
    return (
        "<h3>Полнота документации</h3>"
        f"<p><b>{escape(AI_DOCUMENTATION_COMPLETENESS_DISCLAIMER)}</b></p>"
        f"<p><b>Статус:</b> {escape(status)} · policy version: "
        f"{escape(assessment.policy_version)}</p>"
        f"<p>Известно: {assessment.known_document_count} · доступно локально: "
        f"{assessment.locally_available_count} · доступен текст: "
        f"{assessment.text_available_count} · включено в контекст: "
        f"{assessment.included_document_count}</p>"
        f"<h4>Покрытие областей</h4><ul>{coverage}</ul>"
        f"<h4>Локальный состав</h4><ul>{inventory}</ul>"
        f"<h4>Проблемы и действия</h4><ul>{issues}</ul>"
        f"<h4>Предупреждения оценки полноты</h4><ul>{warnings}</ul>"
    )


def _render_ai_document_analysis(result: TenderFullAnalysisResult) -> str:
    analysis = result.ai_document_analysis
    if analysis is None:
        return "<h3>AI-анализ недоступен</h3><p>Выполните полный анализ документации.</p>"

    def render_findings(items) -> str:
        rows = []
        sources = {
            source.document_id: source
            for source in (analysis.provenance.sources if analysis.provenance is not None else ())
        }
        for item in items:
            evidence = item.evidence
            if analysis.is_current_verified(item) and evidence is not None:
                source = sources[evidence.document_id]
                locator = " · ".join(
                    part
                    for part in (
                        f"страница {evidence.page}" if evidence.page is not None else "",
                        f"раздел {escape(evidence.section)}" if evidence.section else "",
                    )
                    if part
                )
                locator_html = f" · {locator}" if locator else ""
                truncation = " · контекст источника сокращён" if source.truncated else ""
                short_id = f"{evidence.citation_id[:12]}…"
                proof = (
                    f'<small><a href="corteris-citation://open/{evidence.citation_id}">'
                    f"{escape(source.display_name)}</a>{locator_html}{truncation}<br>"
                    f"Цитата: {escape(evidence.quote)}<br>"
                    f"уверенность AI {evidence.confidence:.0%} · citation {escape(short_id)}</small>"
                )
            else:
                proof = "<small>Неподтверждённый вывод — не влияет на рекомендацию.</small>"
            rows.append(f"<li><b>{escape(item.statement)}</b><br>{proof}</li>")
        return "".join(rows) or "<li>Не выявлено.</li>"

    requirements = analysis.requirements
    requirement_status = {
        AiApplicationRequirementsStatus.COMPLETE: "Полный результат",
        AiApplicationRequirementsStatus.PARTIAL: "Частичный результат",
        AiApplicationRequirementsStatus.NOT_FOUND: "Требования к заявке не найдены",
        AiApplicationRequirementsStatus.UNAVAILABLE: "Анализ требований к заявке недоступен",
    }.get(requirements.status, "Анализ требований к заявке недоступен")
    requirement_groups = {
        "application_composition": "Состав заявки",
        "participant_eligibility": "Требования к участнику",
        "declarations_and_consents": "Декларации и согласия",
        "equipment": "Оборудование и ресурсы",
        "certificates": "Сертификаты и качество",
        "licenses": "Лицензии, допуски и СРО",
        "specialists": "Специалисты и квалификация",
        "documents": "Подтверждающие документы",
        "experience": "Опыт исполнения",
        "deadlines": "Сроки подачи и действия заявки",
        "warranty": "Гарантийные обязательства",
        "bid_security": "Обеспечение заявки",
        "contract_security": "Обеспечение исполнения контракта",
        "bank_guarantee": "Банковская или независимая гарантия",
        "submission_format_and_signature": "Формат и подписание",
        "national_regime_and_origin": "Национальный режим и происхождение",
        "price_proposal_and_estimate": "Ценовое предложение и смета",
        "grounds_for_rejection": "Основания отклонения",
        "ambiguities": "Неоднозначности",
        "contradictions": "Противоречия",
        "clarification_points": "Вопросы для уточнения",
    }
    requirement_html = "".join(
        f"<h4>{escape(requirement_groups[name])}</h4>"
        f"<ul>{render_findings(getattr(requirements, name))}</ul>"
        for name in _APPLICATION_REQUIREMENTS_FINDING_FIELDS
    )
    requirement_warnings = (
        "".join(f"<li>{escape(item)}</li>" for item in requirements.warnings) or "<li>Нет.</li>"
    )
    requirement_context_note = (
        "<p><b>Внимание:</b> контекст требований к заявке неполон.</p>"
        if requirements.status is AiApplicationRequirementsStatus.PARTIAL
        and (
            len(requirements.document_ids) != len(requirements.included_document_ids)
            or requirements.warnings
        )
        else ""
    )
    legal = analysis.legal_risk_assessment
    legal_counts = {
        priority: sum(item.review_priority is priority for item in legal.items)
        for priority in AiLegalReviewPriority
    }
    legal_status = {
        AiLegalRiskStatus.COMPLETE: "Полный реестр подтверждённых условий",
        AiLegalRiskStatus.PARTIAL: "Частичный реестр; требуется проверка полноты",
        AiLegalRiskStatus.NO_VERIFIED_RISKS: (
            "Подтверждённые условия, требующие отдельной юридической проверки, не выявлены"
        ),
        AiLegalRiskStatus.UNAVAILABLE: "Оценка юридических рисков недоступна",
    }.get(legal.status, "Оценка юридических рисков недоступна")
    legal_priority_labels = {
        AiLegalReviewPriority.URGENT: "Срочно",
        AiLegalReviewPriority.ELEVATED: "Повышенный",
        AiLegalReviewPriority.ROUTINE: "Плановый",
    }
    legal_items = (
        "".join(
            "<li>"
            f"<b>{escape(item.title)}</b><br>"
            f"Категория: {escape(item.category.value)} · "
            f"приоритет: {escape(legal_priority_labels[item.review_priority])}<br>"
            f"Действие: {escape(item.recommended_action)}"
            f"<ul>{render_findings(legal_risk_source_findings(analysis, item))}</ul>"
            "</li>"
            for item in legal.items
        )
        or "<li>Нет подтверждённых элементов.</li>"
    )
    legal_warnings = (
        "".join(f"<li>{escape(item)}</li>" for item in legal.warnings) or "<li>Нет.</li>"
    )
    financial = analysis.financial_risk_assessment
    financial_counts = {
        priority: sum(item.review_priority is priority for item in financial.items)
        for priority in AiFinancialReviewPriority
    }
    financial_status = {
        AiFinancialRiskStatus.COMPLETE: "Полный реестр подтверждённых условий",
        AiFinancialRiskStatus.PARTIAL: "Частичный реестр; требуется проверка полноты",
        AiFinancialRiskStatus.NO_VERIFIED_CONDITIONS: (
            "Подтверждённые финансово значимые условия не выявлены"
        ),
        AiFinancialRiskStatus.UNAVAILABLE: "Оценка финансовых условий недоступна",
    }.get(financial.status, "Оценка финансовых условий недоступна")
    financial_priority_labels = {
        AiFinancialReviewPriority.URGENT: "Срочно",
        AiFinancialReviewPriority.ELEVATED: "Повышенный",
        AiFinancialReviewPriority.ROUTINE: "Плановый",
    }
    financial_items = (
        "".join(
            "<li>"
            f"<b>{escape(item.title)}</b><br>"
            f"Категория: {escape(item.category.value)} · "
            f"приоритет: {escape(financial_priority_labels[item.review_priority])}<br>"
            f"Действие: {escape(item.recommended_action)}"
            f"<ul>{render_findings(financial_risk_source_findings(analysis, item))}</ul>"
            "</li>"
            for item in financial.items
        )
        or "<li>Нет подтверждённых элементов.</li>"
    )
    financial_warnings = (
        "".join(f"<li>{escape(item)}</li>" for item in financial.warnings) or "<li>Нет.</li>"
    )
    competition = analysis.competition_assessment
    competition_counts = {
        priority: sum(item.review_priority is priority for item in competition.items)
        for priority in AiCompetitionReviewPriority
    }
    competition_status = {
        AiCompetitionStatus.COMPLETE: "Полный реестр подтверждённых условий",
        AiCompetitionStatus.PARTIAL: "Частичный реестр; требуется проверка полноты",
        AiCompetitionStatus.NO_VERIFIED_CONDITIONS: (
            "Документально подтверждённые условия, включённые в текущую политику "
            "конкурентной проверки, не выявлены."
        ),
        AiCompetitionStatus.UNAVAILABLE: "Оценка условий конкуренции недоступна",
    }.get(competition.status, "Оценка условий конкуренции недоступна")
    competition_priority_labels = {
        AiCompetitionReviewPriority.URGENT: "Срочно",
        AiCompetitionReviewPriority.ELEVATED: "Повышенный",
        AiCompetitionReviewPriority.ROUTINE: "Плановый",
    }
    competition_items = (
        "".join(
            "<li>"
            f"<b>{escape(item.title)}</b><br>"
            f"Категория: {escape(item.category.value)} · "
            f"приоритет: {escape(competition_priority_labels[item.review_priority])}<br>"
            f"Действие: {escape(item.recommended_action)}"
            f"<ul>{render_findings(competition_source_findings(analysis, item))}</ul>"
            "</li>"
            for item in competition.items
        )
        or "<li>Нет подтверждённых элементов.</li>"
    )
    competition_warnings = (
        "".join(f"<li>{escape(item)}</li>" for item in competition.warnings) or "<li>Нет.</li>"
    )

    technical = analysis.technical_specification
    technical_status = {
        AiTechnicalSpecificationStatus.COMPLETE: "Полный результат",
        AiTechnicalSpecificationStatus.PARTIAL: "Частичный результат",
        AiTechnicalSpecificationStatus.NOT_FOUND: "Техническое задание не найдено",
        AiTechnicalSpecificationStatus.UNAVAILABLE: "Анализ технического задания недоступен",
    }.get(technical.status, "Анализ технического задания недоступен")
    technical_groups = {
        "scope": "Предмет и состав",
        "deliverables": "Результаты и материалы",
        "quantities_and_volumes": "Объёмы и количества",
        "technical_characteristics": "Технические характеристики",
        "materials_and_equipment": "Материалы и оборудование",
        "standards_and_regulations": "Стандарты и нормы",
        "execution_conditions": "Условия выполнения",
        "stages_and_deadlines": "Этапы и сроки",
        "acceptance_and_quality": "Приёмка и качество",
        "customer_inputs_and_dependencies": "Данные и действия заказчика",
        "ambiguities": "Неоднозначности",
        "contradictions": "Противоречия",
        "clarification_points": "Вопросы для уточнения",
    }
    technical_html = "".join(
        f"<h4>{escape(label)}</h4><ul>{render_findings(getattr(technical, name))}</ul>"
        for name, label in technical_groups.items()
    )
    technical_warnings = (
        "".join(f"<li>{escape(item)}</li>" for item in technical.warnings) or "<li>Нет.</li>"
    )
    contract = analysis.draft_contract
    contract_status = {
        AiDraftContractStatus.COMPLETE: "Полный результат",
        AiDraftContractStatus.PARTIAL: "Частичный результат",
        AiDraftContractStatus.NOT_FOUND: "Проект договора/контракта не найден",
        AiDraftContractStatus.UNAVAILABLE: "Анализ проекта договора/контракта недоступен",
    }.get(contract.status, "Анализ проекта договора/контракта недоступен")
    contract_groups = {
        "subject_and_scope": "Предмет и объём обязательств",
        "term_schedule_and_location": "Сроки, этапы и место исполнения",
        "price_and_price_change": "Цена и изменение цены",
        "payment_terms": "Условия оплаты",
        "acceptance_and_closing_documents": "Приёмка и закрывающие документы",
        "performance_security": "Обеспечение исполнения и гарантий",
        "warranty_and_defect_remediation": "Гарантия и устранение недостатков",
        "customer_obligations_and_dependencies": "Обязанности и зависимости заказчика",
        "contractor_obligations_and_subcontracting": "Обязанности исполнителя и субподряд",
        "liability_penalties_and_damages": "Ответственность, штрафы и убытки",
        "change_suspension_and_termination": "Изменение, приостановка и расторжение",
        "force_majeure_and_notifications": "Форс-мажор и уведомления",
        "dispute_confidentiality_and_ip": "Споры, конфиденциальность и права",
        "ambiguities": "Неоднозначности",
        "contradictions": "Противоречия",
        "clarification_points": "Вопросы для уточнения",
    }
    contract_html = "".join(
        f"<h4>{escape(label)}</h4><ul>{render_findings(getattr(contract, name))}</ul>"
        for name, label in contract_groups.items()
    )
    contract_warnings = (
        "".join(f"<li>{escape(item)}</li>" for item in contract.warnings) or "<li>Нет.</li>"
    )
    missing = (
        "".join(f"<li>{escape(item)}</li>" for item in analysis.missing_documents)
        or "<li>Не выявлено.</li>"
    )
    status_text = {
        AiAnalysisStatus.COMPLETE: "Завершён",
        AiAnalysisStatus.PARTIAL: "Частичный результат",
        AiAnalysisStatus.NO_DOCUMENTS: "Нет документов для анализа",
        AiAnalysisStatus.PROVIDER_DISABLED: "AI-провайдер отключён",
        AiAnalysisStatus.PROVIDER_ERROR: "AI-провайдер недоступен",
        AiAnalysisStatus.INVALID_RESPONSE: "Ответ AI отклонён",
        AiAnalysisStatus.CACHE_INCOMPATIBLE: "Кеш несовместим",
    }.get(analysis.status, "Неизвестный безопасный статус")
    warnings = "".join(f"<li>{escape(item)}</li>" for item in analysis.warnings) or "<li>Нет.</li>"
    context_note = (
        "<p><b>Внимание:</b> контекст сокращён по безопасному лимиту; "
        "результат не считается полным.</p>"
        if analysis.context_truncated
        else ""
    )
    return (
        f"<h2>AI-анализ документации</h2><p><b>Статус:</b> {escape(status_text)}</p>"
        f"<p><b>Контекст:</b> {analysis.context_document_count} документов, "
        f"{analysis.context_character_count} символов</p>{context_note}"
        f"<h3>Краткое резюме</h3><p>{escape(analysis.summary)}</p>"
        f"{_render_documentation_completeness(analysis)}"
        f"<h3>Техническое задание</h3><p><b>Статус:</b> {escape(technical_status)}</p>"
        f"<p><b>Документы ТЗ:</b> найдено {len(technical.document_ids)}, "
        f"включено {len(technical.included_document_ids)}</p>{technical_html}"
        f"<h4>Предупреждения по ТЗ</h4><ul>{technical_warnings}</ul>"
        f"<h3>Проект договора/контракта</h3><p><b>Статус:</b> {escape(contract_status)}</p>"
        f"<p><b>Документы проекта договора:</b> найдено {len(contract.document_ids)}, "
        f"включено {len(contract.included_document_ids)}</p>{contract_html}"
        f"<h4>Предупреждения по проекту договора</h4><ul>{contract_warnings}</ul>"
        f"<h3>Требования к заявке</h3><p><b>Статус:</b> {escape(requirement_status)}</p>"
        f"<p><b>Документы требований:</b> найдено {len(requirements.document_ids)}, "
        f"включено {len(requirements.included_document_ids)}</p>{requirement_context_note}"
        f"{requirement_html}<h4>Предупреждения по требованиям к заявке</h4>"
        f"<ul>{requirement_warnings}</ul>"
        f"<h3>Юридические риски</h3>"
        f"<p><b>Информационная оценка; не является "
        f"юридическим заключением.</b></p>"
        f"<p><b>Статус:</b> {escape(legal_status)} · policy version: "
        f"{escape(legal.policy_version)} · срочно: "
        f"{legal_counts[AiLegalReviewPriority.URGENT]} · повышенный: "
        f"{legal_counts[AiLegalReviewPriority.ELEVATED]} · плановый: "
        f"{legal_counts[AiLegalReviewPriority.ROUTINE]}</p>"
        f"<ul>{legal_items}</ul>"
        f"<h4>Предупреждения юридической оценки</h4><ul>{legal_warnings}</ul>"
        f"<h3>Финансовые условия</h3>"
        f"<p><b>Информационная оценка условий документации; не является финансовым прогнозом, "
        f"расчётом убытка или рекомендацией об участии.</b></p>"
        f"<p><b>Статус:</b> {escape(financial_status)} · policy version: "
        f"{escape(financial.policy_version)} · срочно: "
        f"{financial_counts[AiFinancialReviewPriority.URGENT]} · повышенный: "
        f"{financial_counts[AiFinancialReviewPriority.ELEVATED]} · плановый: "
        f"{financial_counts[AiFinancialReviewPriority.ROUTINE]}</p>"
        f"<ul>{financial_items}</ul>"
        f"<h4>Предупреждения финансовой оценки</h4><ul>{financial_warnings}</ul>"
        f"<h3>Анализ конкуренции</h3>"
        f"<p><b>Информационная оценка документально подтверждённых условий участия. "
        f"Не является оценкой числа конкурентов, вероятности победы, законности условий "
        f"закупки или рекомендацией об участии.</b></p>"
        f"<p><b>Статус:</b> {escape(competition_status)} · policy version: "
        f"{escape(competition.policy_version)} · срочно: "
        f"{competition_counts[AiCompetitionReviewPriority.URGENT]} · повышенный: "
        f"{competition_counts[AiCompetitionReviewPriority.ELEVATED]} · плановый: "
        f"{competition_counts[AiCompetitionReviewPriority.ROUTINE]}</p>"
        f"<ul>{competition_items}</ul>"
        f"<h4>Предупреждения конкурентной оценки</h4><ul>{competition_warnings}</ul>"
        f"<h3>Риски</h3><ul>{render_findings(analysis.risks)}</ul>"
        f"<h3>Подозрительные условия</h3><ul>{render_findings(analysis.suspicious_conditions)}</ul>"
        f"<h3>Противоречия</h3><ul>{render_findings(analysis.contradictions)}</ul>"
        f"<h3>Возможные отсутствующие документы по ответу AI — не подтверждено "
        f"локальной проверкой</h3><ul>{missing}</ul>"
        f"<h3>Технические предупреждения</h3><ul>{warnings}</ul>"
        f"<h3>Итог AI</h3><p>{escape(analysis.final_ai_conclusion)}</p>"
    )


def _current_citation_targets(analysis: AiDocumentAnalysis | None) -> dict[str, str]:
    if analysis is None:
        return {}
    requirements = tuple(
        item
        for name in _APPLICATION_REQUIREMENTS_FINDING_FIELDS
        for item in getattr(analysis.requirements, name)
    )
    technical = tuple(
        item
        for name in analysis.technical_specification.__dataclass_fields__
        if name not in {"status", "document_ids", "included_document_ids", "warnings"}
        for item in getattr(analysis.technical_specification, name)
    )
    contract = tuple(
        item
        for name in analysis.draft_contract.__dataclass_fields__
        if name not in {"status", "document_ids", "included_document_ids", "warnings"}
        for item in getattr(analysis.draft_contract, name)
    )
    targets: dict[str, str] = {}
    for finding in (
        *requirements,
        *analysis.risks,
        *analysis.suspicious_conditions,
        *analysis.contradictions,
        *technical,
        *contract,
    ):
        if analysis.is_current_verified(finding) and finding.evidence is not None:
            targets[finding.evidence.citation_id] = finding.evidence.document_id
    return targets


__all__ = ["TenderFullAnalysisDialog"]
