"""Button system for Corteris Tender AI."""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import Property, QSize, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QPushButton, QWidget

from app.ui.theme.colors import ThemeName, ThemePalette, get_palette
from app.ui.theme.typography import Typography


class ButtonVariant(StrEnum):
    """Supported visual button variants."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    OUTLINE = "outline"
    GHOST = "ghost"
    DANGER = "danger"


class ButtonSize(StrEnum):
    """Supported button sizes."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class CorterisButton(QPushButton):
    """Theme-aware button used across the Corteris Tender AI interface."""

    def __init__(
        self,
        text: str = "",
        *,
        variant: ButtonVariant | str = ButtonVariant.PRIMARY,
        size: ButtonSize | str = ButtonSize.MEDIUM,
        theme: ThemeName | str = ThemeName.DARK,
        icon_text: str = "",
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
        self._loading_timer.setInterval(160)
        self._loading_timer.timeout.connect(self._advance_loading)

        self.setObjectName("CorterisButton")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setAutoDefault(False)
        self.setDefault(False)
        self.setAccessibleName(text or "Кнопка")
        self._apply_size()
        self._apply_theme()
        self._refresh_text()

    def get_variant(self) -> str:
        return self._variant.value

    def set_variant(self, value: ButtonVariant | str) -> None:
        variant = ButtonVariant(value)
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
    def icon_text(self) -> str:
        return self._icon_text

    @icon_text.setter
    def icon_text(self, value: str) -> None:
        self._icon_text = value
        self._refresh_text()

    def setText(self, text: str) -> None:  # noqa: N802
        self._original_text = text
        self.setAccessibleName(text or "Кнопка")
        self._refresh_text()

    def _advance_loading(self) -> None:
        self._loading_frame = (self._loading_frame + 1) % 4
        self._refresh_text()

    def _refresh_text(self) -> None:
        if self._loading:
            dots = "." * self._loading_frame
            display = f"Выполнение{dots}"
        else:
            display = self._original_text

        if self._icon_text and not self._loading:
            display = f"{self._icon_text}  {display}" if display else self._icon_text

        QPushButton.setText(self, display)

    def _apply_size(self) -> None:
        metrics = {
            ButtonSize.SMALL: (30, 10, 7, Typography.BODY_S.css()),
            ButtonSize.MEDIUM: (36, 14, 9, Typography.BUTTON.css()),
            ButtonSize.LARGE: (44, 18, 11, Typography.BODY_L.css()),
        }
        height, horizontal_padding, vertical_padding, _ = metrics[self._size]
        self.setMinimumHeight(height)
        self.setIconSize(QSize(height - 12, height - 12))
        self.setProperty("horizontalPadding", horizontal_padding)
        self.setProperty("verticalPadding", vertical_padding)

    def _variant_colors(
        self,
        palette: ThemePalette,
    ) -> tuple[str, str, str, str, str, str]:
        if self._variant == ButtonVariant.PRIMARY:
            return (
                palette.brand_primary,
                palette.text_on_brand,
                palette.brand_primary_hover,
                palette.brand_primary_pressed,
                palette.brand_primary,
                palette.text_on_brand,
            )

        if self._variant == ButtonVariant.SECONDARY:
            return (
                palette.elevated_background,
                palette.text_primary,
                palette.hover_background,
                palette.selected_background,
                palette.border_default,
                palette.text_disabled,
            )

        if self._variant == ButtonVariant.OUTLINE:
            return (
                "transparent",
                palette.brand_primary,
                palette.brand_accent_soft,
                palette.selected_background,
                palette.brand_primary,
                palette.text_disabled,
            )

        if self._variant == ButtonVariant.GHOST:
            return (
                "transparent",
                palette.text_secondary,
                palette.hover_background,
                palette.selected_background,
                "transparent",
                palette.text_disabled,
            )

        return (
            palette.danger,
            palette.text_on_danger,
            palette.danger_background,
            palette.danger,
            palette.danger,
            palette.text_on_danger,
        )

    def _apply_theme(self) -> None:
        palette = get_palette(self._theme)
        (
            background,
            foreground,
            hover_background,
            pressed_background,
            border,
            disabled_foreground,
        ) = self._variant_colors(palette)

        metrics = {
            ButtonSize.SMALL: (10, 7, 6, Typography.BODY_S.css()),
            ButtonSize.MEDIUM: (14, 9, 7, Typography.BUTTON.css()),
            ButtonSize.LARGE: (18, 11, 9, Typography.BODY_L.css()),
        }
        horizontal_padding, vertical_padding, radius, font_css = metrics[self._size]

        disabled_background = (
            palette.neutral_background
            if self._variant in {ButtonVariant.PRIMARY, ButtonVariant.DANGER}
            else "transparent"
        )

        self.setStyleSheet(
            f"""
            QPushButton#CorterisButton {{
                background-color: {background};
                color: {foreground};
                border: 1px solid {border};
                border-radius: {radius}px;
                padding: {vertical_padding}px {horizontal_padding}px;
                {font_css}
            }}
            QPushButton#CorterisButton:hover {{
                background-color: {hover_background};
            }}
            QPushButton#CorterisButton:pressed {{
                background-color: {pressed_background};
            }}
            QPushButton#CorterisButton:disabled {{
                background-color: {disabled_background};
                color: {disabled_foreground};
                border-color: {palette.border_subtle};
            }}
            QPushButton#CorterisButton:focus {{
                border: 2px solid {palette.focus_ring};
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


class IconButton(GhostButton):
    """Compact square button for icon-only actions."""

    def __init__(
        self,
        icon_text: str,
        *,
        accessible_name: str,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "",
            icon_text=icon_text,
            size=ButtonSize.SMALL,
            theme=theme,
            parent=parent,
        )
        self.setFixedSize(34, 34)
        self.setAccessibleName(accessible_name)
        self.setToolTip(accessible_name)


__all__ = [
    "ButtonSize",
    "ButtonVariant",
    "CorterisButton",
    "DangerButton",
    "GhostButton",
    "IconButton",
    "OutlineButton",
    "PrimaryButton",
    "SecondaryButton",
]
