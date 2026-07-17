from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from app.tenders.collector.normalizer import (
    TENDER_NORMALIZATION_CONTRACT_VERSION,
    TenderNormalizer,
)
from app.tenders.collector.participation_score import (
    CorterisParticipationRanker,
    ParticipationScoringContext,
)
from app.tenders.models import TenderSource
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.provider_registry import TenderProviderRegistry
from app.tenders.providers.eis import EisHtmlParser
from app.tenders.providers.mos_supplier_parser import MosSupplierApiParser
from app.tenders.search_engine import TenderSearchEngine
from tests.tender_search_helpers import FakeProvider, descriptor, tender


FIXTURES = Path(__file__).parent / "fixtures"


def test_eis_and_moscow_provider_fixtures_share_contract_version() -> None:
    eis_html = (FIXTURES / "eis_search_results.html").read_text(encoding="utf-8")
    eis = EisHtmlParser(base_url="https://zakupki.gov.ru/").parse_search(eis_html).items[0]
    mos_payload = json.loads(
        (FIXTURES / "mos_supplier_search_documented_contract.json").read_text(encoding="utf-8")
    )
    mos = MosSupplierApiParser().parse_search(mos_payload).items[0]

    results = tuple(TenderNormalizer().normalize(item) for item in (eis, mos))

    assert {item.contract_version for item in results} == {TENDER_NORMALIZATION_CONTRACT_VERSION}
    assert {item.tender.source for item in results} == {
        TenderSource.EIS,
        TenderSource.MOS_SUPPLIER,
    }
    assert all(
        value is None or value.utcoffset() is not None
        for item in results
        for value in (item.tender.published_at, item.tender.application_deadline)
    )


def test_legacy_provider_engine_routes_results_through_canonical_boundary() -> None:
    source = tender(
        source=TenderSource.EIS,
        external_id=" 0007 ",
        procurement_number=" 001122334455 ",
        title="  Tender\x00  ",
        tags=("beta", "alpha", "alpha"),
    )
    provider = FakeProvider(
        descriptor=descriptor("eis", TenderSource.EIS, priority=10),
        items=(source,),
    )

    result = TenderSearchEngine(TenderProviderRegistry((provider,))).search(
        TenderSearchQuery(), parallel=False
    )

    assert len(result.items) == 1
    normalized = result.items[0]
    assert normalized.external_id == "0007"
    assert normalized.procurement_number == "001122334455"
    assert normalized.title == "Tender"
    assert normalized.tags == ("alpha", "beta")
    assert (
        normalized.raw_metadata["normalization_contract_version"]
        == TENDER_NORMALIZATION_CONTRACT_VERSION
    )


def test_normalization_preserves_rm107_score_and_recommendation_for_same_facts() -> None:
    source = tender(
        source=TenderSource.EIS,
        external_id="score-1",
        procurement_number="00112233445566778899",
        title="Поставка и монтаж системы видеонаблюдения",
        description="IP-камеры и пусконаладочные работы",
        amount="1500000",
        tags=("монтаж",),
    )
    context = ParticipationScoringContext(now=datetime(2026, 7, 17, tzinfo=timezone.utc))
    ranker = CorterisParticipationRanker()

    before = ranker.score(source, context)
    after = ranker.score(TenderNormalizer().normalize(source).tender, context)

    assert after.total_score == before.total_score
    assert after.recommendation is before.recommendation
    assert after.hard_excluded is before.hard_excluded


def test_commercial_and_manual_readiness_is_not_changed_by_normalization() -> None:
    source = Path("app/tenders/providers/commercial_adapter.py").read_text(encoding="utf-8")
    manual = Path("app/tenders/collector/manual_adapter.py").read_text(encoding="utf-8")

    assert "commercial_access_pending" in source
    assert "raise ProviderNotConfiguredError" in source
    assert "connection_test_required" in manual
    assert "raise ManualAdapterLiveOperationError" in manual
