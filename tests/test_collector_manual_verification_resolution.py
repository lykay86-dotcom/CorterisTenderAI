"""Manual field resolution and audit-history tests for C14."""

from __future__ import annotations

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.verification import TenderVerificationService
from app.tenders.models import TenderSource
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.tender_registry import TenderRegistryRepository
from tests.collector_c3_helpers import make_tender


def _conflicted_repository(tmp_path):
    repository = CollectorStateRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    repository.start_run(TenderSearchQuery(), run_id="run-c14")
    eis = make_tender(
        source=TenderSource.EIS,
        external_id="eis-c14",
        amount="1500000.00",
    )
    aggregator = make_tender(
        source=TenderSource.CUSTOM,
        external_id="agg-c14",
        amount="1900000.00",
        raw_metadata={"aggregator": True},
    )
    deduplicated = TenderDeduplicator().deduplicate((eis, aggregator))
    verification = TenderVerificationService().verify(
        deduplicated,
        observed_at="2026-07-12T12:00:00+00:00",
    )
    repository.save_batch(
        "run-c14",
        verification.deduplication,
        verification=verification,
    )
    key = verification.deduplication.items[0].canonical_key
    return repository, key


def test_manual_selection_updates_record_and_audit(tmp_path) -> None:
    repository, registry_key = _conflicted_repository(tmp_path)
    candidates = repository.list_field_candidates(
        registry_key,
        field_name="price",
    )
    aggregator = next(
        item for item in candidates if item.source_id == "custom"
    )

    resolution = repository.resolve_field_candidate(
        registry_key,
        "price",
        aggregator.candidate_id,
        note="Коммерческая цена подтверждена менеджером",
        resolved_by="operator",
        resolved_at="2026-07-12T13:00:00+00:00",
    )

    record = TenderRegistryRepository(repository.path).get_record(
        registry_key
    )
    assert record is not None
    assert str(record.price_amount) == "1900000.00"
    current = repository.list_field_candidates(
        registry_key,
        field_name="price",
    )
    selected = next(item for item in current if item.selected)
    assert selected.candidate_id == aggregator.candidate_id
    assert selected.manual_override
    assert resolution.selected_source_id == "custom"
    history = repository.list_field_resolutions(registry_key)
    assert history[0].resolved_by == "operator"
    assert "подтверждена" in history[0].note.casefold()


def test_manual_resolution_hides_effective_unresolved_conflict(
    tmp_path,
) -> None:
    repository = CollectorStateRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    repository.start_run(
        TenderSearchQuery(),
        run_id="run-c14-unresolved",
    )
    first = make_tender(
        source=TenderSource.EIS,
        external_id="eis-c14-first",
        amount="1500000.00",
    )
    second = make_tender(
        source=TenderSource.EIS,
        external_id="eis-c14-second",
        amount="1900000.00",
    )
    deduplicated = TenderDeduplicator().deduplicate(
        (first, second)
    )
    verification = TenderVerificationService().verify(
        deduplicated,
        observed_at="2026-07-12T12:00:00+00:00",
    )
    repository.save_batch(
        "run-c14-unresolved",
        verification.deduplication,
        verification=verification,
    )
    registry_key = (
        verification.deduplication.items[0].canonical_key
    )
    conflict_before = repository.list_field_conflicts(
        registry_key,
        unresolved_only=True,
    )
    candidates = repository.list_field_candidates(
        registry_key,
        field_name="price",
    )
    selected = next(
        item
        for item in candidates
        if item.source_url.endswith("/eis-c14-first")
    )

    repository.resolve_field_candidate(
        registry_key,
        "price",
        selected.candidate_id,
    )

    assert conflict_before
    assert not repository.list_field_conflicts(
        registry_key,
        unresolved_only=True,
    )
    state = repository.get_verification_state(registry_key)
    assert state is not None
    assert state.unresolved_conflict_count == 0


def test_clear_manual_resolution_restores_automatic_priority(tmp_path) -> None:
    repository, registry_key = _conflicted_repository(tmp_path)
    candidates = repository.list_field_candidates(
        registry_key,
        field_name="price",
    )
    aggregator = next(
        item for item in candidates if item.source_id == "custom"
    )
    repository.resolve_field_candidate(
        registry_key,
        "price",
        aggregator.candidate_id,
    )

    cleared = repository.clear_manual_field_resolution(
        registry_key,
        "price",
        resolved_by="operator",
    )

    assert cleared is not None
    current = repository.list_field_candidates(
        registry_key,
        field_name="price",
    )
    selected = next(item for item in current if item.selected)
    assert selected.source_id == "eis"
    assert not selected.manual_override
    record = TenderRegistryRepository(repository.path).get_record(
        registry_key
    )
    assert record is not None
    assert str(record.price_amount) == "1500000.00"
