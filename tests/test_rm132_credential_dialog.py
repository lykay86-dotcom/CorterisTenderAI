"""RM-132 Qt credential input contract."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMessageBox

from app.tenders.provider_credentials import CredentialState, CredentialStateResult
from app.ui.provider_credentials_dialog import (
    CredentialDialogOperation,
    ProviderCredentialsDialog,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _state(state: CredentialState) -> CredentialStateResult:
    return CredentialStateResult(
        provider_id="mos_supplier",
        secret_name="api_key",
        state=state,
        message="Безопасное состояние",
        observed_at="2026-07-17T00:00:00+00:00",
    )


def test_dialog_opens_without_prefill_and_clears_submitted_widget_text() -> None:
    _app()
    sentinel = "RM132_SECRET_SENTINEL_DIALOG"
    dialog = ProviderCredentialsDialog(
        "mos_supplier",
        "Портал поставщиков",
        state=_state(CredentialState.NOT_CONFIGURED),
    )

    assert dialog.token_input.text() == ""
    assert "Сохранён" not in dialog.token_input.placeholderText()
    dialog.token_input.setText(sentinel)
    dialog._accept_if_valid()

    assert dialog.result() == dialog.DialogCode.Accepted
    assert dialog.operation is CredentialDialogOperation.SAVE
    assert dialog.token_input.text() == ""
    assert dialog.take_value() == sentinel
    assert dialog.take_value() == ""
    assert sentinel not in dialog.accessibleName()
    assert sentinel not in dialog.token_input.accessibleName()


def test_replacement_and_delete_require_confirmation(monkeypatch) -> None:
    _app()
    answers = iter(
        [
            QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        ]
    )
    monkeypatch.setattr(QMessageBox, "question", lambda *_args, **_kwargs: next(answers))
    dialog = ProviderCredentialsDialog(
        "mos_supplier",
        "Портал поставщиков",
        state=_state(CredentialState.CONFIGURED),
    )
    dialog.token_input.setText("replacement")

    dialog._accept_if_valid()
    assert dialog.result() != dialog.DialogCode.Accepted
    dialog._accept_if_valid()
    assert dialog.operation is CredentialDialogOperation.REPLACE

    delete_dialog = ProviderCredentialsDialog(
        "mos_supplier",
        "Портал поставщиков",
        state=_state(CredentialState.CONFIGURED),
    )
    delete_dialog._request_delete()
    assert delete_dialog.result() != delete_dialog.DialogCode.Accepted
    delete_dialog._request_delete()
    assert delete_dialog.operation is CredentialDialogOperation.DELETE


def test_cancel_and_repeated_submit_leave_no_secret_in_widget_tree() -> None:
    _app()
    sentinel = "RM132_SECRET_SENTINEL_CANCEL"
    dialog = ProviderCredentialsDialog(
        "b2b_center",
        "B2B-Center",
        state=_state(CredentialState.NOT_CONFIGURED),
    )
    dialog.token_input.setText(sentinel)
    dialog.reject()
    dialog._accept_if_valid()

    assert dialog.operation is CredentialDialogOperation.NONE
    assert dialog.take_value() == ""
    assert all(
        sentinel not in widget.text() for widget in dialog.findChildren(type(dialog.message))
    )
