from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from app.tenders.collector.company_capability import CompanyCapabilityProfile
from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.participation_score import (
    CorterisParticipationRanker,
    ParticipationRecommendation,
    ParticipationScoringContext,
)
from app.tenders.collector.stop_factor import (
    StopFactorEngine,
    StopFactorKind,
    StopFactorStatus,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.requirement_analysis import (
    TenderAnalysisSource,
    TenderRequirementsAnalyzer,
)
from tests.collector_c3_helpers import make_tender


NOW = datetime(2026, 7, 12, tzinfo=timezone.utc)


def _profile(*, sro: bool = False) -> CompanyCapabilityProfile:
    return CompanyCapabilityProfile(
        company_name="КОРТЕРИС",
        business_directions=("видеонаблюдение",),
        self_install_regions=("Москва",),
        licenses=("МЧС",),
        sro_memberships=("СРО",) if sro else (),
        confirmed_experience=("Контракт видеонаблюдения №1",),
        installation_crew_count=2,
        max_project_amount="50000000",
        working_capital="10000000",
        equipment=("камеры",),
        suppliers=("поставщик",),
        confirmed_at="2026-07-12T09:00:00+00:00",
        confirmed_by="user",
    )


def _analysis(text: str):
    return TenderRequirementsAnalyzer().analyze(
        "tender:1",
        (
            TenderAnalysisSource(
                document_key="requirements",
                source_name="Требования.pdf",
                text=text,
            ),
        ),
    )


def test_expired_deadline_is_blocked_with_complete_evidence() -> None:
    tender = replace(
        make_tender(title="Монтаж видеонаблюдения"),
        application_deadline=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    assessment = StopFactorEngine(_profile()).evaluate(
        "tender:1", tender, analysis=_analysis("Извещение."), now=NOW
    )

    assert assessment.status == StopFactorStatus.BLOCKED_BY_REQUIREMENT
    factor = next(
        item for item in assessment.factors if item.kind == StopFactorKind.DEADLINE_EXPIRED
    )
    assert factor.evidence.document
    assert factor.evidence.page
    assert factor.evidence.section
    assert factor.evidence.quote
    assert factor.evidence.remediation
    assert factor.evidence.confidence == 1.0


def test_naive_deadline_is_data_insufficient_instead_of_localized() -> None:
    tender = replace(
        make_tender(title="Монтаж видеонаблюдения"),
        application_deadline=datetime(2026, 7, 11),
    )

    assessment = StopFactorEngine(_profile()).evaluate(
        "tender:1", tender, analysis=_analysis("Извещение."), now=NOW
    )

    assert assessment.status == StopFactorStatus.DATA_INSUFFICIENT
    factor = next(
        item
        for item in assessment.factors
        if item.kind == StopFactorKind.DEADLINE_TIMEZONE_UNKNOWN
    )
    assert factor.evidence.quote == "2026-07-11T00:00:00"


def test_naive_evaluation_time_is_rejected() -> None:
    tender = make_tender(title="Монтаж видеонаблюдения", deadline_day=30)

    try:
        StopFactorEngine(_profile()).evaluate(
            "tender:1",
            tender,
            analysis=_analysis("Извещение."),
            now=datetime(2026, 7, 12),
        )
    except ValueError as error:
        assert "timezone-aware" in str(error)
    else:
        raise AssertionError("naive evaluation time must be rejected")


def test_missing_mandatory_sro_blocks_but_confirmed_sro_removes_block() -> None:
    analysis = _analysis(
        "Участник должен иметь обязательное членство в СРО и предоставить выписку из реестра СРО."
    )
    tender = make_tender(title="Монтаж видеонаблюдения", deadline_day=30)

    missing = StopFactorEngine(_profile(sro=False)).evaluate(
        "tender:1", tender, analysis=analysis, now=NOW
    )
    confirmed = StopFactorEngine(_profile(sro=True)).evaluate(
        "tender:1", tender, analysis=analysis, now=NOW
    )

    assert missing.status == StopFactorStatus.BLOCKED_BY_REQUIREMENT
    assert any(item.kind == StopFactorKind.REQUIRED_SRO_MISSING for item in missing.factors)
    assert not any(item.kind == StopFactorKind.REQUIRED_SRO_MISSING for item in confirmed.factors)


def test_high_score_cannot_override_structured_block() -> None:
    tender = make_tender(
        title="Поставка и монтаж системы видеонаблюдения Trassir и СКУД",
        deadline_day=30,
    )
    assessment = StopFactorEngine(_profile()).evaluate(
        "tender:1",
        tender,
        analysis=_analysis("Работы связаны с государственной тайной."),
        now=NOW,
    )
    score = CorterisParticipationRanker().score(
        tender,
        ParticipationScoringContext(
            now=NOW,
            stop_factor_assessment=assessment,
        ),
    )

    assert score.recommendation == ParticipationRecommendation.NOT_RECOMMENDED
    assert not score.accepted_for_registry
    assert score.stop_factor_assessment == assessment


def test_security_above_confirmed_limit_is_blocked() -> None:
    profile = replace(_profile(), max_contract_security="500000")
    tender = make_tender(
        title="Монтаж видеонаблюдения",
        amount="10000000",
        deadline_day=30,
    )
    analysis = _analysis("Обеспечение исполнения контракта составляет 10%.")

    assessment = StopFactorEngine(profile).evaluate("tender:1", tender, analysis=analysis, now=NOW)

    assert assessment.status == StopFactorStatus.BLOCKED_BY_REQUIREMENT
    factor = next(
        item
        for item in assessment.factors
        if item.kind == StopFactorKind.SECURITY_CAPACITY_EXCEEDED
    )
    assert "1000000.00" in factor.description
    assert "500000" in factor.description


def test_stop_factor_assessment_is_stored_separately(tmp_path) -> None:
    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
    tender = make_tender(title="Монтаж видеонаблюдения", deadline_day=30)
    normalized = TenderNormalizer().normalize(tender)
    run_id = repository.start_run(TenderSearchQuery())
    assessment = StopFactorEngine(_profile()).evaluate(
        normalized.canonical_key,
        tender,
        analysis=_analysis("Работы связаны с государственной тайной."),
        now=NOW,
    )
    score = CorterisParticipationRanker().score(
        tender,
        ParticipationScoringContext(now=NOW, stop_factor_assessment=assessment),
    )

    repository.save_batch(
        run_id,
        TenderDeduplicator().deduplicate((normalized,)),
        rankings={normalized.canonical_key: score},
    )

    assert repository.get_latest_stop_factor_assessment(normalized.canonical_key) == assessment
    with repository._connect() as connection:
        stored = connection.execute(
            "SELECT document_name, page_reference, quote_fragment, remediation "
            "FROM collector_stop_factors WHERE registry_key = ?",
            (normalized.canonical_key,),
        ).fetchall()
    assert stored
    assert all(row["document_name"] and row["page_reference"] for row in stored)
    assert all(row["quote_fragment"] and row["remediation"] for row in stored)
