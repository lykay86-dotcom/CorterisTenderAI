"""Form presentation wrappers that do not own validation decisions."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.tokens import BorderWidth, Radius, Spacing
from app.ui.theme.typography import Typography


class FormField(QWidget):
    def __init__(
        self,
        label: str,
        control: QWidget,
        *,
        help_text: str = "",
        required: bool = False,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.control = control
        self._theme = ThemeName(theme)
        self.setObjectName("CorterisFormField")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.XS))
        self.label = QLabel(f"{label}{' *' if required else ''}", self)
        self.label.setObjectName("FormFieldLabel")
        self.help_label = QLabel(help_text, self)
        self.help_label.setObjectName("FormFieldHelp")
        self.help_label.setWordWrap(True)
        self.help_label.setVisible(bool(help_text))
        self.error_label = QLabel("", self)
        self.error_label.setObjectName("FormFieldError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        control.setParent(self)
        layout.addWidget(self.label)
        layout.addWidget(control)
        layout.addWidget(self.help_label)
        layout.addWidget(self.error_label)
        self.setAccessibleName(label)
        self.apply_theme(self._theme)

    def set_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))
        self.control.setProperty("validationState", "error" if message else "normal")
        self.setAccessibleDescription(message or self.help_label.text())
        self.apply_theme(self._theme)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        border = palette.danger if self.error_label.text() else palette.border_default
        self.setStyleSheet(
            f"""
            QWidget#CorterisFormField {{ background: transparent; border: none; }}
            QLabel#FormFieldLabel {{ color: {palette.text_primary}; {Typography.BODY_M.css()} }}
            QLabel#FormFieldHelp {{ color: {palette.text_muted}; {Typography.CAPTION.css()} }}
            QLabel#FormFieldError {{ color: {palette.danger}; {Typography.CAPTION.css()} }}
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
                color: {palette.text_primary}; background-color: {palette.input_background};
                border: {int(BorderWidth.DEFAULT)}px solid {border};
                border-radius: {int(Radius.MEDIUM)}px; padding: {int(Spacing.S)}px;
            }}
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
                border: {int(BorderWidth.FOCUS)}px solid {palette.focus_ring};
            }}
            """
        )


class FormSection(QFrame):
    def __init__(
        self,
        title: str,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = ThemeName(theme)
        self._fields: list[FormField] = []
        self.setObjectName("CorterisFormSection")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            int(Spacing.L), int(Spacing.L), int(Spacing.L), int(Spacing.L)
        )
        self._layout.setSpacing(int(Spacing.M))
        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("FormSectionTitle")
        self._layout.addWidget(self.title_label)
        self.setAccessibleName(title)
        self.apply_theme(self._theme)

    @property
    def fields(self) -> tuple[FormField, ...]:
        return tuple(self._fields)

    def add_field(self, field: FormField) -> None:
        self._fields.append(field)
        self._layout.addWidget(field)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"QFrame#CorterisFormSection {{ background-color: {palette.card_background}; "
            f"border: {int(BorderWidth.DEFAULT)}px solid {palette.border_default}; "
            f"border-radius: {int(Radius.LARGE)}px; }} "
            f"QLabel#FormSectionTitle {{ color: {palette.text_primary}; border: none; "
            f"background: transparent; {Typography.H3.css()} }}"
        )
        for field in self._fields:
            field.apply_theme(self._theme)


__all__ = ["FormField", "FormSection"]
