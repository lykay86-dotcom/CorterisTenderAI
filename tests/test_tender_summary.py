from app.tenders.tender_summary import DeterministicTenderSummaryGenerator, TenderSummarySource
from tests.collector_c3_helpers import make_tender


def test_offline_summary_uses_only_tender_card_facts():
    tender = make_tender()
    result = DeterministicTenderSummaryGenerator().generate("key", tender)
    assert result.source == TenderSummarySource.DETERMINISTIC
    assert result.headline == tender.title
    assert "Документация закупки" in result.missing_information
