"""Progress and result dialog for the complete tender analysis workflow."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
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
from app.ui.theme.colors import ThemeName, get_palette


_STAGE_LABELS = {
    FullAnalysisStage.LOADING: "Карточка закупки",
    FullAnalysisStage.DOWNLOADING: "Скачивание документов",
    FullAnalysisStage.EXTRACTING_ARCHIVES: "Распаковка архивов",
    FullAnalysisStage.EXTRACTING_TEXT: "Извлечение текста",
    FullAnalysisStage.ANALYZING_REQUIREMENTS: "Анализ требований",
    FullAnalysisStage.RUNNING_LEGACY_ANALYSIS: "AnalysisEngine",
    FullAnalysisStage.SCORING: "Оценка участия",
    FullAnalysisStage.COMPLETED: "Завершение",
}


class TenderFullAnalysisDialog(QDialog):
    cancel_requested = Signal(str)
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
        root.addWidget(self.stages, 1)

        self.summary = QTextBrowser(self)
        self.summary.setObjectName("FullAnalysisSummary")
        root.addWidget(self.summary, 1)

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
        for button in (self.documents_button, self.requirements_button, self.score_button):
            button.setEnabled(False)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.documents_button)
        actions.addWidget(self.requirements_button)
        actions.addWidget(self.score_button)
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
        self.progress.setValue(100 if result.status != FullAnalysisStatus.CANCELLED else self.progress.value())
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
            QTableWidget, QTextBrowser#FullAnalysisSummary {{ color: {palette.text_primary}; background: {palette.input_background}; border: 1px solid {palette.border_default}; }}
            QPushButton {{ min-height: 32px; color: {palette.text_primary}; background: {palette.elevated_background}; border: 1px solid {palette.border_default}; border-radius: 7px; padding: 4px 10px; font-weight: 600; }}
        """)


def _render_result(result: TenderFullAnalysisResult) -> str:
    download = result.download
    archives = result.archives
    text = result.text
    score = result.score
    requirements = result.requirements
    commercial = result.commercial_estimate
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
        f"<h3>Предупреждения</h3><ul>{warnings}</ul>"
    )


__all__ = ["TenderFullAnalysisDialog"]
