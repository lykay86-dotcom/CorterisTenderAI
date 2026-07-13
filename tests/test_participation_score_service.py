"""Tests for rescoring a registry tender with local evidence."""

from __future__ import annotations

from dataclasses import replace

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.participation_score_service import (
    CorterisParticipationScoreService,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.tender_registry import TenderRegistryRepository
from tests.collector_c3_helpers import make_tender


class TextResult:
    document_key = "doc-1"
    available_locally = True
    source_path = None


class TextService:
    def list_results(self, registry_key):
        assert registry_key
        return (TextResult(),)

    def read_text(self, result):
        del result
        return "Монтаж СКУД и автоматического шлагбаума"


class AnalysisService:
    def latest(self, registry_key):
        assert registry_key
        return None


def test_service_uses_local_text_and_persists(tmp_path) -> None:
    path = tmp_path / "tender_registry.sqlite3"
    state_repository = CollectorStateRepository(path)
    tender = replace(
        make_tender(
            title="Оказание услуг",
            description="По техническому заданию",
        ),
        tags=(),
        classification_codes=(),
    )
    normalized = TenderNormalizer().normalize(tender)
    run_id = state_repository.start_run(TenderSearchQuery())
    state_repository.save_batch(
        run_id,
        TenderDeduplicator().deduplicate((normalized,)),
    )
    service = CorterisParticipationScoreService(
        TenderRegistryRepository(path),
        state_repository,
        text_service=TextService(),
        requirement_analysis_service=AnalysisService(),
    )

    score = service.evaluate(normalized.canonical_key)

    assert any(item.casefold() == "скуд" for item in score.matched_keywords)
    assert service.latest(normalized.canonical_key) == score
