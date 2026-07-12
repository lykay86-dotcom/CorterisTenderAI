from __future__ import annotations

from decimal import Decimal

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.commercial_estimator import (
    CommercialCostCategory,
    CommercialCostLine,
    CommercialEstimateDraft,
    CommercialEstimateRepository,
    CommercialEstimateStatus,
    CommercialEstimator,
    CommercialEvidence,
)
from app.tenders.provider_base import TenderSearchQuery
from tests.collector_c3_helpers import make_tender


def _line(category: CommercialCostCategory, amount: str) -> CommercialCostLine:
    return CommercialCostLine(
        line_id=category.value,
        category=category,
        description=category.value,
        quantity=Decimal("1"),
        unit_cost=Decimal(amount),
        evidence=CommercialEvidence(
            source="Счёт поставщика",
            document="offer.pdf",
            page="1",
            quote=amount,
            confidence=0.95,
        ),
    )


def test_empty_draft_does_not_invent_prices_or_profit() -> None:
    result = CommercialEstimator().calculate(
        CommercialEstimateDraft(registry_key="tender:1")
    )

    assert result.status == CommercialEstimateStatus.DATA_INSUFFICIENT
    assert result.known_cost == Decimal("0.00")
    assert result.total_cost is None
    assert result.profit is None
    assert result.margin_percent is None
    assert "Предложенная цена/выручка" in result.missing_data
    assert any(item.startswith("Категория:") for item in result.missing_data)


def test_complete_estimate_calculates_exact_profit_margin_and_exposure() -> None:
    lines = (
        _line(CommercialCostCategory.EQUIPMENT, "500000"),
        _line(CommercialCostCategory.INSTALLATION, "200000"),
        _line(CommercialCostCategory.LOGISTICS, "30000"),
        _line(CommercialCostCategory.TRAVEL, "20000"),
        _line(CommercialCostCategory.WARRANTY, "25000"),
        _line(CommercialCostCategory.SUBCONTRACT, "50000"),
        _line(CommercialCostCategory.WORKING_CAPITAL, "15000"),
        _line(CommercialCostCategory.BANK_GUARANTEE, "10000"),
    )
    result = CommercialEstimator().calculate(CommercialEstimateDraft(
        registry_key="tender:1",
        lines=lines,
        proposed_revenue=Decimal("1000000"),
        revenue_evidence=CommercialEvidence("Коммерческое предложение"),
        advance_percent=Decimal("20"),
        payment_delay_days=30,
        payment_evidence=CommercialEvidence("Проект контракта"),
        target_margin_percent=Decimal("20"),
    ))

    assert result.status == CommercialEstimateStatus.COMPLETE
    assert result.total_cost == Decimal("850000.00")
    assert result.profit == Decimal("150000.00")
    assert result.margin_percent == Decimal("15.00")
    assert result.advance_amount == Decimal("200000.00")
    assert result.financing_exposure == Decimal("650000.00")
    assert result.warnings == ("Маржа 15.00% ниже целевой 20%.",)


def test_explicit_confirmed_zero_accounts_for_category() -> None:
    draft = CommercialEstimateDraft(
        registry_key="tender:1",
        confirmed_zero_categories=tuple(CommercialCostCategory),
        confirmed_zero_evidence=tuple(
            (category, CommercialEvidence("Ручное подтверждение нулевой статьи"))
            for category in CommercialCostCategory
        ),
        proposed_revenue="1000",
        revenue_evidence=CommercialEvidence("Ручная цена"),
        advance_percent="100",
        payment_delay_days=0,
        payment_evidence=CommercialEvidence("Предоплата"),
    )

    result = CommercialEstimator().calculate(draft)

    assert result.status == CommercialEstimateStatus.COMPLETE
    assert result.total_cost == Decimal("0.00")
    assert result.profit == Decimal("1000.00")


def test_estimate_and_evidence_lines_are_persisted(tmp_path) -> None:
    database = tmp_path / "registry.sqlite3"
    state = CollectorStateRepository(database)
    tender = make_tender()
    normalized = TenderNormalizer().normalize(tender)
    run_id = state.start_run(TenderSearchQuery())
    state.save_batch(
        run_id,
        TenderDeduplicator().deduplicate((normalized,)),
    )
    repository = CommercialEstimateRepository(database)
    draft = CommercialEstimateDraft(
        registry_key=normalized.canonical_key,
        lines=(_line(CommercialCostCategory.EQUIPMENT, "100"),),
    )
    result = CommercialEstimator().calculate(draft)

    stored = repository.save(draft, result)
    loaded = repository.latest(normalized.canonical_key)

    assert loaded == (draft, stored)
    with repository._connect() as connection:
        row = connection.execute(
            "SELECT evidence_json FROM collector_commercial_cost_lines"
        ).fetchone()
    assert "offer.pdf" in row["evidence_json"]


def test_fingerprint_ignores_technical_line_id() -> None:
    first = _line(CommercialCostCategory.EQUIPMENT, "100")
    second = CommercialCostLine(
        line_id="another-id",
        category=first.category,
        description=first.description,
        quantity=first.quantity,
        unit_cost=first.unit_cost,
        evidence=first.evidence,
    )

    one = CommercialEstimator().calculate(
        CommercialEstimateDraft(registry_key="tender:1", lines=(first,))
    )
    two = CommercialEstimator().calculate(
        CommercialEstimateDraft(registry_key="tender:1", lines=(second,))
    )

    assert one.input_fingerprint == two.input_fingerprint
