from app.tenders.tender_summary import DeterministicTenderSummaryGenerator, SafeTenderSummaryEnhancer, TenderSummarySource
from tests.collector_c3_helpers import make_tender


def test_offline_summary_uses_only_tender_card_facts():
    tender = make_tender()
    result = DeterministicTenderSummaryGenerator().generate("key", tender)
    assert result.source == TenderSummarySource.DETERMINISTIC
    assert result.headline == tender.title
    assert "Tender documentation" in result.missing_information
    assert all(item.confidence == 0.0 for item in result.facts)
    assert all(item.provenance == "unverified:tender_card" for item in result.facts)


def test_offline_summary_is_reproducible_without_verified_timestamp():
    tender = make_tender()
    generator = DeterministicTenderSummaryGenerator()

    assert generator.generate("key", tender).to_payload() == generator.generate(
        "key", tender
    ).to_payload()


def test_ai_enhancement_cannot_change_deterministic_facts():
    result = DeterministicTenderSummaryGenerator().generate("key", make_tender())
    enhanced = SafeTenderSummaryEnhancer().enhance(result, "Краткое резюме")
    assert enhanced.source == TenderSummarySource.AI_ENHANCED
    assert enhanced.facts == result.facts
    assert enhanced.risks == result.risks
    assert enhanced.recommendation == result.recommendation
    assert enhanced.missing_information == result.missing_information
