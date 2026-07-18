"""Deterministic offline harness for Corteris Design System v1."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QGraphicsEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.dashboard.data_state import DataState, DataStatePanel
from app.ui.theme.colors import SemanticColor, ThemeName, get_palette
from app.ui.theme.icons import IconId, get_icon_provider
from app.ui.theme.tokens import DESIGN_TOKENS, IconSize, Spacing
from app.ui.theme.typography import Typography
from app.ui.widgets.button import ButtonSize, ButtonVariant, CorterisButton, IconButton
from app.ui.widgets.card import Card, CardTone, KpiCard
from app.ui.widgets.feedback import InlineMessage, StatusBadge
from app.ui.widgets.form import FormField, FormSection


COMPONENT_GALLERY_VERSION = "corteris-gallery-v1"


class ComponentGallery(QScrollArea):
    """Non-production gallery used by tests and manual visual acceptance."""

    group_ids = ("buttons", "cards", "status", "data_states", "forms", "icons")
    synthetic_long_label = (
        "Очень длинная русская подпись для проверки роста элемента без обрезания смысла"
    )

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = ThemeName(theme)
        self.setObjectName("CorterisComponentGallery")
        self.setWidgetResizable(True)
        self._surface = QWidget(self)
        self._surface.setObjectName("ComponentGallerySurface")
        self._layout = QVBoxLayout(self._surface)
        self._layout.setContentsMargins(
            DESIGN_TOKENS.layout.page_margin,
            DESIGN_TOKENS.layout.page_margin,
            DESIGN_TOKENS.layout.page_margin,
            DESIGN_TOKENS.layout.page_margin,
        )
        self._layout.setSpacing(DESIGN_TOKENS.layout.section_gap)
        self._themed: list[QWidget] = []
        self._build_buttons()
        self._build_cards()
        self._build_status()
        self._build_data_states()
        self._build_forms()
        self._build_icons()
        self._layout.addStretch(1)
        self.setWidget(self._surface)
        self.set_theme(self._theme)

    def _group(self, group_id: str, title: str) -> QVBoxLayout:
        frame = QWidget(self._surface)
        frame.setObjectName(f"GalleryGroup_{group_id}")
        layout = QVBoxLayout(frame)
        layout.setSpacing(int(Spacing.S))
        heading = QLabel(title, frame)
        heading.setObjectName("GalleryHeading")
        layout.addWidget(heading)
        self._layout.addWidget(frame)
        return layout

    def _remember(self, widget: QWidget) -> QWidget:
        self._themed.append(widget)
        return widget

    def _build_buttons(self) -> None:
        group = self._group("buttons", "Кнопки")
        for size in ButtonSize:
            row = QHBoxLayout()
            for variant in ButtonVariant:
                if variant is ButtonVariant.ICON_ONLY:
                    button = IconButton(
                        IconId.ACTION_REFRESH,
                        accessible_name="Обновить",
                        theme=self._theme,
                    )
                else:
                    button = CorterisButton(
                        self.synthetic_long_label
                        if variant is ButtonVariant.PRIMARY
                        else variant.value,
                        variant=variant,
                        size=size,
                        theme=self._theme,
                    )
                row.addWidget(self._remember(button))
            group.addLayout(row)

    def _build_cards(self) -> None:
        group = self._group("cards", "Карточки")
        row = QHBoxLayout()
        row.addWidget(self._remember(Card("Карточка", subtitle="Пояснение", theme=self._theme)))
        row.addWidget(self._remember(Card("Действие", clickable=True, theme=self._theme)))
        row.addWidget(
            self._remember(
                KpiCard("Новые", "12", trend="+2", trend_tone=CardTone.SUCCESS, theme=self._theme)
            )
        )
        group.addLayout(row)

    def _build_status(self) -> None:
        group = self._group("status", "Статусы")
        row = QHBoxLayout()
        for tone in SemanticColor:
            row.addWidget(self._remember(StatusBadge(tone.value, tone=tone, theme=self._theme)))
        group.addLayout(row)
        group.addWidget(
            self._remember(
                InlineMessage(
                    "Требуется проверка",
                    details="Смысл указан текстом.",
                    tone=SemanticColor.WARNING,
                    theme=self._theme,
                )
            )
        )

    def _build_data_states(self) -> None:
        group = self._group("data_states", "Состояния данных")
        for state in (
            DataState.loading(),
            DataState.empty(),
            DataState.error("Повторите попытку"),
            DataState.disabled(),
        ):
            panel = DataStatePanel(theme=self._theme)
            panel.set_state(state)
            group.addWidget(self._remember(panel))

    def _build_forms(self) -> None:
        group = self._group("forms", "Формы")
        section = FormSection("Параметры", theme=self._theme)
        section.add_field(
            FormField(
                "Название",
                QLineEdit(),
                help_text="До 120 символов",
                required=True,
                theme=self._theme,
            )
        )
        group.addWidget(self._remember(section))

    def _build_icons(self) -> None:
        group = self._group("icons", "Иконки")
        row = QHBoxLayout()
        provider = get_icon_provider()
        for icon_id in IconId:
            label = QLabel()
            label.setPixmap(
                provider.icon(icon_id, theme=self._theme).pixmap(int(IconSize.L), int(IconSize.L))
            )
            label.setAccessibleName(icon_id.value)
            label.setToolTip(icon_id.value)
            row.addWidget(label)
        group.addLayout(row)

    def set_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"QWidget#ComponentGallerySurface {{ background-color: {palette.app_background}; }} "
            f"QLabel#GalleryHeading {{ color: {palette.text_primary}; {Typography.H2.css()} }}"
        )
        for widget in self._themed:
            apply_theme = getattr(widget, "apply_theme", None)
            set_theme = getattr(widget, "set_theme", None)
            if callable(apply_theme):
                apply_theme(self._theme)
            elif callable(set_theme):
                set_theme(self._theme)

    def lifecycle_counts(self) -> tuple[int, int]:
        timers = len(self.findChildren(QTimer))
        effects = sum(
            1
            for widget in self.findChildren(QWidget)
            if isinstance(widget.graphicsEffect(), QGraphicsEffect)
        )
        return timers, effects


__all__ = ["COMPONENT_GALLERY_VERSION", "ComponentGallery"]
