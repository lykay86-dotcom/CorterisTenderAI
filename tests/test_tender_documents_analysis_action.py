"""Tests for launching analysis from local documents."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.document_storage import TenderDocumentStore
from app.tenders.http_client import HttpResponse
from app.ui.tender_documents_dialog import TenderDocumentsDialog
from tests.test_tender_documents_dialog import _tender


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_documents_dialog_enables_analysis_for_local_files(
    tmp_path,
) -> None:
    app = _app()
    tender = _tender()
    store = TenderDocumentStore(tmp_path / "documents")
    store.save_response(
        tender,
        tender.documents[0],
        HttpResponse(
            url=tender.documents[0].url,
            status_code=200,
            headers={"content-type": "application/pdf"},
            body=b"%PDF-1.4 local document",
        ),
    )
    dialog = TenderDocumentsDialog(tender, store)
    requested: list[str] = []
    dialog.analysis_requested.connect(requested.append)

    dialog.analysis_button.click()

    assert dialog.analysis_button.isEnabled()
    assert requested == [dialog.registry_key]
    app.processEvents()


def test_documents_dialog_disables_analysis_without_local_files(
    tmp_path,
) -> None:
    app = _app()
    dialog = TenderDocumentsDialog(
        _tender(),
        TenderDocumentStore(tmp_path / "documents"),
    )

    assert not dialog.analysis_button.isEnabled()
    app.processEvents()
