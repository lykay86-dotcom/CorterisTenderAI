from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import re

import pytest

from app.core.ai.citations import resolve_citation
from app.core.ai.competition_review import (
    AI_COMPETITION_POLICY_VERSION,
    COMPETITION_CATEGORY_PRIORITIES,
    COMPETITION_SOURCE_POLICY,
    assess_competition_conditions,
    competition_source_findings,
)
from app.core.ai.financial_risk import assess_financial_risks
from app.core.ai.legal_risk import assess_legal_risks
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiAnalysisProvenance,
    AiAnalysisStatus,
    AiApplicationRequirementsStatus,
    AiDocument,
    AiDocumentAnalysis,
    AiDraftContractAnalysis,
    AiDraftContractStatus,
    AiCompetitionReviewPriority,
    AiCompetitionAssessment,
    AiCompetitionCategory,
    AiCompetitionItem,
    AiCompetitionSourceRef,
    AiCompetitionStatus,
    AiFinding,
    AiFindingStatus,
    AiSourceSnapshot,
    AiTechnicalSpecificationAnalysis,
    AiTechnicalSpecificationStatus,
    TenderRequirements,
)
from app.core.document_classification import DocumentKind


EXPECTED_SOURCE_POLICY = {
    ("requirements", "application_composition"): (
        AiCompetitionCategory.APPLICATION_AND_SUBMISSION_CONDITIONS
    ),
    ("requirements", "declarations_and_consents"): (
        AiCompetitionCategory.APPLICATION_AND_SUBMISSION_CONDITIONS
    ),
    ("requirements", "documents"): (AiCompetitionCategory.APPLICATION_AND_SUBMISSION_CONDITIONS),
    ("requirements", "submission_format_and_signature"): (
        AiCompetitionCategory.APPLICATION_AND_SUBMISSION_CONDITIONS
    ),
    ("requirements", "deadlines"): (AiCompetitionCategory.APPLICATION_AND_SUBMISSION_CONDITIONS),
    ("requirements", "participant_eligibility"): AiCompetitionCategory.PARTICIPANT_ELIGIBILITY,
    ("requirements", "experience"): AiCompetitionCategory.EXPERIENCE_AND_TRACK_RECORD,
    ("requirements", "licenses"): (AiCompetitionCategory.LICENSES_CERTIFICATES_AND_AUTHORIZATIONS),
    ("requirements", "certificates"): (
        AiCompetitionCategory.LICENSES_CERTIFICATES_AND_AUTHORIZATIONS
    ),
    ("requirements", "specialists"): AiCompetitionCategory.PERSONNEL_AND_EQUIPMENT,
    ("requirements", "equipment"): AiCompetitionCategory.PERSONNEL_AND_EQUIPMENT,
    ("requirements", "bid_security"): AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS,
    ("requirements", "contract_security"): AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS,
    ("requirements", "bank_guarantee"): AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS,
    ("requirements", "national_regime_and_origin"): (
        AiCompetitionCategory.NATIONAL_REGIME_AND_ORIGIN
    ),
    ("requirements", "grounds_for_rejection"): AiCompetitionCategory.GROUNDS_FOR_REJECTION,
    ("requirements", "ambiguities"): AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS,
    ("requirements", "clarification_points"): (
        AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("requirements", "contradictions"): AiCompetitionCategory.CONTRADICTIONS,
    ("technical_specification", "technical_characteristics"): (
        AiCompetitionCategory.TECHNICAL_SPECIFICITY_AND_EQUIVALENCE
    ),
    ("technical_specification", "materials_and_equipment"): (
        AiCompetitionCategory.TECHNICAL_SPECIFICITY_AND_EQUIVALENCE
    ),
    ("technical_specification", "standards_and_regulations"): (
        AiCompetitionCategory.STANDARDS_AND_COMPATIBILITY
    ),
    ("technical_specification", "acceptance_and_quality"): (
        AiCompetitionCategory.STANDARDS_AND_COMPATIBILITY
    ),
    ("technical_specification", "execution_conditions"): (
        AiCompetitionCategory.GEOGRAPHY_SITE_AND_EXECUTION_CONSTRAINTS
    ),
    ("technical_specification", "stages_and_deadlines"): (
        AiCompetitionCategory.GEOGRAPHY_SITE_AND_EXECUTION_CONSTRAINTS
    ),
    ("technical_specification", "customer_inputs_and_dependencies"): (
        AiCompetitionCategory.GEOGRAPHY_SITE_AND_EXECUTION_CONSTRAINTS
    ),
    ("technical_specification", "ambiguities"): (
        AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("technical_specification", "clarification_points"): (
        AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("technical_specification", "contradictions"): AiCompetitionCategory.CONTRADICTIONS,
    ("draft_contract", "term_schedule_and_location"): (
        AiCompetitionCategory.GEOGRAPHY_SITE_AND_EXECUTION_CONSTRAINTS
    ),
    ("draft_contract", "performance_security"): (
        AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS
    ),
    ("draft_contract", "contractor_obligations_and_subcontracting"): (
        AiCompetitionCategory.SUBCONTRACTING_AND_THIRD_PARTIES
    ),
    ("draft_contract", "ambiguities"): (AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS),
    ("draft_contract", "clarification_points"): (
        AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("draft_contract", "contradictions"): AiCompetitionCategory.CONTRADICTIONS,
}

_URGENT = {
    AiCompetitionCategory.GROUNDS_FOR_REJECTION,
    AiCompetitionCategory.CONTRADICTIONS,
}
_ELEVATED = {
    AiCompetitionCategory.PARTICIPANT_ELIGIBILITY,
    AiCompetitionCategory.EXPERIENCE_AND_TRACK_RECORD,
    AiCompetitionCategory.LICENSES_CERTIFICATES_AND_AUTHORIZATIONS,
    AiCompetitionCategory.PERSONNEL_AND_EQUIPMENT,
    AiCompetitionCategory.TECHNICAL_SPECIFICITY_AND_EQUIVALENCE,
    AiCompetitionCategory.NATIONAL_REGIME_AND_ORIGIN,
    AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS,
    AiCompetitionCategory.GEOGRAPHY_SITE_AND_EXECUTION_CONSTRAINTS,
}
EXPECTED_PRIORITIES = {
    category: (
        AiCompetitionReviewPriority.URGENT
        if category in _URGENT
        else AiCompetitionReviewPriority.ELEVATED
        if category in _ELEVATED
        else AiCompetitionReviewPriority.ROUTINE
    )
    for category in AiCompetitionCategory
}
EXPECTED_PRESENTATION = {
    AiCompetitionCategory.APPLICATION_AND_SUBMISSION_CONDITIONS: (
        "Состав и процедура подачи заявки",
        "Оценить административную нагрузку и однозначность выполнения требований к подаче; "
        "не трактовать их как ограничение конкуренции автоматически.",
    ),
    AiCompetitionCategory.PARTICIPANT_ELIGIBILITY: (
        "Требования к допуску участника",
        "Проверить обязательность и соразмерность требований к участнику и их возможное "
        "влияние на круг допустимых участников.",
    ),
    AiCompetitionCategory.EXPERIENCE_AND_TRACK_RECORD: (
        "Опыт и подтверждённая квалификация",
        "Проверить соразмерность требуемого опыта предмету закупки и допустимые способы его "
        "подтверждения.",
    ),
    AiCompetitionCategory.LICENSES_CERTIFICATES_AND_AUTHORIZATIONS: (
        "Лицензии, сертификаты и авторизации",
        "Проверить обязательность документов, допустимые аналоги и доступность подтверждения "
        "без автоматического вывода об ограничении.",
    ),
    AiCompetitionCategory.PERSONNEL_AND_EQUIPMENT: (
        "Персонал и оборудование участника",
        "Проверить требования к собственным ресурсам, возможность аренды, привлечения партнёров "
        "или эквивалентного подтверждения.",
    ),
    AiCompetitionCategory.TECHNICAL_SPECIFICITY_AND_EQUIVALENCE: (
        "Техническая специфика и эквивалентность",
        "Проверить функциональность характеристик, допустимость эквивалентов и нейтральность "
        "технического описания; не делать автоматический вывод о заточке.",
    ),
    AiCompetitionCategory.STANDARDS_AND_COMPATIBILITY: (
        "Стандарты, качество и совместимость",
        "Проверить применимость стандартов, методы подтверждения качества и доступность "
        "совместимых решений.",
    ),
    AiCompetitionCategory.NATIONAL_REGIME_AND_ORIGIN: (
        "Национальный режим и происхождение",
        "Проверить применимые ограничения, допустимые товары и документы о происхождении.",
    ),
    AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS: (
        "Обеспечение и финансовый порог участия",
        "Проверить форму и условия обеспечения и их влияние на доступность участия без расчёта "
        "уровня конкуренции.",
    ),
    AiCompetitionCategory.GEOGRAPHY_SITE_AND_EXECUTION_CONSTRAINTS: (
        "География, объект и сроки исполнения",
        "Проверить обязательность присутствия или осмотра, территориальные условия и "
        "реалистичность сроков для потенциальных участников.",
    ),
    AiCompetitionCategory.SUBCONTRACTING_AND_THIRD_PARTIES: (
        "Субподряд, партнёры и третьи лица",
        "Проверить ограничения на субподряд и партнёрскую модель исполнения и их влияние на "
        "допустимый круг участников.",
    ),
    AiCompetitionCategory.GROUNDS_FOR_REJECTION: (
        "Основания отклонения заявки",
        "Срочно проверить однозначность основания отклонения и возможность полного выполнения "
        "требования до подачи заявки.",
    ),
    AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS: (
        "Неоднозначности условий участия",
        "Сформулировать запрос на разъяснение; не делать вывод о состоянии конкуренции до "
        "получения официального ответа.",
    ),
    AiCompetitionCategory.CONTRADICTIONS: (
        "Противоречия условий участия",
        "Срочно сопоставить независимые источники и запросить официальное разъяснение.",
    ),
}

_SECTION_KIND = {
    "requirements": DocumentKind.APPLICATION_REQUIREMENTS,
    "technical_specification": DocumentKind.TECHNICAL_SPECIFICATION,
    "draft_contract": DocumentKind.DRAFT_CONTRACT,
}


def _analysis(
    section: str | None = None,
    field: str | None = None,
    *,
    quotes: tuple[str, ...] = ("exact competition condition",),
    statement: str = "Provider statement",
    verified: bool = True,
    source_kind: DocumentKind | None = None,
    analysis_status: AiAnalysisStatus = AiAnalysisStatus.COMPLETE,
    requirements_status: AiApplicationRequirementsStatus = (
        AiApplicationRequirementsStatus.COMPLETE
    ),
    technical_status: AiTechnicalSpecificationStatus = AiTechnicalSpecificationStatus.COMPLETE,
    contract_status: AiDraftContractStatus = AiDraftContractStatus.COMPLETE,
    requirements_present: bool = True,
    technical_present: bool = True,
    contract_present: bool = True,
    context_truncated: bool = False,
) -> AiDocumentAnalysis:
    fingerprint = "e" * 64
    documents: dict[str, AiDocument] = {}
    sources: list[AiSourceSnapshot] = []
    for current_section, kind in _SECTION_KIND.items():
        current_kind = source_kind if current_section == section and source_kind else kind
        text = " | ".join(quotes) if current_section == section else f"{current_section} context"
        document_id = f"{current_section}-doc"
        checksum = hashlib.sha256(text.encode()).hexdigest()
        documents[current_section] = AiDocument(
            document_id,
            f"{current_section}.pdf",
            "local_document_store",
            "pdf",
            "2026-07-15T12:00:00+00:00",
            "verified",
            text,
            checksum,
            original_character_count=len(text),
            document_kind=current_kind.value,
        )
        sources.append(
            AiSourceSnapshot(
                document_id,
                f"{current_section}.pdf",
                "pdf",
                checksum,
                "verified",
                "2026-07-15T12:00:00+00:00",
                False,
                len(text),
                len(text),
                current_kind.value,
            )
        )

    findings: tuple[AiFinding, ...] = ()
    if section and field:
        built: list[AiFinding] = []
        for quote in quotes:
            evidence = resolve_citation(
                document_id=documents[section].document_id,
                quote=quote,
                section="",
                page=None,
                confidence=0.9,
                documents=tuple(documents.values()),
                context_fingerprint=fingerprint,
            ).evidence
            assert evidence is not None
            built.append(
                AiFinding(
                    f"{section}.{field}",
                    statement,
                    evidence if verified else None,
                    AiFindingStatus.VERIFIED if verified else AiFindingStatus.UNVERIFIED,
                )
            )
        findings = tuple(built)

    requirements = TenderRequirements(
        status=requirements_status,
        document_ids=((documents["requirements"].document_id,) if requirements_present else ()),
        included_document_ids=(
            (documents["requirements"].document_id,) if requirements_present else ()
        ),
    )
    technical = AiTechnicalSpecificationAnalysis(
        status=technical_status,
        document_ids=(
            (documents["technical_specification"].document_id,) if technical_present else ()
        ),
        included_document_ids=(
            (documents["technical_specification"].document_id,) if technical_present else ()
        ),
    )
    contract = AiDraftContractAnalysis(
        status=contract_status,
        document_ids=((documents["draft_contract"].document_id,) if contract_present else ()),
        included_document_ids=(
            (documents["draft_contract"].document_id,) if contract_present else ()
        ),
    )
    if section == "requirements" and field:
        requirements = replace(requirements, **{field: findings})
    elif section == "technical_specification" and field:
        technical = replace(technical, **{field: findings})
    elif section == "draft_contract" and field:
        contract = replace(contract, **{field: findings})

    provenance = AiAnalysisProvenance(
        analysis_id="analysis_122",
        context_fingerprint=fingerprint,
        created_at="2026-07-15T12:01:00+00:00",
        prompt_version="6",
        output_schema_version="4",
        persisted_schema_version=AI_ANALYSIS_SCHEMA_VERSION,
        analyzer_version="12",
        context_version="6",
        citation_resolver_version="1",
        provider_id="openai",
        provider_model="gpt-5",
        provider_response_id="resp_" + "a" * 64,
        sources=tuple(sources),
    )
    return AiDocumentAnalysis(
        "procurement:122",
        "Safe summary",
        status=analysis_status,
        provenance=provenance,
        requirements=requirements,
        technical_specification=technical,
        draft_contract=contract,
        context_truncated=context_truncated,
    )


def _with_assessments(analysis: AiDocumentAnalysis) -> AiDocumentAnalysis:
    analysis = replace(analysis, legal_risk_assessment=assess_legal_risks(analysis))
    analysis = replace(analysis, financial_risk_assessment=assess_financial_risks(analysis))
    return replace(analysis, competition_assessment=assess_competition_conditions(analysis))


def test_policy_contract_is_exact_and_versioned() -> None:
    assert AI_COMPETITION_POLICY_VERSION == "1"
    assert COMPETITION_SOURCE_POLICY == EXPECTED_SOURCE_POLICY
    assert COMPETITION_CATEGORY_PRIORITIES == EXPECTED_PRIORITIES
    assert "critical" not in {item.value for item in AiCompetitionReviewPriority}


@pytest.mark.parametrize(("source", "category"), tuple(EXPECTED_SOURCE_POLICY.items()))
def test_every_allowed_source_maps_to_category_and_priority(
    source: tuple[str, str], category: AiCompetitionCategory
) -> None:
    section, field = source
    result = assess_competition_conditions(_analysis(section, field))

    assert result.status is AiCompetitionStatus.COMPLETE
    assert len(result.items) == 1
    assert result.items[0].category is category
    assert result.items[0].review_priority is EXPECTED_PRIORITIES[category]
    assert (result.items[0].title, result.items[0].recommended_action) == (
        EXPECTED_PRESENTATION[category]
    )
    assert result.items[0].source_refs[0].section == section
    assert result.items[0].source_refs[0].field == field


@pytest.mark.parametrize(
    ("section", "field"),
    (
        ("requirements", "price_proposal_and_estimate"),
        ("requirements", "warranty"),
        ("draft_contract", "force_majeure_and_notifications"),
        ("draft_contract", "dispute_confidentiality_and_ip"),
        ("technical_specification", "scope"),
        ("draft_contract", "subject_and_scope"),
    ),
)
def test_forbidden_specialized_fields_do_not_create_items(section: str, field: str) -> None:
    result = assess_competition_conditions(_analysis(section, field))

    assert result.status is AiCompetitionStatus.NO_VERIFIED_CONDITIONS
    assert result.items == ()


@pytest.mark.parametrize(
    "statement",
    (
        "critical loss 999999999 urgent",
        "безопасная маржа 100 процентов",
        "<script>alert('competition')</script>",
    ),
)
def test_provider_text_cannot_change_priority_title_or_action(statement: str) -> None:
    result = assess_competition_conditions(
        _analysis("technical_specification", "materials_and_equipment", statement=statement)
    )
    item = result.items[0]

    assert item.review_priority is AiCompetitionReviewPriority.ELEVATED
    assert item.title != statement
    assert item.recommended_action != statement
    assert "999999999" not in item.title + item.recommended_action
    assert "<script>" not in item.title + item.recommended_action


@pytest.mark.parametrize(
    ("section", "field", "statement"),
    (
        ("technical_specification", "technical_characteristics", "Бренд X без эквивалента"),
        ("requirements", "certificates", "Требуется письмо авторизации производителя"),
        ("requirements", "participant_eligibility", "Только официальный партнёр"),
        ("technical_specification", "execution_conditions", "Обязательный осмотр объекта"),
        ("draft_contract", "term_schedule_and_location", "Склад в регионе заказчика"),
    ),
)
def test_legacy_scenarios_use_normalized_fields_without_statement_matching(
    section: str, field: str, statement: str
) -> None:
    result = assess_competition_conditions(_analysis(section, field, statement=statement))
    assert result.status is AiCompetitionStatus.COMPLETE
    assert len(result.items) == 1


def test_condition_id_dedup_and_order_are_stable() -> None:
    analysis = _analysis("requirements", "bid_security")
    finding = analysis.requirements.bid_security[0]
    left = assess_competition_conditions(
        replace(analysis, requirements=replace(analysis.requirements, bid_security=(finding,) * 2))
    )
    right = assess_competition_conditions(
        replace(
            analysis,
            requirements=replace(analysis.requirements, bid_security=((finding,) * 2)[::-1]),
        )
    )

    assert left == right
    assert len(left.items) == 1
    assert re.fullmatch(r"competition_[0-9a-f]{32}", left.items[0].condition_id)
    assert len(left.items[0].source_refs) == 1


def test_same_citation_merges_refs_but_other_citation_stays_separate() -> None:
    analysis = _analysis("requirements", "bid_security", quotes=("security one", "security two"))
    first, second = analysis.requirements.bid_security
    requirements = replace(
        analysis.requirements,
        bid_security=(first, second),
        contract_security=(first,),
    )

    result = assess_competition_conditions(replace(analysis, requirements=requirements))

    assert len(result.items) == 2
    merged = next(
        item
        for item in result.items
        if item.source_refs[0].citation_id == first.evidence.citation_id
    )
    assert tuple((ref.section, ref.field) for ref in merged.source_refs) == (
        ("requirements", "bid_security"),
        ("requirements", "contract_security"),
    )


def test_domain_objects_are_immutable_and_strings_are_bounded() -> None:
    result = assess_competition_conditions(_analysis("draft_contract", "performance_security"))
    with pytest.raises(FrozenInstanceError):
        result.status = AiCompetitionStatus.PARTIAL  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.items[0].title = "tampered"  # type: ignore[misc]

    ref = result.items[0].source_refs[0]
    item = AiCompetitionItem(
        "competition_" + "b" * 32,
        AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS,
        AiCompetitionReviewPriority.ELEVATED,
        "t" * 600,
        (ref,),
        "a" * 1200,
    )
    assert len(item.title) == 500
    assert len(item.recommended_action) == 1000


def test_invalid_ids_unknown_values_and_duplicate_refs_are_rejected() -> None:
    with pytest.raises(ValueError):
        AiCompetitionSourceRef("requirements", "price_proposal_and_estimate", "cit_" + "a" * 32)
    with pytest.raises(ValueError):
        AiCompetitionSourceRef("requirements", "bid_security", "bad")
    ref = AiCompetitionSourceRef("requirements", "bid_security", "cit_" + "a" * 32)
    with pytest.raises(ValueError):
        AiCompetitionItem(
            "bad",
            AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS,
            AiCompetitionReviewPriority.ELEVATED,
            "title",
            (ref,),
            "action",
        )
    with pytest.raises(ValueError):
        AiCompetitionItem(
            "competition_" + "b" * 32,
            "unknown",  # type: ignore[arg-type]
            "critical",  # type: ignore[arg-type]
            "title",
            (ref, ref),
            "action",
        )


@pytest.mark.parametrize(
    ("attribute", "value"),
    (
        ("checksum_sha256", "0" * 64),
        ("context_fingerprint", "0" * 64),
        ("citation_id", "cit_" + "0" * 32),
    ),
)
def test_tampered_evidence_is_rejected(attribute: str, value: str) -> None:
    analysis = _analysis("draft_contract", "performance_security")
    finding = analysis.draft_contract.performance_security[0]
    assert finding.evidence is not None
    tampered = replace(finding, evidence=replace(finding.evidence, **{attribute: value}))
    contract = replace(analysis.draft_contract, performance_security=(tampered,))

    result = assess_competition_conditions(replace(analysis, draft_contract=contract))

    assert result.status is AiCompetitionStatus.PARTIAL
    assert result.items == ()
    assert result.warnings


def test_missing_provenance_foreign_kind_and_duplicate_source_fail_closed() -> None:
    no_provenance = assess_competition_conditions(
        replace(_analysis("draft_contract", "performance_security"), provenance=None)
    )
    assert no_provenance.status is AiCompetitionStatus.UNAVAILABLE

    foreign = assess_competition_conditions(
        _analysis(
            "requirements",
            "bid_security",
            source_kind=DocumentKind.DRAFT_CONTRACT,
        )
    )
    assert foreign.status is AiCompetitionStatus.PARTIAL
    assert foreign.items == ()

    analysis = _analysis("draft_contract", "performance_security")
    assert analysis.provenance is not None
    duplicated = replace(
        analysis,
        provenance=replace(
            analysis.provenance,
            sources=(*analysis.provenance.sources, analysis.provenance.sources[-1]),
        ),
    )
    duplicate_result = assess_competition_conditions(duplicated)
    assert duplicate_result.status is AiCompetitionStatus.PARTIAL
    assert duplicate_result.items == ()


def test_unverified_and_generic_findings_are_not_promoted() -> None:
    unverified = assess_competition_conditions(
        _analysis("draft_contract", "performance_security", verified=False)
    )
    assert unverified.status is AiCompetitionStatus.PARTIAL
    assert unverified.items == ()

    analysis = _analysis()
    generic = _analysis(
        "draft_contract", "performance_security"
    ).draft_contract.performance_security[0]
    generic_result = assess_competition_conditions(
        replace(
            analysis, risks=(generic,), suspicious_conditions=(generic,), contradictions=(generic,)
        )
    )
    assert generic_result.status is AiCompetitionStatus.NO_VERIFIED_CONDITIONS
    assert generic_result.items == ()


@pytest.mark.parametrize(
    ("changes", "expected"),
    (
        ({}, AiCompetitionStatus.NO_VERIFIED_CONDITIONS),
        (
            {"section": "draft_contract", "field": "performance_security"},
            AiCompetitionStatus.COMPLETE,
        ),
        (
            {"requirements_status": AiApplicationRequirementsStatus.PARTIAL},
            AiCompetitionStatus.PARTIAL,
        ),
        ({"requirements_present": False}, AiCompetitionStatus.PARTIAL),
        ({"technical_present": False}, AiCompetitionStatus.PARTIAL),
        ({"contract_present": False}, AiCompetitionStatus.NO_VERIFIED_CONDITIONS),
        ({"contract_status": AiDraftContractStatus.PARTIAL}, AiCompetitionStatus.PARTIAL),
        (
            {"technical_status": AiTechnicalSpecificationStatus.PARTIAL},
            AiCompetitionStatus.PARTIAL,
        ),
        ({"context_truncated": True}, AiCompetitionStatus.PARTIAL),
        (
            {"analysis_status": AiAnalysisStatus.PROVIDER_DISABLED},
            AiCompetitionStatus.UNAVAILABLE,
        ),
        ({"analysis_status": AiAnalysisStatus.PROVIDER_ERROR}, AiCompetitionStatus.UNAVAILABLE),
        ({"analysis_status": AiAnalysisStatus.INVALID_RESPONSE}, AiCompetitionStatus.UNAVAILABLE),
        ({"analysis_status": AiAnalysisStatus.NO_DOCUMENTS}, AiCompetitionStatus.UNAVAILABLE),
        (
            {"analysis_status": AiAnalysisStatus.CACHE_INCOMPATIBLE},
            AiCompetitionStatus.UNAVAILABLE,
        ),
    ),
)
def test_status_matrix(changes: dict[str, object], expected: AiCompetitionStatus) -> None:
    changes = dict(changes)
    section = changes.pop("section", None)
    field = changes.pop("field", None)
    result = assess_competition_conditions(_analysis(section, field, **changes))  # type: ignore[arg-type]
    assert result.status is expected


def test_source_resolution_returns_only_current_policy_findings() -> None:
    analysis = _analysis("draft_contract", "performance_security")
    result = assess_competition_conditions(analysis)
    assert competition_source_findings(analysis, result.items[0]) == (
        analysis.draft_contract.performance_security[0],
    )

    stale = replace(
        analysis,
        draft_contract=replace(
            analysis.draft_contract,
            performance_security=(
                replace(analysis.draft_contract.performance_security[0], evidence=None),
            ),
        ),
    )
    assert competition_source_findings(stale, result.items[0]) == ()


def test_v9_payload_has_exact_competition_keys_and_round_trips() -> None:
    analysis = _with_assessments(_analysis("draft_contract", "performance_security"))
    payload = analysis.to_payload()
    competition = payload["competition_assessment"]
    assert set(competition) == {"status", "policy_version", "items", "warnings"}
    assert set(competition["items"][0]) == {
        "condition_id",
        "category",
        "review_priority",
        "title",
        "source_refs",
        "recommended_action",
    }
    assert set(competition["items"][0]["source_refs"][0]) == {
        "section",
        "field",
        "citation_id",
    }

    restored = AiDocumentAnalysis.from_payload(json.loads(json.dumps(payload)))

    assert restored.payload_version == AI_ANALYSIS_SCHEMA_VERSION == 10
    assert restored.competition_assessment == analysis.competition_assessment
    assert restored.legal_risk_assessment == analysis.legal_risk_assessment


@pytest.mark.parametrize("legacy_version", range(1, 9))
def test_legacy_payload_never_promotes_competition_assessment(legacy_version: int) -> None:
    payload = _with_assessments(_analysis("draft_contract", "performance_security")).to_payload()
    payload["payload_version"] = legacy_version

    restored = AiDocumentAnalysis.from_payload(payload)

    assert restored.competition_assessment.status is AiCompetitionStatus.UNAVAILABLE
    assert restored.competition_assessment.items == ()


@pytest.mark.parametrize(
    ("path", "tampered"),
    (
        (("status",), "unavailable"),
        (("category",), "unknown"),
        (("review_priority",), "critical"),
        (("title",), "provider controlled"),
        (("recommended_action",), "provider controlled"),
        (("condition_id",), "competition_" + "0" * 32),
        (("source_refs", 0, "field"), "price_proposal_and_estimate"),
        (("source_refs", 0, "citation_id"), "cit_" + "0" * 32),
    ),
)
def test_tampered_current_payload_is_not_trusted(
    path: tuple[object, ...], tampered: object
) -> None:
    analysis = _with_assessments(_analysis("draft_contract", "performance_security"))
    payload = analysis.to_payload()
    target: object = payload["competition_assessment"]
    if path[0] != "status":
        target = target["items"][0]  # type: ignore[index]
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = tampered  # type: ignore[index]

    restored = AiDocumentAnalysis.from_payload(payload)

    assert restored.competition_assessment.status is AiCompetitionStatus.PARTIAL
    assert "provider controlled" not in json.dumps(
        restored.competition_assessment.to_payload(), ensure_ascii=False
    )
    assert restored.competition_assessment.warnings


def test_duplicate_persisted_refs_and_future_payload_fail_closed() -> None:
    analysis = _with_assessments(_analysis("draft_contract", "performance_security"))
    payload = analysis.to_payload()
    refs = payload["competition_assessment"]["items"][0]["source_refs"]
    refs.append(dict(refs[0]))
    restored = AiDocumentAnalysis.from_payload(payload)
    assert restored.competition_assessment.status is AiCompetitionStatus.PARTIAL

    future = analysis.to_payload()
    future["payload_version"] = AI_ANALYSIS_SCHEMA_VERSION + 1
    restored_future = AiDocumentAnalysis.from_payload(future)
    assert restored_future.status is AiAnalysisStatus.CACHE_INCOMPATIBLE
    assert restored_future.competition_assessment.status is AiCompetitionStatus.UNAVAILABLE


def test_payload_contains_no_external_or_private_metadata() -> None:
    rendered = json.dumps(
        assess_competition_conditions(
            _analysis("draft_contract", "performance_security")
        ).to_payload(),
        ensure_ascii=False,
    )
    for forbidden in ("file://", "C:\\Users", "http://", "https://", "raw_response", "prompt"):
        assert forbidden not in rendered


def test_competition_policy_has_no_io_money_parsing_or_legacy_imports() -> None:
    path = Path(__file__).parents[1] / "app" / "core" / "ai" / "competition_review.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert not imports & {"decimal", "pathlib", "sqlite3", "requests", "urllib", "re"}
    assert "open" not in calls
    for forbidden in (
        "provider.analyze",
        "COMP_RULES",
        "raw_metadata",
        "CompanyCapabilityProfile",
        "app.tender_analysis.engine",
    ):
        assert forbidden not in source


def test_public_types_represent_fail_closed_result() -> None:
    result = AiCompetitionAssessment(
        AiCompetitionStatus.UNAVAILABLE,
        AI_COMPETITION_POLICY_VERSION,
        (),
        ("Недостаточно проверяемых данных.",),
    )
    ref = AiCompetitionSourceRef("draft_contract", "performance_security", "cit_" + "a" * 32)
    item = AiCompetitionItem(
        "competition_" + "b" * 32,
        AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS,
        AiCompetitionReviewPriority.ELEVATED,
        "Обеспечение и финансовый порог участия",
        (ref,),
        "Сверить условия вручную.",
    )

    assert result.to_payload()["status"] == "unavailable"
    assert item.to_payload()["source_refs"][0]["citation_id"] == ref.citation_id
