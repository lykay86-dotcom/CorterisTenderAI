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
from app.core.ai.schemas import AiAnalysisStatus, AiDocumentAnalysis
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

    requirements = tuple(
        item
        for name in analysis.requirements.__dataclass_fields__
        for item in getattr(analysis.requirements, name)
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
        f"<h3>Требования</h3><ul>{render_findings(requirements)}</ul>"
        f"<h3>Риски</h3><ul>{render_findings(analysis.risks)}</ul>"
        f"<h3>Подозрительные условия</h3><ul>{render_findings(analysis.suspicious_conditions)}</ul>"
        f"<h3>Противоречия</h3><ul>{render_findings(analysis.contradictions)}</ul>"
        f"<h3>Недостающие документы</h3><ul>{missing}</ul>"
        f"<h3>Технические предупреждения</h3><ul>{warnings}</ul>"
        f"<h3>Итог AI</h3><p>{escape(analysis.final_ai_conclusion)}</p>"
    )


def _current_citation_targets(analysis: AiDocumentAnalysis | None) -> dict[str, str]:
    if analysis is None:
        return {}
    requirements = tuple(
        item
        for name in analysis.requirements.__dataclass_fields__
        for item in getattr(analysis.requirements, name)
    )
    targets: dict[str, str] = {}
    for finding in (
        *requirements,
        *analysis.risks,
        *analysis.suspicious_conditions,
        *analysis.contradictions,
    ):
        if analysis.is_current_verified(finding) and finding.evidence is not None:
            targets[finding.evidence.citation_id] = finding.evidence.document_id
    return targets


__all__ = ["TenderFullAnalysisDialog"]
