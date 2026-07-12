"""SQLite persistence and downgrade-protection tests for C13."""

from __future__ import annotations

import sqlite3

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.schema import COLLECTOR_SCHEMA_VERSION
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.verification import (
    SourceTrustLevel,
    TenderVerificationService,
)
from app.tenders.models import TenderSource, TenderStatus
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.tender_registry import TenderRegistryRepository
from tests.collector_c3_helpers import make_tender


def _save(repository, tender, run_id: str):
    repository.start_run(
        TenderSearchQuery(),
        run_id=run_id,
        provider_ids=(tender.source.value,),
    )
    deduplicated = TenderDeduplicator().deduplicate((tender,))
    verifier = TenderVerificationService(
        history_loader=repository.get_verification_history
    )
    verification = verifier.verify(
        deduplicated,
        observed_at=f"2026-07-12T{10 + int(run_id[-1])}:00:00+00:00",
    )
    summary = repository.save_batch(
        run_id,
        verification.deduplication,
        verification=verification,
    )
    return verification, summary


def test_current_schema_contains_review_and_freshness_tables(tmp_path) -> None:
    path = tmp_path / "tender_registry.sqlite3"
    repository = CollectorStateRepository(path)
    repository.initialize()
    repository.initialize()

    with sqlite3.connect(path) as connection:
        version = int(
            connection.execute(
                """
                SELECT value FROM tender_registry_meta
                WHERE key='collector_schema_version'
                """
            ).fetchone()[0]
        )
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert version == COLLECTOR_SCHEMA_VERSION == 10
    assert {
        "collector_verification_runs",
        "collector_tender_field_values",
        "collector_tender_field_provenance",
        "collector_tender_field_conflicts",
        "collector_tender_verification_state",
        "collector_tender_field_manual_selections",
        "collector_tender_field_resolution_history",
        "collector_tender_freshness_state",
    } <= tables


def test_provenance_conflict_and_state_are_persisted(tmp_path) -> None:
    repository = CollectorStateRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    repository.start_run(TenderSearchQuery(), run_id="run-1")
    eis = make_tender(
        source=TenderSource.EIS,
        external_id="eis-1",
        amount="1500000.00",
    )
    aggregator = make_tender(
        source=TenderSource.CUSTOM,
        external_id="agg-1",
        amount="1900000.00",
        raw_metadata={"aggregator": True},
    )
    deduplicated = TenderDeduplicator().deduplicate(
        (eis, aggregator)
    )
    verification = TenderVerificationService().verify(
        deduplicated,
        observed_at="2026-07-12T12:00:00+00:00",
    )

    summary = repository.save_batch(
        "run-1",
        verification.deduplication,
        verification=verification,
    )
    registry_key = verification.deduplication.items[0].canonical_key
    state = repository.get_verification_state(registry_key)
    provenance = repository.list_field_provenance(
        registry_key,
        field_name="price",
    )
    conflicts = repository.list_field_conflicts(registry_key)

    assert summary.verification_run_id
    assert summary.verified_field_count > 0
    assert summary.conflict_count >= 1
    assert state is not None
    assert state.conflict_count >= 1
    assert len(provenance) == 2
    assert any(item.source_id == "eis" for item in provenance)
    assert any(item.field_name == "price" for item in conflicts)


def test_previous_official_value_is_not_downgraded_by_aggregator(
    tmp_path,
) -> None:
    repository = CollectorStateRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    official = make_tender(
        source=TenderSource.EIS,
        external_id="official-1",
        amount="1500000.00",
        raw_metadata={
            "application_security": "0",
            "contract_security": "75000",
            "documentation_url": "https://example.org/official-docs",
        },
    )
    first, _ = _save(repository, official, "run-1")
    key = first.deduplication.items[0].canonical_key

    aggregator = make_tender(
        source=TenderSource.CUSTOM,
        external_id="aggregator-later",
        amount="2400000.00",
        deadline_day=25,
        status=TenderStatus.CANCELLED,
        raw_metadata={
            "aggregator": True,
            "application_security": "0",
            "contract_security": "120000",
            "documentation_url": "https://aggregator.example/docs",
        },
    )
    second, _ = _save(repository, aggregator, "run-2")
    selected_tender = second.deduplication.items[0].tender
    history = repository.get_verification_history(
        second.deduplication.items[0]
    )

    assert str(selected_tender.price.amount) == "1500000.00"
    assert selected_tender.application_deadline == official.application_deadline
    assert selected_tender.status == TenderStatus.ACCEPTING_APPLICATIONS
    assert selected_tender.raw_metadata["contract_security"] == "75000"
    record = TenderRegistryRepository(repository.path).get_record(key)

    assert record is not None
    assert str(record.price_amount) == "1500000.00"
    assert history is not None
    assert history.registry_key == key
    assert history.selected_candidates["price"].trust_level == (
        SourceTrustLevel.EIS
    )
    assert history.selected_candidates[
        "application_deadline"
    ].trust_level == SourceTrustLevel.EIS
    assert history.selected_candidates["status"].trust_level == (
        SourceTrustLevel.EIS
    )
