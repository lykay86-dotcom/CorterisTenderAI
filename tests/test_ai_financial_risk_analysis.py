from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

import pytest

from app.core.ai.citations import resolve_citation
from app.core.ai.competition_review import assess_competition_conditions
from app.core.ai.financial_risk import (
    AI_FINANCIAL_RISK_POLICY_VERSION,
    FINANCIAL_RISK_CATEGORY_PRIORITIES,
    FINANCIAL_RISK_SOURCE_POLICY,
    assess_financial_risks,
    financial_risk_source_findings,
)
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
    AiFinancialReviewPriority,
    AiFinancialRiskAssessment,
    AiFinancialRiskCategory,
    AiFinancialRiskItem,
    AiFinancialRiskSourceRef,
    AiFinancialRiskStatus,
    AiFinding,
    AiFindingStatus,
    AiSourceSnapshot,
    AiTechnicalSpecificationAnalysis,
    AiTechnicalSpecificationStatus,
    TenderRequirements,
)
from app.core.document_classification import DocumentKind
from app.tenders.commercial_estimator import (
    CommercialEstimateDraft,
    CommercialEstimateStatus,
    CommercialEstimator,
)


EXPECTED_SOURCE_POLICY = {
    ("requirements", "price_proposal_and_estimate"): (AiFinancialRiskCategory.PRICE_AND_ESTIMATE),
    ("requirements", "bid_security"): (AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS),
    ("requirements", "contract_security"): (AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS),
    ("requirements", "bank_guarantee"): (AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS),
    ("requirements", "warranty"): AiFinancialRiskCategory.WARRANTY_AND_DEFECT_COSTS,
    ("requirements", "national_regime_and_origin"): (
        AiFinancialRiskCategory.NATIONAL_REGIME_AND_SUPPLY_RESTRICTIONS
    ),
    ("requirements", "ambiguities"): (AiFinancialRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS),
    ("requirements", "clarification_points"): (
        AiFinancialRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("requirements", "contradictions"): AiFinancialRiskCategory.CONTRADICTIONS,
    ("technical_specification", "scope"): (AiFinancialRiskCategory.SCOPE_AND_VOLUME_UNCERTAINTY),
    ("technical_specification", "deliverables"): (
        AiFinancialRiskCategory.SCOPE_AND_VOLUME_UNCERTAINTY
    ),
    ("technical_specification", "quantities_and_volumes"): (
        AiFinancialRiskCategory.SCOPE_AND_VOLUME_UNCERTAINTY
    ),
    ("technical_specification", "technical_characteristics"): (
        AiFinancialRiskCategory.MATERIALS_AND_EQUIPMENT_COSTS
    ),
    ("technical_specification", "materials_and_equipment"): (
        AiFinancialRiskCategory.MATERIALS_AND_EQUIPMENT_COSTS
    ),
    ("technical_specification", "execution_conditions"): (
        AiFinancialRiskCategory.EXECUTION_SCHEDULE_AND_RESOURCE_LOAD
    ),
    ("technical_specification", "stages_and_deadlines"): (
        AiFinancialRiskCategory.EXECUTION_SCHEDULE_AND_RESOURCE_LOAD
    ),
    ("technical_specification", "acceptance_and_quality"): (
        AiFinancialRiskCategory.ACCEPTANCE_AND_PAYMENT_DEPENDENCY
    ),
    ("technical_specification", "customer_inputs_and_dependencies"): (
        AiFinancialRiskCategory.CUSTOMER_INPUTS_AND_DEPENDENCIES
    ),
    ("technical_specification", "ambiguities"): (
        AiFinancialRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("technical_specification", "clarification_points"): (
        AiFinancialRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("technical_specification", "contradictions"): AiFinancialRiskCategory.CONTRADICTIONS,
    ("draft_contract", "subject_and_scope"): (AiFinancialRiskCategory.SCOPE_AND_VOLUME_UNCERTAINTY),
    ("draft_contract", "term_schedule_and_location"): (
        AiFinancialRiskCategory.EXECUTION_SCHEDULE_AND_RESOURCE_LOAD
    ),
    ("draft_contract", "price_and_price_change"): (AiFinancialRiskCategory.PRICE_AND_ESTIMATE),
    ("draft_contract", "payment_terms"): AiFinancialRiskCategory.PAYMENT_AND_CASH_FLOW,
    ("draft_contract", "acceptance_and_closing_documents"): (
        AiFinancialRiskCategory.ACCEPTANCE_AND_PAYMENT_DEPENDENCY
    ),
    ("draft_contract", "performance_security"): (
        AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS
    ),
    ("draft_contract", "warranty_and_defect_remediation"): (
        AiFinancialRiskCategory.WARRANTY_AND_DEFECT_COSTS
    ),
    ("draft_contract", "customer_obligations_and_dependencies"): (
        AiFinancialRiskCategory.CUSTOMER_INPUTS_AND_DEPENDENCIES
    ),
    ("draft_contract", "contractor_obligations_and_subcontracting"): (
        AiFinancialRiskCategory.SUBCONTRACTING_AND_THIRD_PARTY_COSTS
    ),
    ("draft_contract", "liability_penalties_and_damages"): (
        AiFinancialRiskCategory.LIABILITY_PENALTIES_AND_DAMAGES
    ),
    ("draft_contract", "change_suspension_and_termination"): (
        AiFinancialRiskCategory.CHANGE_SUSPENSION_AND_TERMINATION
    ),
    ("draft_contract", "ambiguities"): (AiFinancialRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS),
    ("draft_contract", "clarification_points"): (
        AiFinancialRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("draft_contract", "contradictions"): AiFinancialRiskCategory.CONTRADICTIONS,
}

_ELEVATED = {
    AiFinancialRiskCategory.PRICE_AND_ESTIMATE,
    AiFinancialRiskCategory.PAYMENT_AND_CASH_FLOW,
    AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS,
    AiFinancialRiskCategory.SCOPE_AND_VOLUME_UNCERTAINTY,
    AiFinancialRiskCategory.ACCEPTANCE_AND_PAYMENT_DEPENDENCY,
    AiFinancialRiskCategory.WARRANTY_AND_DEFECT_COSTS,
    AiFinancialRiskCategory.LIABILITY_PENALTIES_AND_DAMAGES,
    AiFinancialRiskCategory.CHANGE_SUSPENSION_AND_TERMINATION,
}
EXPECTED_PRIORITIES = {
    category: (
        AiFinancialReviewPriority.URGENT
        if category is AiFinancialRiskCategory.CONTRADICTIONS
        else AiFinancialReviewPriority.ELEVATED
        if category in _ELEVATED
        else AiFinancialReviewPriority.ROUTINE
    )
    for category in AiFinancialRiskCategory
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
    quotes: tuple[str, ...] = ("exact financial condition",),
    statement: str = "Provider statement",
    verified: bool = True,
    source_kind: DocumentKind | None = None,
    analysis_status: AiAnalysisStatus = AiAnalysisStatus.COMPLETE,
    requirements_status: AiApplicationRequirementsStatus = (
        AiApplicationRequirementsStatus.COMPLETE
    ),
    technical_status: AiTechnicalSpecificationStatus = AiTechnicalSpecificationStatus.COMPLETE,
    contract_status: AiDraftContractStatus = AiDraftContractStatus.COMPLETE,
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
        document_ids=(documents["requirements"].document_id,),
        included_document_ids=(documents["requirements"].document_id,),
    )
    technical = AiTechnicalSpecificationAnalysis(
        status=technical_status,
        document_ids=(documents["technical_specification"].document_id,),
        included_document_ids=(documents["technical_specification"].document_id,),
    )
    contract = AiDraftContractAnalysis(
        status=contract_status,
        document_ids=(documents["draft_contract"].document_id,),
        included_document_ids=(documents["draft_contract"].document_id,),
    )
    if section == "requirements" and field:
        requirements = replace(requirements, **{field: findings})
    elif section == "technical_specification" and field:
        technical = replace(technical, **{field: findings})
    elif section == "draft_contract" and field:
        contract = replace(contract, **{field: findings})

    provenance = AiAnalysisProvenance(
        analysis_id="analysis_121",
        context_fingerprint=fingerprint,
        created_at="2026-07-15T12:01:00+00:00",
        prompt_version="6",
        output_schema_version="4",
        persisted_schema_version=AI_ANALYSIS_SCHEMA_VERSION,
        analyzer_version="10",
        context_version="5",
        citation_resolver_version="1",
        provider_id="openai",
        provider_model="gpt-5",
        provider_response_id="resp_" + "a" * 64,
        sources=tuple(sources),
    )
    return AiDocumentAnalysis(
        "procurement:121",
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
    assert AI_FINANCIAL_RISK_POLICY_VERSION == "1"
    assert FINANCIAL_RISK_SOURCE_POLICY == EXPECTED_SOURCE_POLICY
    assert FINANCIAL_RISK_CATEGORY_PRIORITIES == EXPECTED_PRIORITIES
    assert "critical" not in {item.value for item in AiFinancialReviewPriority}


@pytest.mark.parametrize(("source", "category"), tuple(EXPECTED_SOURCE_POLICY.items()))
def test_every_allowed_source_maps_to_category_and_priority(
    source: tuple[str, str], category: AiFinancialRiskCategory
) -> None:
    section, field = source
    result = assess_financial_risks(_analysis(section, field))

    assert result.status is AiFinancialRiskStatus.COMPLETE
    assert len(result.items) == 1
    assert result.items[0].category is category
    assert result.items[0].review_priority is EXPECTED_PRIORITIES[category]
    assert result.items[0].source_refs[0].section == section
    assert result.items[0].source_refs[0].field == field


@pytest.mark.parametrize(
    ("section", "field"),
    (
        ("requirements", "licenses"),
        ("requirements", "application_composition"),
        ("draft_contract", "force_majeure_and_notifications"),
        ("draft_contract", "dispute_confidentiality_and_ip"),
        ("technical_specification", "standards_and_regulations"),
    ),
)
def test_forbidden_specialized_fields_do_not_create_items(section: str, field: str) -> None:
    result = assess_financial_risks(_analysis(section, field))

    assert result.status is AiFinancialRiskStatus.NO_VERIFIED_CONDITIONS
    assert result.items == ()


@pytest.mark.parametrize(
    "statement",
    (
        "critical loss 999999999 urgent",
        "безопасная маржа 100 процентов",
        "<script>alert('financial')</script>",
    ),
)
def test_provider_text_cannot_change_priority_title_or_action(statement: str) -> None:
    result = assess_financial_risks(
        _analysis("technical_specification", "materials_and_equipment", statement=statement)
    )
    item = result.items[0]

    assert item.review_priority is AiFinancialReviewPriority.ROUTINE
    assert item.title != statement
    assert item.recommended_action != statement
    assert "999999999" not in item.title + item.recommended_action
    assert "<script>" not in item.title + item.recommended_action


def test_risk_id_dedup_and_order_are_stable() -> None:
    analysis = _analysis("requirements", "bid_security")
    finding = analysis.requirements.bid_security[0]
    left = assess_financial_risks(
        replace(analysis, requirements=replace(analysis.requirements, bid_security=(finding,) * 2))
    )
    right = assess_financial_risks(
        replace(
            analysis,
            requirements=replace(analysis.requirements, bid_security=((finding,) * 2)[::-1]),
        )
    )

    assert left == right
    assert len(left.items) == 1
    assert re.fullmatch(r"financial_[0-9a-f]{32}", left.items[0].risk_id)
    assert len(left.items[0].source_refs) == 1


def test_same_citation_merges_refs_but_other_citation_stays_separate() -> None:
    analysis = _analysis("requirements", "bid_security", quotes=("security one", "security two"))
    first, second = analysis.requirements.bid_security
    requirements = replace(
        analysis.requirements,
        bid_security=(first, second),
        contract_security=(first,),
    )

    result = assess_financial_risks(replace(analysis, requirements=requirements))

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
    result = assess_financial_risks(_analysis("draft_contract", "payment_terms"))
    with pytest.raises(FrozenInstanceError):
        result.status = AiFinancialRiskStatus.PARTIAL  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.items[0].title = "tampered"  # type: ignore[misc]

    ref = result.items[0].source_refs[0]
    item = AiFinancialRiskItem(
        "financial_" + "b" * 32,
        AiFinancialRiskCategory.PAYMENT_AND_CASH_FLOW,
        AiFinancialReviewPriority.ELEVATED,
        "t" * 600,
        (ref,),
        "a" * 1200,
    )
    assert len(item.title) == 500
    assert len(item.recommended_action) == 1000


def test_invalid_ids_unknown_values_and_duplicate_refs_are_rejected() -> None:
    with pytest.raises(ValueError):
        AiFinancialRiskSourceRef("requirements", "licenses", "cit_" + "a" * 32)
    with pytest.raises(ValueError):
        AiFinancialRiskSourceRef("requirements", "bid_security", "bad")
    ref = AiFinancialRiskSourceRef("requirements", "bid_security", "cit_" + "a" * 32)
    with pytest.raises(ValueError):
        AiFinancialRiskItem(
            "bad",
            AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS,
            AiFinancialReviewPriority.ELEVATED,
            "title",
            (ref,),
            "action",
        )
    with pytest.raises(ValueError):
        AiFinancialRiskItem(
            "financial_" + "b" * 32,
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
    analysis = _analysis("draft_contract", "payment_terms")
    finding = analysis.draft_contract.payment_terms[0]
    assert finding.evidence is not None
    tampered = replace(finding, evidence=replace(finding.evidence, **{attribute: value}))
    contract = replace(analysis.draft_contract, payment_terms=(tampered,))

    result = assess_financial_risks(replace(analysis, draft_contract=contract))

    assert result.status is AiFinancialRiskStatus.PARTIAL
    assert result.items == ()
    assert result.warnings


def test_missing_provenance_foreign_kind_and_duplicate_source_fail_closed() -> None:
    no_provenance = assess_financial_risks(
        replace(_analysis("draft_contract", "payment_terms"), provenance=None)
    )
    assert no_provenance.status is AiFinancialRiskStatus.UNAVAILABLE

    foreign = assess_financial_risks(
        _analysis(
            "requirements",
            "bid_security",
            source_kind=DocumentKind.DRAFT_CONTRACT,
        )
    )
    assert foreign.status is AiFinancialRiskStatus.PARTIAL
    assert foreign.items == ()

    analysis = _analysis("draft_contract", "payment_terms")
    assert analysis.provenance is not None
    duplicated = replace(
        analysis,
        provenance=replace(
            analysis.provenance,
            sources=(*analysis.provenance.sources, analysis.provenance.sources[-1]),
        ),
    )
    duplicate_result = assess_financial_risks(duplicated)
    assert duplicate_result.status is AiFinancialRiskStatus.PARTIAL
    assert duplicate_result.items == ()


def test_unverified_and_generic_findings_are_not_promoted() -> None:
    unverified = assess_financial_risks(
        _analysis("draft_contract", "payment_terms", verified=False)
    )
    assert unverified.status is AiFinancialRiskStatus.PARTIAL
    assert unverified.items == ()

    analysis = _analysis()
    generic = _analysis("draft_contract", "payment_terms").draft_contract.payment_terms[0]
    generic_result = assess_financial_risks(
        replace(
            analysis, risks=(generic,), suspicious_conditions=(generic,), contradictions=(generic,)
        )
    )
    assert generic_result.status is AiFinancialRiskStatus.NO_VERIFIED_CONDITIONS
    assert generic_result.items == ()


@pytest.mark.parametrize(
    ("changes", "expected"),
    (
        ({}, AiFinancialRiskStatus.NO_VERIFIED_CONDITIONS),
        (
            {"section": "draft_contract", "field": "payment_terms"},
            AiFinancialRiskStatus.COMPLETE,
        ),
        (
            {"requirements_status": AiApplicationRequirementsStatus.PARTIAL},
            AiFinancialRiskStatus.PARTIAL,
        ),
        ({"contract_status": AiDraftContractStatus.NOT_FOUND}, AiFinancialRiskStatus.PARTIAL),
        (
            {"technical_status": AiTechnicalSpecificationStatus.PARTIAL},
            AiFinancialRiskStatus.PARTIAL,
        ),
        ({"context_truncated": True}, AiFinancialRiskStatus.PARTIAL),
        (
            {"analysis_status": AiAnalysisStatus.PROVIDER_DISABLED},
            AiFinancialRiskStatus.UNAVAILABLE,
        ),
        ({"analysis_status": AiAnalysisStatus.PROVIDER_ERROR}, AiFinancialRiskStatus.UNAVAILABLE),
        ({"analysis_status": AiAnalysisStatus.INVALID_RESPONSE}, AiFinancialRiskStatus.UNAVAILABLE),
        ({"analysis_status": AiAnalysisStatus.NO_DOCUMENTS}, AiFinancialRiskStatus.UNAVAILABLE),
        (
            {"analysis_status": AiAnalysisStatus.CACHE_INCOMPATIBLE},
            AiFinancialRiskStatus.UNAVAILABLE,
        ),
    ),
)
def test_status_matrix(changes: dict[str, object], expected: AiFinancialRiskStatus) -> None:
    changes = dict(changes)
    section = changes.pop("section", None)
    field = changes.pop("field", None)
    result = assess_financial_risks(_analysis(section, field, **changes))  # type: ignore[arg-type]
    assert result.status is expected


def test_source_resolution_returns_only_current_policy_findings() -> None:
    analysis = _analysis("draft_contract", "payment_terms")
    result = assess_financial_risks(analysis)
    assert financial_risk_source_findings(analysis, result.items[0]) == (
        analysis.draft_contract.payment_terms[0],
    )

    stale = replace(
        analysis,
        draft_contract=replace(
            analysis.draft_contract,
            payment_terms=(replace(analysis.draft_contract.payment_terms[0], evidence=None),),
        ),
    )
    assert financial_risk_source_findings(stale, result.items[0]) == ()


def test_v8_payload_has_exact_financial_keys_and_round_trips() -> None:
    analysis = _with_assessments(_analysis("draft_contract", "payment_terms"))
    payload = analysis.to_payload()
    financial = payload["financial_risk_assessment"]
    assert set(financial) == {"status", "policy_version", "items", "warnings"}
    assert set(financial["items"][0]) == {
        "risk_id",
        "category",
        "review_priority",
        "title",
        "source_refs",
        "recommended_action",
    }
    assert set(financial["items"][0]["source_refs"][0]) == {
        "section",
        "field",
        "citation_id",
    }

    restored = AiDocumentAnalysis.from_payload(json.loads(json.dumps(payload)))

    assert restored.payload_version == AI_ANALYSIS_SCHEMA_VERSION == 9
    assert restored.financial_risk_assessment == analysis.financial_risk_assessment
    assert restored.legal_risk_assessment == analysis.legal_risk_assessment


@pytest.mark.parametrize("legacy_version", range(1, 8))
def test_legacy_payload_never_promotes_financial_assessment(legacy_version: int) -> None:
    payload = _with_assessments(_analysis("draft_contract", "payment_terms")).to_payload()
    payload["payload_version"] = legacy_version

    restored = AiDocumentAnalysis.from_payload(payload)

    assert restored.financial_risk_assessment.status is AiFinancialRiskStatus.UNAVAILABLE
    assert restored.financial_risk_assessment.items == ()


@pytest.mark.parametrize(
    ("path", "tampered"),
    (
        (("status",), "unavailable"),
        (("category",), "unknown"),
        (("review_priority",), "critical"),
        (("title",), "provider controlled"),
        (("recommended_action",), "provider controlled"),
        (("risk_id",), "financial_" + "0" * 32),
        (("source_refs", 0, "field"), "licenses"),
        (("source_refs", 0, "citation_id"), "cit_" + "0" * 32),
    ),
)
def test_tampered_current_payload_is_not_trusted(
    path: tuple[object, ...], tampered: object
) -> None:
    analysis = _with_assessments(_analysis("draft_contract", "payment_terms"))
    payload = analysis.to_payload()
    target: object = payload["financial_risk_assessment"]
    if path[0] != "status":
        target = target["items"][0]  # type: ignore[index]
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = tampered  # type: ignore[index]

    restored = AiDocumentAnalysis.from_payload(payload)

    assert restored.financial_risk_assessment.status is AiFinancialRiskStatus.PARTIAL
    assert "provider controlled" not in json.dumps(
        restored.financial_risk_assessment.to_payload(), ensure_ascii=False
    )
    assert restored.financial_risk_assessment.warnings


def test_duplicate_persisted_refs_and_future_payload_fail_closed() -> None:
    analysis = _with_assessments(_analysis("draft_contract", "payment_terms"))
    payload = analysis.to_payload()
    refs = payload["financial_risk_assessment"]["items"][0]["source_refs"]
    refs.append(dict(refs[0]))
    restored = AiDocumentAnalysis.from_payload(payload)
    assert restored.financial_risk_assessment.status is AiFinancialRiskStatus.PARTIAL

    future = analysis.to_payload()
    future["payload_version"] = AI_ANALYSIS_SCHEMA_VERSION + 1
    restored_future = AiDocumentAnalysis.from_payload(future)
    assert restored_future.status is AiAnalysisStatus.CACHE_INCOMPATIBLE
    assert restored_future.financial_risk_assessment.status is AiFinancialRiskStatus.UNAVAILABLE


def test_payload_contains_no_external_or_private_metadata() -> None:
    rendered = json.dumps(
        assess_financial_risks(_analysis("draft_contract", "payment_terms")).to_payload(),
        ensure_ascii=False,
    )
    for forbidden in ("file://", "C:\\Users", "http://", "https://", "raw_response", "prompt"):
        assert forbidden not in rendered


def test_financial_policy_has_no_io_money_parsing_or_legacy_imports() -> None:
    path = Path(__file__).parents[1] / "app" / "core" / "ai" / "financial_risk.py"
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
        "CommercialEstimator",
        "CompanyCapabilityProfile",
        "app.tender_analysis.engine",
    ):
        assert forbidden not in source


def test_commercial_estimator_remains_decimal_and_does_not_invent_values() -> None:
    result = CommercialEstimator().calculate(CommercialEstimateDraft("procurement:121"))

    assert result.status is CommercialEstimateStatus.DATA_INSUFFICIENT
    assert isinstance(result.known_cost, Decimal)
    assert result.known_cost == Decimal("0.00")
    assert result.total_cost is None
    assert result.profit is None
    assert result.margin_percent is None


def test_public_types_represent_fail_closed_result() -> None:
    result = AiFinancialRiskAssessment(
        AiFinancialRiskStatus.UNAVAILABLE,
        AI_FINANCIAL_RISK_POLICY_VERSION,
        (),
        ("Недостаточно проверяемых данных.",),
    )
    ref = AiFinancialRiskSourceRef("draft_contract", "payment_terms", "cit_" + "a" * 32)
    item = AiFinancialRiskItem(
        "financial_" + "b" * 32,
        AiFinancialRiskCategory.PAYMENT_AND_CASH_FLOW,
        AiFinancialReviewPriority.ELEVATED,
        "Оплата и денежный поток",
        (ref,),
        "Сверить условия вручную.",
    )

    assert result.to_payload()["status"] == "unavailable"
    assert item.to_payload()["source_refs"][0]["citation_id"] == ref.citation_id
