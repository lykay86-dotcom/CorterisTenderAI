"""Read-model tests for the C14 verification review service."""

from __future__ import annotations

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.verification import TenderVerificationService
from app.tenders.collector.verification_review import (
    TenderVerificationReviewService,
)
from app.tenders.models import TenderSource
from app.tenders.provider_base import TenderSearchQuery
from tests.collector_c3_helpers import make_tender


def test_review_groups_sources_by_field(tmp_path) -> None:
    repository = CollectorStateRepository(tmp_path / "tender_registry.sqlite3")
    repository.start_run(TenderSearchQuery(), run_id="review-run")
    eis = make_tender(
        source=TenderSource.EIS,
        external_id="review-eis",
        amount="1000000.00",
    )
    other = make_tender(
        source=TenderSource.CUSTOM,
        external_id="review-other",
        amount="1100000.00",
        raw_metadata={"aggregator": True},
    )
    deduplicated = TenderDeduplicator().deduplicate((eis, other))
    verification = TenderVerificationService().verify(deduplicated)
    repository.save_batch(
        "review-run",
        verification.deduplication,
        verification=verification,
    )
    key = verification.deduplication.items[0].canonical_key

    review = TenderVerificationReviewService(repository).load(key)

    price = next(item for item in review.fields if item.field_name == "price")
    assert price.label == "НМЦК / цена"
    assert len(price.candidates) == 2
    assert price.selected_candidate is not None
    assert price.selected_candidate.source_id == "eis"
    assert review.conflicts
