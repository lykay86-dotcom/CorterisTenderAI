from app.tenders.tender_summary import DeterministicTenderSummaryGenerator, SafeTenderSummaryEnhancer, TenderSummarySource
from tests.collector_c3_helpers import make_tender


def test_offline_summary_uses_only_tender_card_facts():
    tender = make_tender()
    result = DeterministicTenderSummaryGenerator().generate("key", tender)
    assert result.source == TenderSummarySource.DETERMINISTIC
    assert result.headline == tender.title
    assert "Документация закупки" in result.missing_information


def test_ai_enhancement_cannot_change_deterministic_facts():
    result = DeterministicTenderSummaryGenerator().generate("key", make_tender())
    enhanced = SafeTenderSummaryEnhancer().enhance(result, "Краткое резюме")
    assert enhanced.source == TenderSummarySource.AI_ENHANCED
    assert enhanced.facts == result.facts
    assert enhanced.risks == result.risks
