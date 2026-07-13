"""Explainable participation-score view for one tender."""

from __future__ import annotations

from html import escape
from typing import Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.tenders.collector.participation_score import (
    CorterisParticipationScore,
)
from app.tenders.participation_decision import ParticipationDecision
from app.ui.theme.colors import ThemeName, get_palette


class TenderParticipationScoreDialog(QDialog):
    """Display components, evidence and a non-final recommendation."""

    recalculate_requested = Signal(str)

    def __init__(
        self,
        registry_key: str,
        *,
        score: CorterisParticipationScore | None = None,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.registry_key = registry_key.strip()
        if not self.registry_key:
            raise ValueError("registry_key must not be empty")
        try:
            self._theme = ThemeName(theme)
        except (ValueError, TypeError, AttributeError):
            self._theme = ThemeName.DARK
        self._score: CorterisParticipationScore | None = None

        self.setWindowTitle("Corteris Tender AI — оценка участия")
        self.setModal(False)
        self.resize(1000, 800)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        summary = QFrame(self)
        summary.setObjectName("ParticipationScoreSummary")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(16, 14, 16, 14)
        self.score_value = QLabel("—", summary)
        self.score_value.setObjectName("ParticipationScoreValue")
        self.recommendation_label = QLabel(
            "Оценка ещё не рассчитана",
            summary,
        )
        self.recommendation_label.setObjectName(
            "ParticipationRecommendation"
        )
        self.recommendation_label.setWordWrap(True)
        summary_layout.addWidget(self.score_value)
        summary_layout.addWidget(self.recommendation_label, 1)
        root.addWidget(summary)

        self.decision_label = QLabel("Итоговое решение ещё не сформировано", self)
        self.decision_label.setObjectName("ParticipationDecision")
        self.decision_label.setWordWrap(True)
        root.addWidget(self.decision_label)

        note = QLabel(
            "Рейтинг является предварительной рекомендацией и не заменяет "
            "проверку документации, лицензий, ресурсов и договора.",
            self,
        )
        note.setObjectName("ParticipationScoreNote")
        note.setWordWrap(True)
        root.addWidget(note)

        self.components_table = QTableWidget(self)
        self.components_table.setObjectName("ParticipationScoreComponents")
        self.components_table.setColumnCount(4)
        self.components_table.setHorizontalHeaderLabels(
            ("Критерий", "Балл", "Максимум", "Объяснение")
        )
        self.components_table.verticalHeader().setVisible(False)
        self.components_table.horizontalHeader().setStretchLastSection(True)
        self.components_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        root.addWidget(self.components_table, 1)

        self.details = QTextBrowser(self)
        self.details.setObjectName("ParticipationScoreDetails")
        root.addWidget(self.details, 1)

        actions = QHBoxLayout()
        self.recalculate_button = QPushButton(
            "Пересчитать по документам",
            self,
        )
        self.recalculate_button.setObjectName("PrimaryActionButton")
        self.recalculate_button.clicked.connect(
            lambda _checked=False: self.recalculate_requested.emit(
                self.registry_key
            )
        )
        actions.addWidget(self.recalculate_button)
        actions.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).setText("Закрыть")
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        root.addLayout(actions)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("ParticipationScoreStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.apply_theme(self._theme)
        if score is not None:
            self.set_score(score)

    @property
    def score(self) -> CorterisParticipationScore | None:
        return self._score

    def set_score(self, score: CorterisParticipationScore) -> None:
        self._score = score
        self.score_value.setText(f"{score.total_score}/100")
        self.recommendation_label.setText(
            score.recommendation_text
        )
        self.recommendation_label.setProperty(
            "recommendation",
            score.recommendation.value,
        )
        self.recommendation_label.style().unpolish(
            self.recommendation_label
        )
        self.recommendation_label.style().polish(
            self.recommendation_label
        )

        self.components_table.setRowCount(len(score.components))
        for row, component in enumerate(score.components):
            maximum = (
                str(component.maximum)
                if component.maximum > 0
                else "штраф"
            )
            values = (
                component.title,
                str(component.score),
                maximum,
                component.explanation,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.components_table.setItem(row, column, item)

        self.details.setHtml(_render_details(score))
        self.set_busy(False)
        self.set_status("Оценка рассчитана по доступным данным.")

    def set_decision(self, decision: ParticipationDecision) -> None:
        labels = {
            "participate": "Участвовать",
            "participate_after_review": "Участвовать после проверки",
            "do_not_participate": "Не участвовать",
            "data_insufficient": "Недостаточно данных для решения",
        }
        confidence_labels = {
            "high": "высокая",
            "medium": "средняя",
            "low": "низкая",
        }
        reasons = "\n".join(
            f"• {item.title}: {item.detail} ({item.impact:+d})"
            for item in decision.evidence
        ) or "• Причины не сформированы"
        stops = "\n".join(f"• {item}" for item in decision.stop_factors) or "• Нет"
        missing = "\n".join(f"□ {item}" for item in decision.missing) or "• Нет"
        actions = "\n".join(f"✔ {item}" for item in decision.actions) or "• Нет"
        self.decision_label.setText(
            f"Итог: {labels[decision.recommendation.value]} · {decision.score}/100\n"
            f"Уверенность: {decision.confidence:.0%} "
            f"({confidence_labels[decision.confidence_level]})\n"
            f"{decision.summary}\n\nПричины решения:\n{reasons}"
            f"\n\nСтоп-факторы:\n{stops}"
            f"\n\nНе хватает данных:\n{missing}"
            f"\n\nПлан действий:\n{actions}"
        )
        self.decision_label.setProperty(
            "recommendation", decision.recommendation.value
        )
        self.decision_label.style().unpolish(self.decision_label)
        self.decision_label.style().polish(self.decision_label)

    def set_busy(self, busy: bool, *, message: str = "") -> None:
        self.recalculate_button.setEnabled(not busy)
        self.recalculate_button.setText(
            "Расчёт…" if busy else "Пересчитать по документам"
        )
        if message:
            self.set_status(message)

    def set_error(self, message: str) -> None:
        self.set_busy(False)
        self.set_status(message, error=True)

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
                color: {palette.text_primary};
                background-color: {palette.app_background};
            }}
            QFrame#ParticipationScoreSummary {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_default};
                border-radius: 9px;
            }}
            QLabel#ParticipationScoreValue {{
                color: {palette.brand_accent};
                font-size: 28px;
                font-weight: 800;
            }}
            QLabel#ParticipationRecommendation {{
                font-size: 18px;
                font-weight: 700;
            }}
            QLabel#ParticipationRecommendation[recommendation="recommended"] {{
                color: {palette.success};
            }}
            QLabel#ParticipationRecommendation[recommendation="manual_review"] {{
                color: {palette.warning};
            }}
            QLabel#ParticipationRecommendation[recommendation="possible_with_conditions"] {{
                color: {palette.info};
            }}
            QLabel#ParticipationRecommendation[recommendation="not_recommended"] {{
                color: {palette.danger};
            }}
            QLabel#ParticipationScoreNote,
            QLabel#ParticipationDecision,
            QLabel#ParticipationScoreStatus {{
                color: {palette.text_secondary};
            }}
            QLabel#ParticipationDecision[recommendation="participate"] {{
                color: {palette.success};
            }}
            QLabel#ParticipationDecision[recommendation="participate_after_review"],
            QLabel#ParticipationDecision[recommendation="data_insufficient"] {{
                color: {palette.warning};
            }}
            QLabel#ParticipationDecision[recommendation="do_not_participate"] {{
                color: {palette.danger};
            }}
            QLabel#ParticipationScoreStatus[error="true"] {{
                color: {palette.danger};
            }}
            QTableWidget#ParticipationScoreComponents,
            QTextBrowser#ParticipationScoreDetails {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
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
            QPushButton#PrimaryActionButton {{
                color: {palette.text_on_brand};
                background-color: {palette.brand_primary};
                border-color: {palette.brand_primary};
            }}
            """
        )


def _render_details(score: CorterisParticipationScore) -> str:
    def section(title: str, values: Iterable[str]) -> str:
        items = tuple(values)
        rendered = (
            "".join(f"<li>{escape(item)}</li>" for item in items)
            if items
            else "<li>Не выявлено</li>"
        )
        return f"<h3>{escape(title)}</h3><ul>{rendered}</ul>"

    stop_evidence = _render_stop_factor_evidence(score)

    return (
        stop_evidence
        + section("Положительные факторы", score.positive_factors)
        + section("Отрицательные факторы", score.negative_factors)
        + section("Найденные ключевые слова", score.matched_keywords)
        + section("Совпадения ОКПД2", score.matched_okpd2)
        + section("Стоп-факторы", score.stop_factors)
        + section("Недостающие документы", score.missing_documents)
        + section("Источники доказательств", score.evidence_sources)
    )


def _render_stop_factor_evidence(score: CorterisParticipationScore) -> str:
    assessment = score.stop_factor_assessment
    if assessment is None:
        return ""
    status_text = {
        "clear": "CLEAR — блокирующие условия не выявлены",
        "conditional": "CONDITIONAL — участие возможно после устранения условий",
        "data_insufficient": "DATA_INSUFFICIENT — данных недостаточно для решения",
        "blocked_by_requirement": (
            "BLOCKED_BY_REQUIREMENT — участие заблокировано требованием"
        ),
    }[assessment.status.value]
    cards = []
    for factor in assessment.factors:
        evidence = factor.evidence
        cards.append(
            "<li><b>{}</b> [{}]<br>{}<br>"
            "<b>Файл:</b> {} · <b>Страница:</b> {} · "
            "<b>Раздел:</b> {}<br><b>Фрагмент:</b> «{}»<br>"
            "<b>Confidence:</b> {:.0%}<br>"
            "<b>Способ устранения:</b> {}</li>".format(
                escape(factor.title),
                escape(factor.status.value),
                escape(factor.description),
                escape(evidence.document),
                escape(evidence.page),
                escape(evidence.section),
                escape(evidence.quote),
                evidence.confidence,
                escape(evidence.remediation),
            )
        )
    details = (
        f"<ul>{''.join(cards)}</ul>"
        if cards
        else "<p>Факторы не выявлены.</p>"
    )
    return f"<h2>Решение Stop-Factor: {escape(status_text)}</h2>{details}"


__all__ = ["TenderParticipationScoreDialog"]
