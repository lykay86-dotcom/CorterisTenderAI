"""Tests for provider failures and timeout isolation."""

from __future__ import annotations

from app.tenders.models import TenderSource
from app.tenders.provider_base import (
    ProviderNotConfiguredError,
    TenderProviderError,
    TenderSearchQuery,
)
from app.tenders.provider_registry import TenderProviderRegistry
from app.tenders.search_engine import (
    ProviderSearchStatus,
    TenderSearchEngine,
)
from tests.tender_search_helpers import (
    FakeProvider,
    descriptor,
    tender,
)


def test_one_provider_failure_does_not_discard_other_results() -> None:
    successful = FakeProvider(
        descriptor=descriptor(
            "eis",
            TenderSource.EIS,
            priority=10,
        ),
        items=(
            tender(
                source=TenderSource.EIS,
                external_id="1",
                procurement_number="001",
                title="Рабочий результат",
            ),
        ),
    )
    failed = FakeProvider(
        descriptor=descriptor(
            "rts_tender",
            TenderSource.RTS_TENDER,
            priority=20,
        ),
        error=TenderProviderError("network failure"),
    )

    result = TenderSearchEngine(
        TenderProviderRegistry((successful, failed))
    ).search(TenderSearchQuery())

    assert len(result.items) == 1
    assert result.has_partial_failures
    assert result.failed_provider_ids == ("rts_tender",)
    assert result.outcomes[1].status == (
        ProviderSearchStatus.FAILED
    )


def test_not_configured_provider_has_explicit_status() -> None:
    provider = FakeProvider(
        descriptor=descriptor(
            "eis",
            TenderSource.EIS,
            priority=10,
        ),
        error=ProviderNotConfiguredError("credentials missing"),
    )

    result = TenderSearchEngine(
        TenderProviderRegistry((provider,))
    ).search(TenderSearchQuery())

    assert result.outcomes[0].status == (
        ProviderSearchStatus.NOT_CONFIGURED
    )
    assert "credentials missing" in (
        result.outcomes[0].error_message
    )


def test_slow_provider_is_marked_timed_out() -> None:
    slow = FakeProvider(
        descriptor=descriptor(
            "eis",
            TenderSource.EIS,
            priority=10,
        ),
        delay_seconds=0.15,
    )
    engine = TenderSearchEngine(
        TenderProviderRegistry((slow,)),
        timeout_seconds=0.03,
    )

    result = engine.search(
        TenderSearchQuery(),
        parallel=True,
    )

    assert result.outcomes[0].status == (
        ProviderSearchStatus.TIMED_OUT
    )
    assert result.completed_provider_count == 0


def test_parallel_timeout_marks_only_pending_provider() -> None:
    fast = FakeProvider(
        descriptor=descriptor(
            "eis",
            TenderSource.EIS,
            priority=10,
        ),
        items=(
            tender(
                source=TenderSource.EIS,
                external_id="1",
                procurement_number="001",
                title="Быстрый",
            ),
        ),
    )
    slow = FakeProvider(
        descriptor=descriptor(
            "rts_tender",
            TenderSource.RTS_TENDER,
            priority=20,
        ),
        delay_seconds=0.2,
    )
    engine = TenderSearchEngine(
        TenderProviderRegistry((fast, slow)),
        max_workers=2,
        timeout_seconds=0.03,
    )

    result = engine.search(
        TenderSearchQuery(),
        parallel=True,
    )

    assert result.outcomes[0].status == (
        ProviderSearchStatus.SUCCESS
    )
    assert result.outcomes[1].status == (
        ProviderSearchStatus.TIMED_OUT
    )
    assert len(result.items) == 1
