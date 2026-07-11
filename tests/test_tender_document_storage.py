"""Tests for local tender-document storage and duplicate control."""

from __future__ import annotations

from dataclasses import dataclass

from app.tenders.document_storage import (
    DocumentDownloadStatus,
    TenderDocumentDownloadService,
    TenderDocumentStore,
)
from app.tenders.http_client import HttpResponse
from app.tenders.models import (
    TenderCustomer,
    TenderDocument,
    TenderSource,
    UnifiedTender,
)
from app.tenders.provider_base import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderHealth,
    ProviderHealthStatus,
    TenderProvider,
    TenderSearchQuery,
    TenderSearchResult,
)
from app.tenders.provider_registry import TenderProviderRegistry


class FakeTransport:
    def __init__(self, responses: dict[str, HttpResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, **_kwargs) -> HttpResponse:
        self.calls.append(url)
        return self.responses[url]


@dataclass
class FakeProvider(TenderProvider):
    descriptor: ProviderDescriptor
    documents: tuple[TenderDocument, ...]
    list_calls: int = 0

    def search(self, query: TenderSearchQuery) -> TenderSearchResult:
        return TenderSearchResult(
            provider_id=self.descriptor.id,
            items=(),
            page=query.page,
            page_size=query.page_size,
        )

    def get_tender(self, external_id: str) -> UnifiedTender:
        raise KeyError(external_id)

    def list_documents(
        self,
        external_id: str,
    ) -> tuple[TenderDocument, ...]:
        self.list_calls += 1
        return self.documents

    def check_health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.descriptor.id,
            status=ProviderHealthStatus.AVAILABLE,
            checked_at="2026-07-12T20:00:00+00:00",
        )


def _provider(
    documents: tuple[TenderDocument, ...],
) -> FakeProvider:
    return FakeProvider(
        descriptor=ProviderDescriptor(
            id="eis",
            display_name="ЕИС",
            source=TenderSource.EIS,
            homepage_url="https://zakupki.gov.ru/",
            capabilities=ProviderCapabilities(
                search=True,
                tender_details=True,
                documents=True,
            ),
            implementation_status="test",
        ),
        documents=documents,
    )


def _tender(
    number: str = "0373100000126000001",
    *,
    external_id: str = "eis-1",
    documents: tuple[TenderDocument, ...] = (),
) -> UnifiedTender:
    return UnifiedTender(
        source=TenderSource.EIS,
        external_id=external_id,
        procurement_number=number,
        title="Монтаж системы видеонаблюдения",
        customer=TenderCustomer(name="Заказчик"),
        source_url=(
            "https://zakupki.gov.ru/epz/order/notice/"
            f"ea20/view/common-info.html?regNumber={number}"
        ),
        documents=documents,
    )


def _document(
    *,
    url: str = "https://files.example.org/tz.pdf",
    name: str = "Техническое задание.pdf",
) -> TenderDocument:
    return TenderDocument(
        id="doc-1",
        name=name,
        url=url,
        mime_type="application/pdf",
    )


def _response(url: str, body: bytes = b"%PDF-test") -> HttpResponse:
    return HttpResponse(
        url=url,
        status_code=200,
        headers={"content-type": "application/pdf"},
        body=body,
    )


def test_service_discovers_and_downloads_provider_documents(
    tmp_path,
) -> None:
    document = _document()
    provider = _provider((document,))
    transport = FakeTransport(
        {document.url: _response(document.url)}
    )
    store = TenderDocumentStore(tmp_path / "documents")
    service = TenderDocumentDownloadService(
        TenderProviderRegistry((provider,)),
        store,
        http_transport=transport,
    )

    result = service.download_for_tender(_tender())

    assert provider.list_calls == 1
    assert transport.calls == [document.url]
    assert result.downloaded_count == 1
    assert result.failed_count == 0
    stored = result.documents[0]
    assert stored.status == DocumentDownloadStatus.DOWNLOADED
    assert stored.available_locally
    assert stored.local_path is not None
    assert stored.local_path.read_bytes() == b"%PDF-test"
    assert stored.checksum_sha256


def test_repeated_download_reuses_local_file_without_http(
    tmp_path,
) -> None:
    document = _document()
    provider = _provider((document,))
    transport = FakeTransport(
        {document.url: _response(document.url)}
    )
    service = TenderDocumentDownloadService(
        TenderProviderRegistry((provider,)),
        TenderDocumentStore(tmp_path / "documents"),
        http_transport=transport,
    )
    tender = _tender()

    first = service.download_for_tender(tender)
    second = service.download_for_tender(tender)

    assert first.downloaded_count == 1
    assert second.reused_count == 1
    assert second.documents[0].status == DocumentDownloadStatus.REUSED
    assert transport.calls == [document.url]


def test_identical_content_is_stored_as_one_unique_blob(tmp_path) -> None:
    first_document = _document(
        url="https://files.example.org/first.pdf",
        name="ТЗ 1.pdf",
    )
    second_document = _document(
        url="https://files.example.org/second.pdf",
        name="ТЗ 2.pdf",
    )
    body = b"%PDF-same-content"
    transport = FakeTransport(
        {
            first_document.url: _response(first_document.url, body),
            second_document.url: _response(second_document.url, body),
        }
    )
    provider = _provider((first_document,))
    store = TenderDocumentStore(tmp_path / "documents")
    service = TenderDocumentDownloadService(
        TenderProviderRegistry((provider,)),
        store,
        http_transport=transport,
    )

    first = service.download_for_tender(
        _tender(documents=(first_document,)),
        refresh_catalog=False,
    )
    second = service.download_for_tender(
        _tender(
            "0373100000126000002",
            external_id="eis-2",
            documents=(second_document,),
        ),
        refresh_catalog=False,
    )

    assert first.documents[0].status == (
        DocumentDownloadStatus.DOWNLOADED
    )
    assert second.documents[0].status == (
        DocumentDownloadStatus.DEDUPLICATED
    )
    assert first.documents[0].local_path != second.documents[0].local_path
    assert store.statistics().unique_blob_count == 1
    assert store.statistics().document_count == 2


def test_html_access_page_is_recorded_as_failure(tmp_path) -> None:
    document = _document()
    provider = _provider((document,))
    transport = FakeTransport(
        {
            document.url: HttpResponse(
                url=document.url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                body=b"<html>captcha</html>",
            )
        }
    )
    store = TenderDocumentStore(tmp_path / "documents")
    service = TenderDocumentDownloadService(
        TenderProviderRegistry((provider,)),
        store,
        http_transport=transport,
    )

    result = service.download_for_tender(_tender())

    assert result.failed_count == 1
    assert not result.documents[0].available_locally
    assert "HTML" in result.documents[0].error_message
    assert store.statistics().failed_count == 1


def test_force_download_bypasses_url_reuse(tmp_path) -> None:
    document = _document()
    provider = _provider((document,))
    transport = FakeTransport(
        {document.url: _response(document.url)}
    )
    service = TenderDocumentDownloadService(
        TenderProviderRegistry((provider,)),
        TenderDocumentStore(tmp_path / "documents"),
        http_transport=transport,
    )
    tender = _tender()

    service.download_for_tender(tender)
    forced = service.download_for_tender(tender, force=True)

    assert len(transport.calls) == 2
    assert forced.documents[0].status in {
        DocumentDownloadStatus.DOWNLOADED,
        DocumentDownloadStatus.DEDUPLICATED,
    }
