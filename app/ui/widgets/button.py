"""Canonical token-backed button family for Corteris Tender AI."""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import Property, QSize, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QPushButton, QWidget

from app.ui.theme.colors import ThemeName, ThemePalette, get_palette
from app.ui.theme.icons import IconId, get_icon_provider
from app.ui.theme.tokens import BorderWidth, DESIGN_TOKENS
from app.ui.theme.typography import Typography


class ButtonVariant(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    OUTLINE = "outline"
    GHOST = "ghost"
    DANGER = "danger"
    ICON_ONLY = "icon-only"


class ButtonSize(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class CorterisButton(QPushButton):
    """Theme-aware button with stable variants, sizing and loading state."""

    def __init__(
        self,
        text: str = "",
        *,
        variant: ButtonVariant | str = ButtonVariant.PRIMARY,
        size: ButtonSize | str = ButtonSize.MEDIUM,
        theme: ThemeName | str = ThemeName.DARK,
        icon_text: str = "",
        accessible_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._variant = ButtonVariant(variant)
        self._size = ButtonSize(size)
        self._theme = ThemeName(theme)
        self._icon_text = icon_text
        self._loading = False
        self._original_text = text
        self._loading_frame = 0
        self._loading_timer = QTimer(self)
        self._loading_timer.setInterval(DESIGN_TOKENS.motion.loading_frame_ms)
        self._loading_timer.timeout.connect(self._advance_loading)

        if self._variant is ButtonVariant.ICON_ONLY and not accessible_name.strip():
            raise ValueError("icon-only button requires an accessible name")
        self.setObjectName("CorterisButton")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setAutoDefault(False)
        self.setDefault(False)
        self.setAccessibleName(accessible_name.strip() or text or "Кнопка")
        self._apply_size()
        self._apply_theme()
        self._refresh_text()

    def get_variant(self) -> str:
        return self._variant.value

    def set_variant(self, value: ButtonVariant | str) -> None:
        variant = ButtonVariant(value)
        if variant is ButtonVariant.ICON_ONLY and not self.accessibleName().strip():
            raise ValueError("icon-only button requires an accessible name")
        if variant != self._variant:
            self._variant = variant
            self._apply_theme()

    variant = Property(str, get_variant, set_variant)

    def get_size_name(self) -> str:
        return self._size.value

    def set_size_name(self, value: ButtonSize | str) -> None:
        size = ButtonSize(value)
        if size != self._size:
            self._size = size
            self._apply_size()
            self._apply_theme()

    size_name = Property(str, get_size_name, set_size_name)

    def get_theme(self) -> str:
        return self._theme.value

    def set_theme(self, value: ThemeName | str) -> None:
        theme = ThemeName(value)
        if theme != self._theme:
            self._theme = theme
            self._apply_theme()
            if not self.icon().isNull():
                self.update()

    theme = Property(str, get_theme, set_theme)

    def get_loading(self) -> bool:
        return self._loading

    def set_loading(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._loading:
            return
        self._loading = enabled
        self.setEnabled(not enabled)
        self.setCursor(
            QCursor(Qt.CursorShape.WaitCursor)
            if enabled
            else QCursor(Qt.CursorShape.PointingHandCursor)
        )
        if enabled:
            self._loading_frame = 0
            self._loading_timer.start()
        else:
            self._loading_timer.stop()
        self._refresh_text()

    loading = Property(bool, get_loading, set_loading)

    @property
    def loading_timer(self) -> QTimer:
        return self._loading_timer

    @property
    def icon_text(self) -> str:
        return self._icon_text

    @icon_text.setter
    def icon_text(self, value: str) -> None:
        self._icon_text = value
        self._refresh_text()

    def setText(self, text: str) -> None:  # noqa: N802
        self._original_text = text
        if self._variant is not ButtonVariant.ICON_ONLY:
            self.setAccessibleName(text or "Кнопка")
        self._refresh_text()

    def _advance_loading(self) -> None:
        self._loading_frame = (self._loading_frame + 1) % 4
        self._refresh_text()

    def _refresh_text(self) -> None:
        if self._loading:
            display = f"Выполнение{'.' * self._loading_frame}"
            self.setAccessibleName(f"Выполнение: {self._original_text}".rstrip())
        else:
            display = self._original_text
            if self._variant is not ButtonVariant.ICON_ONLY:
                self.setAccessibleName(self._original_text or "Кнопка")
        if self._icon_text and not self._loading:
            display = f"{self._icon_text}  {display}" if display else self._icon_text
        QPushButton.setText(self, display)

    def _apply_size(self) -> None:
        metric = DESIGN_TOKENS.controls[self._size.value]
        self.setMinimumHeight(metric.height)
        self.setIconSize(QSize(metric.icon_size, metric.icon_size))
        self.setProperty("horizontalPadding", metric.horizontal_padding)
        self.setProperty("verticalPadding", metric.vertical_padding)

    def _variant_colors(self, palette: ThemePalette) -> tuple[str, str, str, str, str, str]:
        transparent = DESIGN_TOKENS.transparent
        if self._variant is ButtonVariant.PRIMARY:
            return (palette.brand_primary, palette.text_on_brand, palette.brand_primary_hover, palette.brand_primary_pressed, palette.brand_primary, palette.text_on_brand)
        if self._variant is ButtonVariant.SECONDARY:
            return (palette.elevated_background, palette.text_primary, palette.hover_background, palette.selected_background, palette.border_default, palette.text_disabled)
        if self._variant is ButtonVariant.OUTLINE:
            return (transparent, palette.brand_primary, palette.brand_accent_soft, palette.selected_background, palette.brand_primary, palette.text_disabled)
        if self._variant in {ButtonVariant.GHOST, ButtonVariant.ICON_ONLY}:
            return (transparent, palette.text_secondary, palette.hover_background, palette.selected_background, transparent, palette.text_disabled)
        return (palette.danger, palette.text_on_danger, palette.danger_background, palette.danger, palette.danger, palette.text_on_danger)

    def _apply_theme(self) -> None:
        palette = get_palette(self._theme)
        background, foreground, hover, pressed, border, disabled = self._variant_colors(palette)
        metric = DESIGN_TOKENS.controls[self._size.value]
        font_css = {
            ButtonSize.SMALL: Typography.BODY_S.css(),
            ButtonSize.MEDIUM: Typography.BUTTON.css(),
            ButtonSize.LARGE: Typography.BODY_L.css(),
        }[self._size]
        disabled_background = (
            palette.neutral_background
            if self._variant in {ButtonVariant.PRIMARY, ButtonVariant.DANGER}
            else DESIGN_TOKENS.transparent
        )
        self.setStyleSheet(
            f"""
            QPushButton#CorterisButton {{
                background-color: {background}; color: {foreground};
                border: {int(BorderWidth.DEFAULT)}px solid {border};
                border-radius: {metric.radius}px;
                padding: {metric.vertical_padding}px {metric.horizontal_padding}px;
                {font_css}
            }}
            QPushButton#CorterisButton:hover {{ background-color: {hover}; }}
            QPushButton#CorterisButton:pressed {{ background-color: {pressed}; }}
            QPushButton#CorterisButton:disabled {{
                background-color: {disabled_background}; color: {disabled};
                border-color: {palette.border_subtle};
            }}
            QPushButton#CorterisButton:focus {{
                border: {int(BorderWidth.FOCUS)}px solid {palette.focus_ring};
            }}
            """
        )


class PrimaryButton(CorterisButton):
    def __init__(self, text: str = "", **kwargs) -> None:
        super().__init__(text, variant=ButtonVariant.PRIMARY, **kwargs)


class SecondaryButton(CorterisButton):
    def __init__(self, text: str = "", **kwargs) -> None:
        super().__init__(text, variant=ButtonVariant.SECONDARY, **kwargs)


class OutlineButton(CorterisButton):
    def __init__(self, text: str = "", **kwargs) -> None:
        super().__init__(text, variant=ButtonVariant.OUTLINE, **kwargs)


class GhostButton(CorterisButton):
    def __init__(self, text: str = "", **kwargs) -> None:
        super().__init__(text, variant=ButtonVariant.GHOST, **kwargs)


class DangerButton(CorterisButton):
    def __init__(self, text: str = "", **kwargs) -> None:
        super().__init__(text, variant=ButtonVariant.DANGER, **kwargs)


class IconButton(CorterisButton):
    """Compact square icon-only action with mandatory accessible text."""

    def __init__(
        self,
        icon: IconId | str,
        *,
        accessible_name: str,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        if not accessible_name.strip():
            raise ValueError("icon-only button requires an accessible name")
        super().__init__(
            "",
            variant=ButtonVariant.ICON_ONLY,
            size=ButtonSize.SMALL,
            theme=theme,
            accessible_name=accessible_name,
            parent=parent,
        )
        try:
            semantic_id = icon if isinstance(icon, IconId) else IconId(icon)
        except ValueError:
            self.icon_text = str(icon)
        else:
            self.setIcon(get_icon_provider().icon(semantic_id, theme=theme))
        side = DESIGN_TOKENS.controls[ButtonSize.SMALL.value].height
        self.setFixedSize(side, side)
        self.setAccessibleName(accessible_name)
        self.setToolTip(accessible_name)


__all__ = [
    "ButtonSize", "ButtonVariant", "CorterisButton", "DangerButton", "GhostButton",
    "IconButton", "OutlineButton", "PrimaryButton", "SecondaryButton",
]
