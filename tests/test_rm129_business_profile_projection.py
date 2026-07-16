"""RM-129 pure projection and deterministic score/stop semantics."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.tenders.business_profile import BusinessCapabilityProjection
from app.tenders.collector.company_capability import (
    CompanyCapabilityProfile,
    CompanyCapabilityProfileRepository,
)
from app.tenders.collector.participation_score import (
    CorterisCompanyProfile,
    CorterisParticipationRanker,
    ParticipationRecommendation,
    ParticipationScoringContext,
)
from app.tenders.collector.stop_factor import (
    StopFactorEngine,
    StopFactorKind,
    StopFactorStatus,
)
from app.tenders.collector.verification import TenderVerificationStatus
from app.tenders.commercial_estimator import CommercialEstimateStatus
from app.tenders.models import TenderMoney
from app.tenders.participation_decision_service import ParticipationDecisionService
from app.tenders.requirement_analysis import (
    TenderAnalysisSource,
    TenderRequirementsAnalyzer,
)
from tests.collector_c3_helpers import make_tender


NOW = datetime(2026, 7, 12, tzinfo=timezone.utc)


def _draft(**changes: object) -> CompanyCapabilityProfile:
    values: dict[str, object] = {
        "company_name": "ООО КОРТЕРИС",
        "business_directions": ("видеонаблюдение", "СКУД"),
        "self_install_regions": ("Москва",),
        "licenses": ("МЧС",),
        "installation_crew_count": 2,
        "confirmed_experience": ("Контракт №1",),
        "max_project_amount": Decimal("30000000"),
        "working_capital": Decimal("5000000"),
        "max_contract_security": Decimal("500000"),
        "equipment": ("IP-камера",),
        "brands": ("Trassir",),
        "suppliers": ("Поставщик 1",),
        "minimum_margin_percent": Decimal("20"),
        "base_currency": "RUB",
    }
    values.update(changes)
    return CompanyCapabilityProfile(**values)


def _confirmed(**changes: object) -> CompanyCapabilityProfile:
    return _draft(**changes).confirm(confirmed_by="Директор", confirmed_at=NOW)


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


def _score(profile: CompanyCapabilityProfile):
    projection = BusinessCapabilityProjection.from_capability(profile)
    return CorterisParticipationRanker(
        CorterisCompanyProfile.from_business_profile(projection)
    ).score(
        make_tender(title="Монтаж видеонаблюдения Trassir", amount="1500000"),
        ParticipationScoringContext(now=NOW),
    )


def _equivalent_v1_v2_profiles(
    tmp_path: Path,
    **changes: object,
) -> tuple[CompanyCapabilityProfile, CompanyCapabilityProfile]:
    current = _confirmed(**changes)
    legacy = current.to_dict()
    for key in (
        "base_currency",
        "confirmation_version",
        "confirmation_fingerprint",
        "confirmation_source",
    ):
        legacy.pop(key)
    path = tmp_path / "company_capability_profile.json"
    path.write_text(
        json.dumps({"schema_version": 1, "profile": legacy}, ensure_ascii=False),
        encoding="utf-8",
    )
    migrated = CompanyCapabilityProfileRepository(path).load_result().profile
    return migrated, current


def test_projection_is_frozen_pure_snapshot_and_raw_properties_delegate() -> None:
    profile = _confirmed()
    projection = BusinessCapabilityProjection.from_capability(profile)

    assert projection.is_confirmed
    assert projection.is_configured == profile.is_configured
    assert projection.missing_sections == profile.missing_sections
    assert projection.business_directions == ("видеонаблюдение", "СКУД")
    assert projection.base_currency == "RUB"
    assert projection.max_project_amount == Decimal("30000000")
    with pytest.raises(FrozenInstanceError):
        projection.company_name = "Изменение"  # type: ignore[misc]


def test_unconfirmed_projection_exposes_no_decision_capabilities() -> None:
    projection = BusinessCapabilityProjection.from_capability(
        _draft(
            sro_memberships=("СРО",),
            confirmed_experience=("Контракт",),
            max_bid_security=Decimal("999999999"),
        )
    )

    assert not projection.is_confirmed
    assert not projection.is_configured
    assert projection.business_directions == ()
    assert projection.licenses == ()
    assert projection.sro_memberships == ()
    assert projection.confirmed_experience == ()
    assert projection.max_project_amount is None
    assert projection.max_bid_security is None
    assert projection.equipment == ()


def test_partial_confirmed_profile_preserves_existing_configured_predicate() -> None:
    profile = CompanyCapabilityProfile(
        company_name="ООО КОРТЕРИС",
        business_directions=("видеонаблюдение",),
        base_currency="RUB",
    ).confirm(confirmed_by="Директор", confirmed_at=NOW)
    projection = BusinessCapabilityProjection.from_capability(profile)

    assert projection.is_confirmed
    assert projection.is_configured
    assert projection.missing_sections == (
        "регионы выполнения работ",
        "лицензии и СРО",
        "подтверждённый опыт",
        "монтажные бригады",
        "финансовые возможности",
        "оборудование и бренды",
        "поставщики",
    )


def test_from_capability_remains_compatibility_wrapper() -> None:
    profile = _confirmed()
    projection = BusinessCapabilityProjection.from_capability(profile)

    assert CorterisCompanyProfile.from_capability(profile) == (
        CorterisCompanyProfile.from_business_profile(projection)
    )


def test_complete_profile_preserves_exact_golden_scoring_semantics() -> None:
    score = _score(_confirmed())

    assert score.total_score == 66
    assert score.recommendation is ParticipationRecommendation.MANUAL_REVIEW
    assert tuple((item.key, item.score, item.maximum) for item in score.components) == (
        ("direction", 23, 30),
        ("region", 10, 10),
        ("price", 10, 10),
        ("equipment", 3, 15),
        ("experience", 7, 10),
        ("licenses", 7, 10),
        ("financial", 6, 10),
        ("preparation", 4, 5),
        ("risks", -4, 0),
    )
    assert tuple(item.explanation for item in score.components) == (
        "Базовая релевантность 45/100; направления: video_surveillance. "
        "Подтверждённые направления: видеонаблюдение.",
        "Приоритетный регион: Москва.",
        "НМЦК 1500000 входит в основной рабочий диапазон.",
        "Найдены оборудование/бренды: Trassir",
        "Требования к опыту ещё не извлечены из документации.",
        "Документация ещё не проверена на лицензии и допуски.",
        "Финансовые условия требуют проверки проекта договора.",
        "До окончания подачи около 8 дней.",
        "Риски: неполная документация; штраф 4 балл.",
    )


def test_equivalent_v1_v2_profiles_have_identical_score_semantics(tmp_path: Path) -> None:
    migrated, current = _equivalent_v1_v2_profiles(tmp_path)
    migrated_score = _score(migrated)
    current_score = _score(current)

    assert migrated_score.total_score == current_score.total_score
    assert migrated_score.recommendation is current_score.recommendation
    assert migrated_score.recommendation_text == current_score.recommendation_text
    assert migrated_score.components == current_score.components
    assert migrated_score.positive_factors == current_score.positive_factors
    assert migrated_score.negative_factors == current_score.negative_factors
    assert migrated_score.stop_factors == current_score.stop_factors


def test_empty_unconfirmed_profile_keeps_manual_review_cap_and_no_defaults() -> None:
    score = _score(CompanyCapabilityProfile())
    components = {item.key: item for item in score.components}

    assert score.total_score == 20
    assert score.total_score <= 64
    assert score.recommendation is ParticipationRecommendation.NOT_RECOMMENDED
    assert components["direction"].score == 0
    assert components["region"].score == 4
    assert components["price"].score == 4
    assert components["equipment"].score == 0
    assert "Недостаточно данных" in components["region"].explanation


def test_unconfirmed_sro_cannot_remove_mandatory_stop() -> None:
    analysis = _analysis(
        "Участник должен иметь обязательное членство в СРО и предоставить выписку из реестра СРО."
    )
    tender = make_tender(title="Монтаж видеонаблюдения", deadline_day=30)
    projection = BusinessCapabilityProjection.from_capability(_draft(sro_memberships=("СРО",)))

    assessment = StopFactorEngine(projection).evaluate(
        "tender:1", tender, analysis=analysis, now=NOW
    )

    assert assessment.status is StopFactorStatus.BLOCKED_BY_REQUIREMENT
    assert any(item.kind is StopFactorKind.REQUIRED_SRO_MISSING for item in assessment.factors)


def test_confirmed_sro_removes_only_the_satisfied_capability_stop() -> None:
    analysis = _analysis(
        "Участник должен иметь обязательное членство в СРО и предоставить выписку из реестра СРО."
    )
    tender = make_tender(title="Монтаж видеонаблюдения", deadline_day=30)
    projection = BusinessCapabilityProjection.from_capability(_confirmed(sro_memberships=("СРО",)))

    assessment = StopFactorEngine(projection).evaluate(
        "tender:1", tender, analysis=analysis, now=NOW
    )

    assert not any(item.kind is StopFactorKind.REQUIRED_SRO_MISSING for item in assessment.factors)


def test_equivalent_v1_v2_profiles_have_identical_stop_semantics(tmp_path: Path) -> None:
    migrated, current = _equivalent_v1_v2_profiles(
        tmp_path,
        sro_memberships=("СРО",),
    )
    tender = make_tender(title="Монтаж видеонаблюдения", amount="10000000", deadline_day=30)
    analysis = _analysis("Обеспечение исполнения контракта составляет 10%.")

    assessments = tuple(
        StopFactorEngine(BusinessCapabilityProjection.from_capability(profile)).evaluate(
            "tender:1", tender, analysis=analysis, now=NOW
        )
        for profile in (migrated, current)
    )

    assert assessments[0].status is assessments[1].status
    assert assessments[0].factors == assessments[1].factors
    assert assessments[0].evaluated_at == assessments[1].evaluated_at


def test_security_limit_uses_decimal_and_explicit_matching_currency() -> None:
    tender = make_tender(title="Монтаж видеонаблюдения", amount="10000000", deadline_day=30)
    projection = BusinessCapabilityProjection.from_capability(_confirmed())

    assessment = StopFactorEngine(projection).evaluate(
        "tender:1",
        tender,
        analysis=_analysis("Обеспечение исполнения контракта составляет 10%."),
        now=NOW,
    )

    factor = next(
        item
        for item in assessment.factors
        if item.kind is StopFactorKind.SECURITY_CAPACITY_EXCEEDED
    )
    assert assessment.status is StopFactorStatus.BLOCKED_BY_REQUIREMENT
    assert "1000000.00" in factor.description
    assert "500000" in factor.description


def test_foreign_currency_security_fails_closed_without_conversion() -> None:
    tender = replace(
        make_tender(title="Монтаж видеонаблюдения", amount="10000000", deadline_day=30),
        price=TenderMoney(Decimal("10000000"), "USD"),
    )
    projection = BusinessCapabilityProjection.from_capability(_confirmed())

    assessment = StopFactorEngine(projection).evaluate(
        "tender:1",
        tender,
        analysis=_analysis("Обеспечение исполнения контракта составляет 10%."),
        now=NOW,
    )

    factor = next(
        item
        for item in assessment.factors
        if item.kind is StopFactorKind.SECURITY_CAPACITY_EXCEEDED
    )
    assert assessment.status is StopFactorStatus.DATA_INSUFFICIENT
    assert factor.status is StopFactorStatus.DATA_INSUFFICIENT
    assert "USD" in factor.description
    assert "RUB" in factor.description


def test_critical_stop_still_overrides_high_score() -> None:
    tender = make_tender(
        title="Поставка и монтаж системы видеонаблюдения Trassir и СКУД",
        deadline_day=30,
    )
    projection = BusinessCapabilityProjection.from_capability(_confirmed())
    assessment = StopFactorEngine(projection).evaluate(
        "tender:1",
        tender,
        analysis=_analysis("Работы связаны с государственной тайной."),
        now=NOW,
    )
    score = CorterisParticipationRanker(
        CorterisCompanyProfile.from_business_profile(projection)
    ).score(
        tender,
        ParticipationScoringContext(now=NOW, stop_factor_assessment=assessment),
    )

    assert assessment.status is StopFactorStatus.BLOCKED_BY_REQUIREMENT
    assert score.recommendation is ParticipationRecommendation.NOT_RECOMMENDED
    assert not score.accepted_for_registry


def test_equivalent_v1_v2_profiles_keep_final_decision_contract(tmp_path: Path) -> None:
    migrated, current = _equivalent_v1_v2_profiles(tmp_path)
    tender = make_tender(title="Монтаж видеонаблюдения Trassir", amount="1500000")
    analysis = _analysis("Извещение без специальных обязательных требований.")
    verification = SimpleNamespace(
        registry_key="tender:1",
        status=TenderVerificationStatus.VERIFIED_OFFICIAL_API,
        minimum_confidence=0.9,
    )
    estimate = SimpleNamespace(
        registry_key="tender:1",
        status=CommercialEstimateStatus.COMPLETE,
    )

    class ScoreService:
        def __init__(self, score) -> None:
            self.score = score

        def latest(self, _registry_key: str):
            return self.score

    class StateRepository:
        def __init__(self, stop) -> None:
            self.stop = stop

        def get_latest_stop_factor_assessment(self, _registry_key: str):
            return self.stop

        def get_verification_state(self, _registry_key: str):
            return verification

        @staticmethod
        def save_participation_decision(_decision) -> None:
            return None

    class EstimateRepository:
        @staticmethod
        def latest(_registry_key: str):
            return ("estimate", estimate)

    decisions = []
    for profile in (migrated, current):
        projection = BusinessCapabilityProjection.from_capability(profile)
        stop = StopFactorEngine(projection).evaluate("tender:1", tender, analysis=analysis, now=NOW)
        score = CorterisParticipationRanker(
            CorterisCompanyProfile.from_business_profile(projection)
        ).score(
            tender,
            ParticipationScoringContext(
                now=NOW,
                requirement_analysis=analysis,
                stop_factor_assessment=stop,
            ),
        )
        decisions.append(
            ParticipationDecisionService(
                ScoreService(score),
                StateRepository(stop),
                EstimateRepository(),
            ).evaluate("tender:1")
        )

    left, right = decisions
    assert left.recommendation is right.recommendation
    assert left.summary == right.summary
    assert left.evidence == right.evidence
    assert left.missing == right.missing
    assert left.actions == right.actions
    assert left.score == right.score
    assert left.stop_factors == right.stop_factors
