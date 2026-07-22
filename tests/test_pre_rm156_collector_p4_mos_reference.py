"""P4 reference-adapter contracts for the Moscow Supplier Portal."""

from __future__ import annotations

import asyncio
from pathlib import Path

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
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import (
    ProviderNotConfiguredError,
    TenderProviderError,
    TenderSearchQuery,
)
from app.tenders.providers.mos_supplier_api import AsyncMosSupplierTenderProvider
from tests.test_collector_mos_supplier_provider import (
    CARD_BODY,
    SEARCH_BODY,
    _client,
    _config,
)


SECRET = "P4_MOS_BEARER_SENTINEL"


def _repository(tmp_path: Path) -> CollectorStateRepository:
    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
    repository.initialize()
    return repository


def test_mos_reference_requires_token_before_page_network(tmp_path: Path) -> None:
    async def scenario() -> None:
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, content=SEARCH_BODY, request=request)

        client, raw = _client(handler)
        provider = AsyncMosSupplierTenderProvider(
            client,
            config=_config(""),
            artifact_store=RawArtifactStore(tmp_path / "artifacts"),
        )

        with pytest.raises(ProviderNotConfiguredError):
            _ = tuple(
                [
                    page
                    async for page in provider.iter_search_pages(
                        TenderSearchQuery(keywords=("СКУД",))
                    )
                ]
            )

        assert calls == 0
        assert not tuple((tmp_path / "artifacts").rglob("*.artifact"))
        await raw.aclose()

    asyncio.run(scenario())


def test_mos_search_does_not_advance_checkpoint_before_page_acceptance(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=SEARCH_BODY, request=request)

        repository = _repository(tmp_path)
        client, raw = _client(handler)
        provider = AsyncMosSupplierTenderProvider(
            client,
            config=_config(),
            checkpoint_repository=repository,
        )
        query = TenderSearchQuery(extra={"incremental": False})

        await provider.search(query)

        assert (
            repository.get_checkpoint(
                "mos_supplier",
                scope_key=provider.checkpoints.scope_key(query),
            )
            is None
        )
        await raw.aclose()

    asyncio.run(scenario())


def test_mos_reference_commits_one_terminal_documented_scope_page(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        repository = _repository(tmp_path)
        query = TenderSearchQuery(page_size=1, extra={"incremental": False})
        run_id = repository.start_run(query, provider_ids=("mos_supplier",))
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            assert request.headers["authorization"] == f"Bearer {SECRET}"
            return httpx.Response(
                200,
                content=SEARCH_BODY,
                headers={"content-type": "application/json; charset=utf-8"},
                request=request,
            )

        client, raw = _client(handler)
        provider = AsyncMosSupplierTenderProvider(
            client,
            config=_config(SECRET),
            checkpoint_repository=repository,
            artifact_store=RawArtifactStore(tmp_path / "artifacts"),
        )
        result = await AsyncProviderSearchEngine(
            (provider,),
            accepted_page_repository=repository,
        ).search(query, run_id=run_id)

        assert result.outcomes[0].status is AsyncProviderSearchStatus.SUCCESS
        assert result.outcomes[0].page_count == 1
        assert result.outcomes[0].artifact_count == 1
        assert calls == 1
        assert result.outcomes[0].result is not None
        assert result.outcomes[0].result.next_page_token == ""
        assert any("серверная пагинация" in item for item in result.outcomes[0].warnings)
        fingerprint = build_query_fingerprint(provider, query)
        checkpoint = repository.get_checkpoint("mos_supplier", scope_key=fingerprint)
        assert checkpoint is not None
        assert checkpoint.accepted_page_count == 1
        assert checkpoint.cursor == ""
        with repository._connect() as connection:
            assert (
                connection.execute(
                    "SELECT COUNT(*) FROM collector_raw_artifact_refs WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
                == 1
            )
        artifact = provider.last_artifacts[0]
        assert artifact.request_url == "https://api.zakupki.mos.ru/api/v2/auction/public/Search"
        assert SECRET.casefold() not in repr(artifact).casefold()
        await raw.aclose()

    asyncio.run(scenario())


def test_mos_reference_card_artifact_is_detail_and_document_evidence(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=CARD_BODY,
                headers={"content-type": "application/json"},
                request=request,
            )

        client, raw = _client(handler)
        provider = AsyncMosSupplierTenderProvider(
            client,
            config=_config(SECRET),
            artifact_store=RawArtifactStore(tmp_path / "artifacts"),
        )
        documents = await provider.list_documents("9294080")

        assert len(documents) == 2
        assert len(provider.last_artifacts) == 1
        assert provider.last_artifacts[0].parse_outcome == "card_documents_accepted"
        assert provider.last_artifacts[0].request_url.endswith("/api/v2/auction/public/Get")
        assert SECRET.casefold() not in repr(provider.last_artifacts[0]).casefold()
        await raw.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("body", "outcome"),
    ((b"{", "rejected_json"), (b'{"result":{"items":[{}]}}', "rejected_structure")),
)
def test_mos_reference_retains_rejected_json_without_public_body(
    tmp_path: Path,
    body: bytes,
    outcome: str,
) -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, request=request)

        client, raw = _client(handler)
        provider = AsyncMosSupplierTenderProvider(
            client,
            config=_config(SECRET),
            artifact_store=RawArtifactStore(tmp_path / "artifacts"),
        )

        with pytest.raises(TenderProviderError) as captured:
            await provider.search(TenderSearchQuery(extra={"incremental": False}))

        assert body.decode(errors="ignore") not in str(captured.value)
        assert provider.last_artifacts[-1].parse_outcome == outcome
        assert SECRET.casefold() not in repr(provider.last_artifacts[-1]).casefold()
        await raw.aclose()

    asyncio.run(scenario())


def test_mos_reference_redacts_remote_api_error_body(tmp_path: Path) -> None:
    async def scenario() -> None:
        body = f'{{"error":"Authorization: Bearer {SECRET}"}}'.encode()

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, request=request)

        client, raw = _client(handler)
        provider = AsyncMosSupplierTenderProvider(
            client,
            config=_config(SECRET),
            artifact_store=RawArtifactStore(tmp_path / "artifacts"),
        )

        with pytest.raises(TenderProviderError) as captured:
            await provider.search(TenderSearchQuery(extra={"incremental": False}))

        assert SECRET not in str(captured.value)
        assert provider.last_artifacts[-1].parse_outcome == "rejected_api"
        await raw.aclose()

    asyncio.run(scenario())


def test_mos_reference_honors_pre_request_cancellation(tmp_path: Path) -> None:
    async def scenario() -> None:
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, content=SEARCH_BODY, request=request)

        client, raw = _client(handler)
        provider = AsyncMosSupplierTenderProvider(
            client,
            config=_config(SECRET),
            artifact_store=RawArtifactStore(tmp_path / "artifacts"),
        )
        token = CollectorCancellationToken()
        token.cancel("cancel before authenticated request")

        with pytest.raises(CollectorCancelledError):
            _ = tuple(
                [
                    page
                    async for page in provider.iter_search_pages(
                        TenderSearchQuery(),
                        cancellation_token=token,
                    )
                ]
            )

        assert calls == 0
        await raw.aclose()

    asyncio.run(scenario())


def test_mos_reference_contract_versions_are_explicit() -> None:
    assert AsyncMosSupplierTenderProvider.contract_version == "mos-supplier-api-v1"
    assert AsyncMosSupplierTenderProvider.parser_version == "mos-supplier-api-1"
