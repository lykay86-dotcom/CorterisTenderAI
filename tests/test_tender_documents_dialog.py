"""Tests for the local tender-document dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.document_storage import (
    TenderDocumentStore,
)
from app.tenders.http_client import HttpResponse
from app.tenders.models import (
    TenderCustomer,
    TenderDocument,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)
from app.ui.tender_documents_dialog import TenderDocumentsDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _tender() -> UnifiedTender:
    document = TenderDocument(
        id="doc-1",
        name="Техническое задание.pdf",
        url="https://files.example.org/tz.pdf",
        mime_type="application/pdf",
    )
    return UnifiedTender(
        source=TenderSource.EIS,
        external_id="eis-1",
        procurement_number="0373100000126000001",
        title="Монтаж системы видеонаблюдения",
        customer=TenderCustomer(name="Заказчик"),
        source_url="https://zakupki.example.org/1",
        status=TenderStatus.ACCEPTING_APPLICATIONS,
        documents=(document,),
    )


def test_document_dialog_emits_download_requests(tmp_path) -> None:
    app = _app()
    tender = _tender()
    store = TenderDocumentStore(tmp_path / "documents")
    dialog = TenderDocumentsDialog(tender, store)
    requests: list[tuple[object, bool]] = []
    dialog.download_requested.connect(
        lambda selected, force: requests.append(
            (selected, force)
        )
    )

    dialog.download_button.click()
    dialog.force_download_button.click()

    assert requests == [
        (tender, False),
        (tender, True),
    ]
    app.processEvents()


def test_document_dialog_displays_local_file(tmp_path) -> None:
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
            body=b"%PDF-1.4 test document",
        ),
    )

    dialog = TenderDocumentsDialog(tender, store)

    assert dialog.table.rowCount() == 1
    assert dialog.documents[0].available_locally
    assert dialog.open_file_button.isEnabled()
    assert dialog.available_metric.text() == "1"
    app.processEvents()


def test_document_dialog_busy_state_disables_actions(tmp_path) -> None:
    app = _app()
    dialog = TenderDocumentsDialog(
        _tender(),
        TenderDocumentStore(tmp_path / "documents"),
    )

    dialog.set_download_busy(True)

    assert dialog.download_busy
    assert not dialog.download_button.isEnabled()
    assert not dialog.force_download_button.isEnabled()
    assert "фоне" in dialog.status_label.text()
    app.processEvents()
