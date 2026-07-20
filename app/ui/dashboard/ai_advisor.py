"""AI Advisor widget for Corteris Tender AI Dashboard 1.0."""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.dashboard.data_state import DataState, DataStateKind
from app.ui.theme.colors import (
    SemanticColor,
    ThemeName,
    get_palette,
)
from app.ui.theme.typography import Typography
from app.ui.widgets.button import PrimaryButton


class AiStatus(StrEnum):
    """Visual status of the AI subsystem."""

    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    WARNING = "warning"


class AiAdvisor(QFrame):
    """Decision-support panel for the Dashboard.

    This commit contains the complete visual component only. Business data
    will be connected in the next commit through an Advisor ViewModel.
    """

    action_requested = Signal(str)

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self._status = AiStatus.ONLINE
        self._action_key = ""
        self._compact = False
        self._data_state = DataState.ready()

        self.setObjectName("AiAdvisor")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.setMinimumWidth(320)
        self.setAccessibleName("AI Advisor")
        self.setAccessibleDescription("Рекомендации, приоритетный тендер и следующий шаг")

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(20, 18, 20, 18)
        self._root.setSpacing(14)

        self._build_header()
        self._build_summary()
        self._build_focus()
        self._build_reasons()
        self._build_warning()
        self._build_action()

        self.apply_theme(self._theme)
        self.set_empty_state()

    def _build_header(self) -> None:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        badge = QLabel("AI", self)
        badge.setObjectName("AiAdvisorBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(38, 38)

        title_column = QVBoxLayout()
        title_column.setSpacing(2)

        title = QLabel("AI Advisor", self)
        title.setObjectName("AiAdvisorTitle")

        subtitle = QLabel(
            "Рекомендации и следующий лучший шаг",
            self,
        )
        subtitle.setObjectName("AiAdvisorSubtitle")
        subtitle.setWordWrap(True)

        title_column.addWidget(title)
        title_column.addWidget(subtitle)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("AiAdvisorStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        header.addLayout(title_column, 1)
        header.addWidget(
            self.status_label,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )

        self._root.addLayout(header)

    def _build_summary(self) -> None:
        summary = QFrame(self)
        summary.setObjectName("AiAdvisorSummary")

        layout = QHBoxLayout(summary)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.new_tenders_value = self._metric("0", "новых")
        self.recommended_value = self._metric("0", "рекомендуется")
        self.attention_value = self._metric("0", "внимание")

        layout.addWidget(self.new_tenders_value, 1)
        layout.addWidget(self.recommended_value, 1)
        layout.addWidget(self.attention_value, 1)

        self._root.addWidget(summary)

    def _metric(self, value: str, caption: str) -> QWidget:
        container = QWidget(self)
        container.setObjectName("AiAdvisorMetric")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        value_label = QLabel(value, container)
        value_label.setObjectName("AiAdvisorMetricValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        caption_label = QLabel(caption, container)
        caption_label.setObjectName("AiAdvisorMetricCaption")
        caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(value_label)
        layout.addWidget(caption_label)

        container.value_label = value_label  # type: ignore[attr-defined]
        return container

    def _build_focus(self) -> None:
        focus = QFrame(self)
        focus.setObjectName("AiAdvisorFocus")

        layout = QVBoxLayout(focus)
        layout.setContentsMargins(14, 13, 14, 13)
        layout.setSpacing(8)

        label = QLabel("Сегодняшний приоритет", focus)
        label.setObjectName("AiAdvisorSectionLabel")

        self.focus_title = QLabel(
            "Приоритетный тендер пока не выбран",
            focus,
        )
        self.focus_title.setObjectName("AiAdvisorFocusTitle")
        self.focus_title.setWordWrap(True)

        meta = QHBoxLayout()
        meta.setSpacing(10)

        self.focus_number = QLabel("—", focus)
        self.focus_number.setObjectName("AiAdvisorMeta")

        self.focus_amount = QLabel("—", focus)
        self.focus_amount.setObjectName("AiAdvisorMeta")

        meta.addWidget(self.focus_number)
        meta.addWidget(self.focus_amount)
        meta.addStretch(1)

        score_row = QHBoxLayout()
        score_row.setSpacing(10)

        score_caption = QLabel("AI Score", focus)
        score_caption.setObjectName("AiAdvisorSectionLabel")

        self.score_value = QLabel("—", focus)
        self.score_value.setObjectName("AiAdvisorScore")

        score_row.addWidget(score_caption)
        score_row.addStretch(1)
        score_row.addWidget(self.score_value)

        self.score_bar = QProgressBar(focus)
        self.score_bar.setObjectName("AiAdvisorScoreBar")
        self.score_bar.setRange(0, 100)
        self.score_bar.setValue(0)
        self.score_bar.setTextVisible(False)
        self.score_bar.setFixedHeight(8)

        layout.addWidget(label)
        layout.addWidget(self.focus_title)
        layout.addLayout(meta)
        layout.addLayout(score_row)
        layout.addWidget(self.score_bar)

        self._root.addWidget(focus)

    def _build_reasons(self) -> None:
        reasons = QFrame(self)
        reasons.setObjectName("AiAdvisorReasons")

        layout = QVBoxLayout(reasons)
        layout.setContentsMargins(14, 13, 14, 13)
        layout.setSpacing(7)

        title = QLabel("Почему", reasons)
        title.setObjectName("AiAdvisorSectionLabel")
        layout.addWidget(title)

        self.reason_labels: list[QLabel] = []
        for _ in range(4):
            label = QLabel("• Нет данных", reasons)
            label.setObjectName("AiAdvisorReason")
            label.setWordWrap(True)
            label.setVisible(False)
            layout.addWidget(label)
            self.reason_labels.append(label)

        self._root.addWidget(reasons)

    def _build_warning(self) -> None:
        self.warning_frame = QFrame(self)
        self.warning_frame.setObjectName("AiAdvisorWarning")

        layout = QHBoxLayout(self.warning_frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(9)

        icon = QLabel("!", self.warning_frame)
        icon.setObjectName("AiAdvisorWarningIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(24, 24)

        self.warning_label = QLabel(
            "Предупреждений нет",
            self.warning_frame,
        )
        self.warning_label.setObjectName("AiAdvisorWarningText")
        self.warning_label.setWordWrap(True)

        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.warning_label, 1)

        self._root.addWidget(self.warning_frame)

    def _build_action(self) -> None:
        self._root.addStretch(1)

        self.action_caption = QLabel(
            "Следующее действие",
            self,
        )
        self.action_caption.setObjectName("AiAdvisorSectionLabel")

        self.action_button = PrimaryButton(
            "Открыть тендер",
            theme=self._theme,
            parent=self,
        )
        self.action_button.setObjectName("DashboardFindTendersAction")
        self.action_button.clicked.connect(self._emit_action)

        self._root.addWidget(self.action_caption)
        self._root.addWidget(self.action_button)

    @property
    def data_state(self) -> DataState:
        return self._data_state

    def set_data_state(self, state: DataState) -> None:
        """Render a unified Dashboard data state."""
        previous = self._data_state
        self._data_state = state

        if state.kind == DataStateKind.READY:
            self.set_busy(False)
            if previous.kind in {
                DataStateKind.LOADING,
                DataStateKind.ERROR,
                DataStateKind.PARTIAL,
            }:
                self.set_warning("")
            return

        if state.kind == DataStateKind.LOADING:
            self.set_busy(
                True,
                state.title or "Обновление рекомендаций",
            )
            return

        self.set_busy(False)

        if state.kind == DataStateKind.EMPTY:
            self.set_empty_state()
            self.set_focus(
                title=state.title or "Запустите поиск тендеров, чтобы получить рекомендацию"
            )
            self.set_warning(state.message)
            self.set_action(
                text=state.action_text or "Найти тендеры",
                action_key=state.action_key or "find_tenders",
            )
        elif state.kind == DataStateKind.ERROR:
            self.set_status(AiStatus.OFFLINE)
            self.set_focus(title=state.title or "AI-рекомендации недоступны")
            self.set_reasons([])
            self.set_warning(state.message or "Повторите загрузку данных.")
            self.set_action(
                text=state.action_text or "Повторить",
                action_key=state.action_key or "refresh_dashboard",
            )
        elif state.kind == DataStateKind.PARTIAL:
            self.set_status(AiStatus.WARNING)
            self.set_warning(state.message or "Часть рекомендаций недоступна.")
            if state.has_action:
                self.set_action(
                    text=state.action_text,
                    action_key=state.action_key,
                )

    def set_compact(self, compact: bool) -> None:
        """Switch between normal and compact spacing."""
        self._compact = bool(compact)
        margins = (16, 14, 16, 14) if self._compact else (20, 18, 20, 18)
        self._root.setContentsMargins(*margins)
        self._root.setSpacing(10 if self._compact else 14)

    def set_busy(self, busy: bool, text: str = "Выполняется анализ") -> None:
        """Display a loading state without losing the current recommendation."""
        if busy:
            self.set_status(AiStatus.BUSY, "● Анализ")
            self.action_button.set_loading(True)
            self.action_caption.setText(text)
        else:
            self.action_button.set_loading(False)
            self.action_caption.setText("Следующее действие")
            self.set_status(AiStatus.ONLINE)

    def set_status(
        self,
        status: AiStatus | str,
        text: str | None = None,
    ) -> None:
        """Update the AI subsystem status badge."""
        self._status = AiStatus(status)
        default_text = {
            AiStatus.ONLINE: "● Online",
            AiStatus.OFFLINE: "● Offline",
            AiStatus.BUSY: "● Анализ",
            AiStatus.WARNING: "● Внимание",
        }
        self.status_label.setText(text or default_text[self._status])
        self.apply_theme(self._theme)

    def set_metrics(
        self,
        *,
        new_tenders: int,
        recommended: int,
        attention: int,
    ) -> None:
        """Update the three summary counters."""
        self.new_tenders_value.value_label.setText(str(new_tenders))  # type: ignore[attr-defined]
        self.recommended_value.value_label.setText(str(recommended))  # type: ignore[attr-defined]
        self.attention_value.value_label.setText(str(attention))  # type: ignore[attr-defined]

    def set_focus(
        self,
        *,
        title: str,
        number: str = "",
        amount: str = "",
        score: int | None = None,
    ) -> None:
        """Display the current priority tender."""
        self.focus_title.setText(title or "Приоритетный тендер не выбран")
        self.focus_number.setText(number or "—")
        self.focus_amount.setText(amount or "—")

        normalized_score = 0 if score is None else max(0, min(score, 100))
        self.score_bar.setValue(normalized_score)
        self.score_value.setText("—" if score is None else f"{normalized_score}/100")
        self.score_bar.setAccessibleName("AI Score")
        self.score_bar.setAccessibleDescription(
            "Оценка отсутствует" if score is None else f"Оценка тендера {normalized_score} из 100"
        )
        self.apply_theme(self._theme)

    def set_reasons(self, reasons: list[str]) -> None:
        """Display up to four recommendation reasons."""
        for index, label in enumerate(self.reason_labels):
            if index < len(reasons):
                label.setText(f"✓ {reasons[index]}")
                label.setVisible(True)
            else:
                label.clear()
                label.setVisible(False)

    def set_warning(self, text: str = "") -> None:
        """Display or hide the warning block."""
        normalized = text.strip()
        self.warning_label.setText(normalized or "Предупреждений нет")
        self.warning_frame.setVisible(bool(normalized))
        self.warning_frame.setAccessibleName("Предупреждение AI")
        self.warning_frame.setAccessibleDescription(normalized)

    def set_action(
        self,
        *,
        text: str,
        action_key: str,
        enabled: bool = True,
    ) -> None:
        """Configure the primary advisor action."""
        self._action_key = action_key.strip()
        self.action_button.setText(text.strip() or "Продолжить")
        self.action_button.setEnabled(bool(enabled))
        self.action_button.setAccessibleDescription(f"Действие AI: {self.action_button.text()}")

    def set_empty_state(self) -> None:
        """Show a useful state before AI data is available."""
        self.set_status(AiStatus.ONLINE)
        self.set_metrics(
            new_tenders=0,
            recommended=0,
            attention=0,
        )
        self.set_focus(
            title="Запустите поиск тендеров, чтобы получить рекомендацию",
        )
        self.set_reasons([])
        self.set_warning("")
        self.set_action(
            text="Найти тендеры",
            action_key="find_tenders",
        )

    def apply_theme(self, theme: ThemeName | str) -> None:
        """Apply light or dark theme."""
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        status_color = {
            AiStatus.ONLINE: palette.success,
            AiStatus.OFFLINE: palette.danger,
            AiStatus.BUSY: palette.info,
            AiStatus.WARNING: palette.warning,
        }[self._status]

        warning_foreground, warning_background = palette.semantic(SemanticColor.WARNING)

        score = self.score_bar.value()
        if score >= 80:
            score_color = palette.success
        elif score >= 60:
            score_color = palette.warning
        elif score > 0:
            score_color = palette.danger
        else:
            score_color = palette.brand_accent

        self.setStyleSheet(
            f"""
            QFrame#AiAdvisor {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 14px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QLabel#AiAdvisorBadge {{
                background-color: {palette.brand_accent_soft};
                color: {palette.brand_accent};
                border-radius: 10px;
                {Typography.BUTTON.css()}
            }}
            QLabel#AiAdvisorTitle {{
                color: {palette.text_primary};
                {Typography.H3.css()}
            }}
            QLabel#AiAdvisorSubtitle {{
                color: {palette.text_muted};
                {Typography.BODY_S.css()}
            }}
            QLabel#AiAdvisorStatus {{
                color: {status_color};
                background-color: {palette.elevated_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 8px;
                padding: 4px 8px;
                {Typography.CAPTION.css()}
            }}
            QFrame#AiAdvisorSummary,
            QFrame#AiAdvisorFocus,
            QFrame#AiAdvisorReasons {{
                background-color: {palette.input_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 10px;
            }}
            QWidget#AiAdvisorMetric {{
                background: transparent;
                border: none;
            }}
            QLabel#AiAdvisorMetricValue {{
                color: {palette.text_primary};
                {Typography.H3.css()}
            }}
            QLabel#AiAdvisorMetricCaption {{
                color: {palette.text_muted};
                {Typography.CAPTION.css()}
            }}
            QLabel#AiAdvisorSectionLabel {{
                color: {palette.text_muted};
                {Typography.CAPTION.css()}
            }}
            QLabel#AiAdvisorFocusTitle {{
                color: {palette.text_primary};
                {Typography.BODY_L.css()}
            }}
            QLabel#AiAdvisorMeta {{
                color: {palette.text_secondary};
                {Typography.BODY_S.css()}
            }}
            QLabel#AiAdvisorScore {{
                color: {score_color};
                {Typography.BUTTON.css()}
            }}
            QProgressBar#AiAdvisorScoreBar {{
                background-color: {palette.border_subtle};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar#AiAdvisorScoreBar::chunk {{
                background-color: {score_color};
                border-radius: 4px;
            }}
            QLabel#AiAdvisorReason {{
                color: {palette.text_secondary};
                {Typography.BODY_S.css()}
            }}
            QFrame#AiAdvisorWarning {{
                background-color: {warning_background};
                border: 1px solid {warning_foreground};
                border-radius: 10px;
            }}
            QLabel#AiAdvisorWarningIcon {{
                color: {warning_foreground};
                background-color: transparent;
                {Typography.BUTTON.css()}
            }}
            QLabel#AiAdvisorWarningText {{
                color: {warning_foreground};
                {Typography.BODY_S.css()}
            }}
            """
        )

        self.action_button.set_theme(self._theme)

    def _emit_action(self) -> None:
        if self._action_key:
            self.action_requested.emit(self._action_key)


__all__ = ["AiAdvisor", "AiStatus"]
