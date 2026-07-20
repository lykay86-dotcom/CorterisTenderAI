"""Secure, write-only credential editor for collector providers."""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.tenders.provider_credentials import CredentialState, CredentialStateResult
from app.ui.accessibility.focus import restore_focus


class CredentialDialogOperation(StrEnum):
    NONE = "none"
    SAVE = "save"
    REPLACE = "replace"
    DELETE = "delete"


class ProviderCredentialsDialog(QDialog):
    """Collect one explicit command without reading or retaining stored values."""

    def __init__(
        self,
        provider_id: str,
        display_name: str,
        *,
        state: CredentialStateResult,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._focus_origin = QApplication.focusWidget()
        self.provider_id = provider_id.strip().casefold()
        self.state = state
        self.operation = CredentialDialogOperation.NONE
        self._submitted_value = ""
        self._cancelled = False

        self.setWindowTitle("Управление credential")
        self.setAccessibleName(f"Credential: {display_name}")
        self.setModal(True)
        self.setMinimumWidth(500)

        root = QVBoxLayout(self)
        description = QLabel(
            (
                f"{display_name}: значение передаётся только в защищённое "
                "хранилище и никогда не показывается повторно."
            ),
            self,
        )
        description.setWordWrap(True)
        root.addWidget(description)

        form = QFormLayout()
        self.token_input = QLineEdit(self)
        self.token_input.setObjectName("ProviderCredentialInput")
        self.token_input.setAccessibleName("Новое значение credential")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Введите новое значение")
        form.addRow("API credential:", self.token_input)
        root.addLayout(form)

        self.message = QLabel(state.message, self)
        self.message.setObjectName("ProviderCredentialMessage")
        self.message.setWordWrap(True)
        root.addWidget(self.message)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.delete_button = self.buttons.addButton(
            "Удалить из хранилища",
            QDialogButtonBox.ButtonRole.DestructiveRole,
        )
        self.delete_button.setEnabled(
            state.state in {CredentialState.CONFIGURED, CredentialState.ENVIRONMENT_OVERRIDE}
        )
        self.buttons.accepted.connect(self._accept_if_valid)
        self.buttons.rejected.connect(self.reject)
        self.delete_button.clicked.connect(self._request_delete)
        self.finished.connect(self._schedule_focus_return)
        root.addWidget(self.buttons)

    def take_value(self) -> str:
        value = self._submitted_value
        self._submitted_value = ""
        return value

    def _accept_if_valid(self) -> None:
        if self._cancelled:
            return
        value = self.token_input.text()
        if (
            not value
            or not value.strip()
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
        ):
            self.message.setText("Введите корректное значение credential.")
            self.token_input.setFocus()
            return
        replacing = self.state.state is CredentialState.CONFIGURED
        if (
            replacing
            and QMessageBox.question(
                self,
                "Замена credential",
                "Заменить текущий credential без возможности просмотра?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._submitted_value = value
        self.operation = (
            CredentialDialogOperation.REPLACE if replacing else CredentialDialogOperation.SAVE
        )
        self._clear_widget_value()
        self.buttons.setEnabled(False)
        self.accept()

    def _request_delete(self) -> None:
        if self._cancelled or not self.delete_button.isEnabled():
            return
        if (
            QMessageBox.question(
                self,
                "Удаление credential",
                (
                    "Удалить credential из защищённого хранилища? "
                    "Runtime environment override, если он задан, не изменится."
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.operation = CredentialDialogOperation.DELETE
        self._clear_widget_value()
        self.buttons.setEnabled(False)
        self.accept()

    def reject(self) -> None:
        self._cancelled = True
        self.operation = CredentialDialogOperation.NONE
        self._submitted_value = ""
        self._clear_widget_value()
        super().reject()

    def _clear_widget_value(self) -> None:
        self.token_input.clear()

    def _schedule_focus_return(self, _result: int) -> None:
        QTimer.singleShot(0, self._restore_focus_origin)

    def _restore_focus_origin(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            parent.window().activateWindow()
        fallback = parent.focusProxy() if parent is not None else None
        restore_focus(self._focus_origin, fallback)


__all__ = ["CredentialDialogOperation", "ProviderCredentialsDialog"]
