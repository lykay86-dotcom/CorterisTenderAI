"""P4 reference-adapter contracts for the public EIS provider."""

from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from app.tenders.collector.artifacts import RawArtifactStore
from app.tenders.collector.async_engine import (
    AsyncProviderSearchEngine,
    AsyncProviderSearchStatus,
)
from app.tenders.collector.async_provider import build_query_fingerprint
from app.tenders.collector.cancellation import (
    CollectorCancellationToken,
    CollectorCancelledError,
)
from app.tenders.collector.checkpoint import CollectorCheckpoint
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.providers.eis import EisAccessBlockedError, EisParseError
from app.tenders.providers.eis_async import AsyncEisTenderProvider
from tests.test_collector_eis_async_provider import (
    DOCUMENTS_HTML,
    NOTICE_44_HTML,
    SEARCH_HTML,
    _client,
)


_TOTAL_TWO = "Всего записей: 2".encode()
_TOTAL_SIXTY = "Всего записей: 60".encode()
SECOND_SEARCH_HTML = SEARCH_HTML.replace(
    b"0373100000126000001",
    b"0373100000126000009",
).replace(_TOTAL_TWO, _TOTAL_SIXTY)
FIRST_SEARCH_HTML = SEARCH_HTML.replace(_TOTAL_TWO, _TOTAL_SIXTY)
CAPTCHA_HTML = (Path(__file__).parent / "fixtures" / "eis" / "captcha.html").read_bytes()
DRIFT_HTML = (
    Path(__file__).parent / "fixtures" / "eis" / "search_structure_changed.html"
).read_bytes()


def _repository(tmp_path: Path) -> CollectorStateRepository:
    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
    repository.initialize()
    return repository


