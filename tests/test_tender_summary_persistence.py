from __future__ import annotations

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.tender_summary import DeterministicTenderSummaryGenerator
from tests.collector_c3_helpers import make_tender


def test_summary_is_persisted_in_registry_database(tmp_path) -> None:
    repository = CollectorStateRepository(tmp_path / "tender_registry.sqlite3")
    normalized = TenderNormalizer().normalize(make_tender())
    run_id = repository.start_run(TenderSearchQuery())
    repository.save_batch(run_id, TenderDeduplicator().deduplicate((normalized,)))
    summary = DeterministicTenderSummaryGenerator().generate(
        normalized.canonical_key,
        normalized.tender,
    )

    repository.save_tender_summary(summary)
    payload = repository.get_latest_tender_summary_payload(
        normalized.canonical_key
    )

    assert payload is not None
    assert payload["registry_key"] == normalized.canonical_key
    assert payload["source"] == "deterministic"
    assert payload["facts"]


def test_empty_registry_key_does_not_query_summary_storage(tmp_path) -> None:
    repository = CollectorStateRepository(tmp_path / "tender_registry.sqlite3")

    assert repository.get_latest_tender_summary_payload("  ") is None


def test_summary_history_is_available_for_reuse(tmp_path) -> None:
    repository = CollectorStateRepository(tmp_path / "tender_registry.sqlite3")
    normalized = TenderNormalizer().normalize(make_tender())
    run_id = repository.start_run(TenderSearchQuery())
    repository.save_batch(run_id, TenderDeduplicator().deduplicate((normalized,)))
    generator = DeterministicTenderSummaryGenerator()
    first = generator.generate(normalized.canonical_key, normalized.tender)
    second = generator.generate(normalized.canonical_key, normalized.tender)

    repository.save_tender_summary(first)
    repository.save_tender_summary(second)

    assert len(repository.list_tender_summary_payloads(normalized.canonical_key)) == 2
