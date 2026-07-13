"""Secure credential editor for collector API sources."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class ProviderCredentialsDialog(QDialog):
    """Collect a replacement API credential without ever showing its value."""

    def __init__(
        self,
        provider_id: str,
        display_name: str,
        *,
        configured: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.provider_id = provider_id.strip().casefold()
        self.setWindowTitle("Настройка API-ключа")
        self.setModal(True)
        self.setMinimumWidth(500)

        root = QVBoxLayout(self)
        description = QLabel(
            (
                f"{display_name}: ключ сохраняется в защищённом "
                "хранилище учётных данных Windows и не попадает в проект."
            ),
            self,
        )
        description.setWordWrap(True)
        root.addWidget(description)

        form = QFormLayout()
        self.token_input = QLineEdit(self)
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText(
            "Введите новый ключ для сохранения" if configured else "Bearer API-ключ"
        )
        form.addRow("Bearer API-ключ:", self.token_input)
        root.addLayout(form)

        self.message = QLabel("", self)
        self.message.setWordWrap(True)
        root.addWidget(self.message)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @property
    def token(self) -> str:
        return self.token_input.text().strip()

    def _accept_if_valid(self) -> None:
        if not self.token:
            self.message.setText("Введите API-ключ.")
            self.token_input.setFocus()
            return
        self.accept()


__all__ = ["ProviderCredentialsDialog"]