def test_eis_reference_iterates_bounded_pages_and_commits_before_next_request(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        repository = _repository(tmp_path)
        query = TenderSearchQuery(page_size=50, extra={"incremental": False})
        run_id = repository.start_run(query, provider_ids=("eis",))
        page_numbers: list[int] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            page_number = int(parse_qs(request.url.query.decode())["pageNumber"][0])
            page_numbers.append(page_number)
            if page_number == 2:
                checkpoint = repository.get_checkpoint(
                    "eis",
                    scope_key=build_query_fingerprint(provider, query),
                )
                assert checkpoint is not None
                assert checkpoint.cursor == "2"
                assert checkpoint.accepted_page_count == 1
            body = FIRST_SEARCH_HTML if page_number == 1 else SECOND_SEARCH_HTML
            return httpx.Response(
                200,
                content=body,
                headers={"content-type": "text/html; charset=utf-8"},
                request=request,
            )

        client, raw = _client(handler)
        provider = AsyncEisTenderProvider(
            client,
            checkpoint_repository=repository,
            artifact_store=RawArtifactStore(tmp_path / "artifacts"),
        )
        result = await AsyncProviderSearchEngine(
            (provider,),
            accepted_page_repository=repository,
        ).search(query, run_id=run_id)

        assert result.outcomes[0].status is AsyncProviderSearchStatus.SUCCESS
        assert result.outcomes[0].page_count == 2
        assert result.outcomes[0].artifact_count == 2
        assert page_numbers == [1, 2]
        checkpoint = repository.get_checkpoint(
            "eis",
            scope_key=build_query_fingerprint(provider, query),
        )
        assert checkpoint is not None
        assert checkpoint.cursor == ""
        assert checkpoint.accepted_page_count == 2
        assert tuple((tmp_path / "artifacts").rglob("*.artifact"))
        with repository._connect() as connection:
            assert (
                connection.execute(
                    "SELECT COUNT(*) FROM collector_raw_artifact_refs WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
                == 2
            )
        await raw.aclose()

    asyncio.run(scenario())


def test_eis_reference_resumes_from_committed_cursor(tmp_path: Path) -> None:
    async def scenario() -> None:
        requested_pages: list[int] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requested_pages.append(int(parse_qs(request.url.query.decode())["pageNumber"][0]))
            return httpx.Response(200, content=SECOND_SEARCH_HTML, request=request)

        client, raw = _client(handler)
        provider = AsyncEisTenderProvider(
            client,
            artifact_store=RawArtifactStore(tmp_path / "artifacts"),
        )
        query = TenderSearchQuery(page_size=50, extra={"incremental": False})
        fingerprint = build_query_fingerprint(provider, query)
        resume = CollectorCheckpoint(
            provider_id="eis",
            scope_key=fingerprint,
            cursor="2",
            contract_version=provider.contract_version,
            parser_version=provider.parser_version,
            query_fingerprint=fingerprint,
            accepted_page_count=1,
        )

        pages = tuple([page async for page in provider.iter_search_pages(query, resume=resume)])

        assert requested_pages == [2]
        assert len(pages) == 1
        assert pages[0].page_number == 2
        assert pages[0].terminal
        await raw.aclose()

    asyncio.run(scenario())


def test_eis_reference_honors_cancellation_between_pages(tmp_path: Path) -> None:
    async def scenario() -> None:
        requested_pages: list[int] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requested_pages.append(int(parse_qs(request.url.query.decode())["pageNumber"][0]))
            return httpx.Response(200, content=FIRST_SEARCH_HTML, request=request)

        client, raw = _client(handler)
        provider = AsyncEisTenderProvider(
            client,
            artifact_store=RawArtifactStore(tmp_path / "artifacts"),
        )
        token = CollectorCancellationToken()
        pages = provider.iter_search_pages(
            TenderSearchQuery(page_size=50, extra={"incremental": False}),
            cancellation_token=token,
        )

        first = await anext(pages)
        token.cancel("stop after accepted page")
        with pytest.raises(CollectorCancelledError):
            await anext(pages)

        assert first.next_cursor == "2"
        assert requested_pages == [1]
        await raw.aclose()

    asyncio.run(scenario())


def test_eis_reference_captures_search_detail_and_document_artifacts(tmp_path: Path) -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            if "documents.html" in request.url.path:
                body = DOCUMENTS_HTML
            elif "common-info.html" in request.url.path:
                body = NOTICE_44_HTML
            else:
                body = SEARCH_HTML
            return httpx.Response(
                200,
                content=body,
                headers={"content-type": "text/html; charset=utf-8"},
                request=request,
            )

        client, raw = _client(handler)
        provider = AsyncEisTenderProvider(
            client,
            artifact_store=RawArtifactStore(tmp_path / "artifacts"),
        )
        documents = await provider.list_documents("0373100000126000001")

        assert documents
        assert {item.parse_outcome for item in provider.last_artifacts} == {
            "search_accepted",
            "detail_accepted",
            "documents_accepted",
        }
        assert all("?" not in item.request_url for item in provider.last_artifacts)
        assert len(tuple((tmp_path / "artifacts").rglob("*.artifact"))) == 3
        await raw.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("body", "error_type"),
    ((CAPTCHA_HTML, EisAccessBlockedError), (DRIFT_HTML, EisParseError)),
)
def test_eis_reference_fails_closed_and_retains_rejected_evidence(
    tmp_path: Path,
    body: bytes,
    error_type: type[Exception],
) -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, request=request)

        client, raw = _client(handler)
        provider = AsyncEisTenderProvider(
            client,
            artifact_store=RawArtifactStore(tmp_path / "artifacts"),
        )

        with pytest.raises(error_type):
            await provider.search(TenderSearchQuery(extra={"incremental": False}))

        assert len(provider.last_artifacts) == 1
        assert provider.last_artifacts[0].parse_outcome.startswith("rejected_")
        assert "captcha" not in repr(provider.last_artifacts[0]).casefold()
        await raw.aclose()

    asyncio.run(scenario())


def test_eis_reference_contract_versions_are_explicit() -> None:
    assert AsyncEisTenderProvider.contract_version == "eis-public-html-v1"
    assert AsyncEisTenderProvider.parser_version.startswith("eis-search-v")
