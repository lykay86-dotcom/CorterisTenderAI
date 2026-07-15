from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import re

import pytest

from app.core.ai.citations import resolve_citation
from app.core.ai.competition_review import assess_competition_conditions
from app.core.ai.financial_risk import assess_financial_risks
from app.core.ai.legal_risk import (
    AI_LEGAL_RISK_POLICY_VERSION,
    LEGAL_RISK_CATEGORY_PRIORITIES,
    LEGAL_RISK_SOURCE_POLICY,
    assess_legal_risks,
)
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiAnalysisProvenance,
    AiAnalysisStatus,
    AiApplicationRequirementsStatus,
    AiDocument,
    AiDocumentAnalysis,
    AiDraftContractAnalysis,
    AiDraftContractStatus,
    AiFinding,
    AiFindingStatus,
    AiLegalReviewPriority,
    AiLegalRiskAssessment,
    AiLegalRiskCategory,
    AiLegalRiskItem,
    AiLegalRiskSourceRef,
    AiLegalRiskStatus,
    AiSourceSnapshot,
    AiTechnicalSpecificationAnalysis,
    AiTechnicalSpecificationStatus,
    TenderRequirements,
)
from app.core.document_classification import DocumentKind


EXPECTED_SOURCE_POLICY = {
    ("requirements", "application_composition"): (
        AiLegalRiskCategory.APPLICATION_COMPOSITION_AND_DECLARATIONS
    ),
    ("requirements", "declarations_and_consents"): (
        AiLegalRiskCategory.APPLICATION_COMPOSITION_AND_DECLARATIONS
    ),
    ("requirements", "deadlines"): (AiLegalRiskCategory.APPLICATION_COMPOSITION_AND_DECLARATIONS),
    ("requirements", "submission_format_and_signature"): (
        AiLegalRiskCategory.SUBMISSION_FORMAT_AND_SIGNATURE
    ),
    ("requirements", "grounds_for_rejection"): AiLegalRiskCategory.GROUNDS_FOR_REJECTION,
    ("requirements", "participant_eligibility"): (
        AiLegalRiskCategory.ELIGIBILITY_AND_AUTHORIZATIONS
    ),
    ("requirements", "licenses"): AiLegalRiskCategory.ELIGIBILITY_AND_AUTHORIZATIONS,
    ("requirements", "certificates"): AiLegalRiskCategory.ELIGIBILITY_AND_AUTHORIZATIONS,
    ("requirements", "national_regime_and_origin"): (
        AiLegalRiskCategory.NATIONAL_REGIME_AND_ORIGIN
    ),
    ("requirements", "bid_security"): AiLegalRiskCategory.SECURITY_AND_GUARANTEES,
    ("requirements", "contract_security"): AiLegalRiskCategory.SECURITY_AND_GUARANTEES,
    ("requirements", "bank_guarantee"): AiLegalRiskCategory.SECURITY_AND_GUARANTEES,
    ("requirements", "ambiguities"): AiLegalRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS,
    ("requirements", "clarification_points"): (AiLegalRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS),
    ("requirements", "contradictions"): AiLegalRiskCategory.CONTRADICTIONS,
    ("draft_contract", "subject_and_scope"): (AiLegalRiskCategory.SCOPE_AND_CUSTOMER_DEPENDENCIES),
    ("draft_contract", "term_schedule_and_location"): (
        AiLegalRiskCategory.SCOPE_AND_CUSTOMER_DEPENDENCIES
    ),
    ("draft_contract", "customer_obligations_and_dependencies"): (
        AiLegalRiskCategory.SCOPE_AND_CUSTOMER_DEPENDENCIES
    ),
    ("draft_contract", "price_and_price_change"): (
        AiLegalRiskCategory.PRICE_PAYMENT_AND_CHANGE_MECHANISM
    ),
    ("draft_contract", "payment_terms"): (AiLegalRiskCategory.PRICE_PAYMENT_AND_CHANGE_MECHANISM),
    ("draft_contract", "acceptance_and_closing_documents"): (
        AiLegalRiskCategory.ACCEPTANCE_AND_CLOSING
    ),
    ("draft_contract", "performance_security"): (AiLegalRiskCategory.SECURITY_AND_GUARANTEES),
    ("draft_contract", "warranty_and_defect_remediation"): (
        AiLegalRiskCategory.WARRANTY_AND_REMEDIES
    ),
    ("draft_contract", "contractor_obligations_and_subcontracting"): (
        AiLegalRiskCategory.SUBCONTRACTING_AND_THIRD_PARTIES
    ),
    ("draft_contract", "liability_penalties_and_damages"): (
        AiLegalRiskCategory.LIABILITY_PENALTIES_AND_DAMAGES
    ),
    ("draft_contract", "change_suspension_and_termination"): (
        AiLegalRiskCategory.CHANGE_SUSPENSION_AND_TERMINATION
    ),
    ("draft_contract", "force_majeure_and_notifications"): (
        AiLegalRiskCategory.FORCE_MAJEURE_AND_NOTICES
    ),
    ("draft_contract", "dispute_confidentiality_and_ip"): (
        AiLegalRiskCategory.DISPUTES_CONFIDENTIALITY_AND_IP
    ),
    ("draft_contract", "ambiguities"): AiLegalRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS,
    ("draft_contract", "clarification_points"): (
        AiLegalRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("draft_contract", "contradictions"): AiLegalRiskCategory.CONTRADICTIONS,
    ("technical_specification", "standards_and_regulations"): (
        AiLegalRiskCategory.STANDARDS_AND_REGULATIONS
    ),
    ("technical_specification", "acceptance_and_quality"): (
        AiLegalRiskCategory.ACCEPTANCE_AND_CLOSING
    ),
    ("technical_specification", "customer_inputs_and_dependencies"): (
        AiLegalRiskCategory.SCOPE_AND_CUSTOMER_DEPENDENCIES
    ),
    ("technical_specification", "ambiguities"): (
        AiLegalRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("technical_specification", "clarification_points"): (
        AiLegalRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("technical_specification", "contradictions"): AiLegalRiskCategory.CONTRADICTIONS,
}

EXPECTED_PRIORITIES = {
    category: (
        AiLegalReviewPriority.URGENT
        if category
        in {
            AiLegalRiskCategory.GROUNDS_FOR_REJECTION,
            AiLegalRiskCategory.CONTRADICTIONS,
        }
        else AiLegalReviewPriority.ELEVATED
        if category
        in {
            AiLegalRiskCategory.SUBMISSION_FORMAT_AND_SIGNATURE,
            AiLegalRiskCategory.ELIGIBILITY_AND_AUTHORIZATIONS,
            AiLegalRiskCategory.NATIONAL_REGIME_AND_ORIGIN,
            AiLegalRiskCategory.SECURITY_AND_GUARANTEES,
            AiLegalRiskCategory.PRICE_PAYMENT_AND_CHANGE_MECHANISM,
            AiLegalRiskCategory.LIABILITY_PENALTIES_AND_DAMAGES,
            AiLegalRiskCategory.CHANGE_SUSPENSION_AND_TERMINATION,
            AiLegalRiskCategory.SUBCONTRACTING_AND_THIRD_PARTIES,
            AiLegalRiskCategory.DISPUTES_CONFIDENTIALITY_AND_IP,
        }
        else AiLegalReviewPriority.ROUTINE
    )
    for category in AiLegalRiskCategory
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
    quotes: tuple[str, ...] = ("exact legal condition",),
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
    fingerprint = "d" * 64
    documents: dict[str, AiDocument] = {}
    sources: list[AiSourceSnapshot] = []
    for current_section, kind in _SECTION_KIND.items():
        current_kind = source_kind if current_section == section and source_kind else kind
        text = " | ".join(quotes) if current_section == section else f"{current_section} context"
        document_id = f"{current_section}-doc"
        checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
        document = AiDocument(
            document_id=document_id,
            name=f"{current_section}.pdf",
            source="local_document_store",
            document_type="pdf",
            received_at="2026-07-15T10:00:00+00:00",
            verification_status="verified",
            text=text,
            checksum_sha256=checksum,
            original_character_count=len(text),
            document_kind=current_kind.value,
        )
        documents[current_section] = document
        sources.append(
            AiSourceSnapshot(
                document_id=document_id,
                display_name=f"{current_section}.pdf",
                document_type="pdf",
                checksum_sha256=checksum,
                verification_status="verified",
                received_at="2026-07-15T10:00:00+00:00",
                truncated=False,
                included_character_count=len(text),
                original_character_count=len(text),
                document_kind=current_kind.value,
            )
        )

    findings: tuple[AiFinding, ...] = ()
    if section is not None and field is not None:
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
        analysis_id="analysis_120",
        context_fingerprint=fingerprint,
        created_at="2026-07-15T10:01:00+00:00",
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
        "procurement:120",
        "Safe summary",
        status=analysis_status,
        provenance=provenance,
        requirements=requirements,
        technical_specification=technical,
        draft_contract=contract,
        context_truncated=context_truncated,
    )


def _with_assessment(analysis: AiDocumentAnalysis) -> AiDocumentAnalysis:
    analysis = replace(analysis, legal_risk_assessment=assess_legal_risks(analysis))
    analysis = replace(analysis, financial_risk_assessment=assess_financial_risks(analysis))
    return replace(analysis, competition_assessment=assess_competition_conditions(analysis))


def test_policy_contract_is_exact_and_versioned() -> None:
    assert AI_LEGAL_RISK_POLICY_VERSION == "1"
    assert LEGAL_RISK_SOURCE_POLICY == EXPECTED_SOURCE_POLICY
    assert LEGAL_RISK_CATEGORY_PRIORITIES == EXPECTED_PRIORITIES
    assert "critical" not in {item.value for item in AiLegalReviewPriority}


@pytest.mark.parametrize(
    ("source", "category"),
    tuple(EXPECTED_SOURCE_POLICY.items()),
)
def test_every_allowed_source_field_maps_to_exact_category_and_priority(
    source: tuple[str, str], category: AiLegalRiskCategory
) -> None:
    section, field = source
    assessment = assess_legal_risks(_analysis(section, field))

    assert assessment.status is AiLegalRiskStatus.COMPLETE
    assert len(assessment.items) == 1
    assert assessment.items[0].category is category
    assert assessment.items[0].review_priority is EXPECTED_PRIORITIES[category]
    assert assessment.items[0].source_refs[0].section == section
    assert assessment.items[0].source_refs[0].field == field


@pytest.mark.parametrize(
    "statement",
    (
        "critical urgent illegal reject immediately",
        "routine harmless ordinary",
        "<script>alert('priority')</script>",
    ),
)
def test_provider_text_cannot_change_priority_title_or_action(statement: str) -> None:
    assessment = assess_legal_risks(
        _analysis("requirements", "application_composition", statement=statement)
    )
    item = assessment.items[0]

    assert item.review_priority is AiLegalReviewPriority.ROUTINE
    assert item.title != statement
    assert item.recommended_action != statement
    assert "<script>" not in item.title
    assert "<script>" not in item.recommended_action


def test_risk_id_and_deduplication_are_stable_across_input_order() -> None:
    analysis = _analysis("requirements", "licenses")
    finding = analysis.requirements.licenses[0]
    first = replace(analysis.requirements, licenses=(finding, finding))
    second = replace(analysis.requirements, licenses=(finding, finding)[::-1])

    left = assess_legal_risks(replace(analysis, requirements=first))
    right = assess_legal_risks(replace(analysis, requirements=second))

    assert left == right
    assert len(left.items) == 1
    assert re.fullmatch(r"legal_[0-9a-f]{32}", left.items[0].risk_id)
    assert len(left.items[0].source_refs) == 1


def test_same_citation_across_fields_merges_but_other_citation_stays_separate() -> None:
    analysis = _analysis("requirements", "licenses", quotes=("license one", "license two"))
    first, second = analysis.requirements.licenses
    requirements = replace(
        analysis.requirements,
        licenses=(first, second),
        certificates=(first,),
    )

    assessment = assess_legal_risks(replace(analysis, requirements=requirements))

    assert len(assessment.items) == 2
    first_item = next(
        item
        for item in assessment.items
        if item.source_refs[0].citation_id == first.evidence.citation_id
    )
    assert {(ref.section, ref.field) for ref in first_item.source_refs} == {
        ("requirements", "licenses"),
        ("requirements", "certificates"),
    }


def test_domain_objects_are_immutable() -> None:
    assessment = assess_legal_risks(_analysis("requirements", "licenses"))

    with pytest.raises(FrozenInstanceError):
        assessment.status = AiLegalRiskStatus.PARTIAL  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        assessment.items[0].title = "tampered"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("attribute", "value"),
    (
        ("checksum_sha256", "0" * 64),
        ("context_fingerprint", "0" * 64),
        ("citation_id", "cit_" + "0" * 32),
    ),
)
def test_tampered_evidence_is_rejected_fail_closed(attribute: str, value: str) -> None:
    analysis = _analysis("requirements", "licenses")
    finding = analysis.requirements.licenses[0]
    assert finding.evidence is not None
    tampered = replace(finding, evidence=replace(finding.evidence, **{attribute: value}))
    requirements = replace(analysis.requirements, licenses=(tampered,))

    assessment = assess_legal_risks(replace(analysis, requirements=requirements))

    assert assessment.status is AiLegalRiskStatus.PARTIAL
    assert assessment.items == ()
    assert assessment.warnings


def test_missing_provenance_is_unavailable() -> None:
    assessment = assess_legal_risks(replace(_analysis("requirements", "licenses"), provenance=None))

    assert assessment.status is AiLegalRiskStatus.UNAVAILABLE
    assert assessment.items == ()


def test_foreign_document_kind_is_rejected() -> None:
    assessment = assess_legal_risks(
        _analysis(
            "requirements",
            "licenses",
            source_kind=DocumentKind.DRAFT_CONTRACT,
        )
    )

    assert assessment.status is AiLegalRiskStatus.PARTIAL
    assert assessment.items == ()


def test_unverified_specialized_finding_does_not_create_item() -> None:
    assessment = assess_legal_risks(
        _analysis("draft_contract", "liability_penalties_and_damages", verified=False)
    )

    assert assessment.status is AiLegalRiskStatus.PARTIAL
    assert assessment.items == ()


def test_generic_findings_are_not_copied_to_legal_registry() -> None:
    analysis = _analysis()
    generic = _analysis("requirements", "licenses").requirements.licenses[0]

    assessment = assess_legal_risks(replace(analysis, risks=(generic,)))

    assert assessment.status is AiLegalRiskStatus.NO_VERIFIED_RISKS
    assert assessment.items == ()


@pytest.mark.parametrize(
    ("changes", "expected"),
    (
        ({}, AiLegalRiskStatus.NO_VERIFIED_RISKS),
        ({"section": "requirements", "field": "licenses"}, AiLegalRiskStatus.COMPLETE),
        (
            {"requirements_status": AiApplicationRequirementsStatus.PARTIAL},
            AiLegalRiskStatus.PARTIAL,
        ),
        (
            {"requirements_status": AiApplicationRequirementsStatus.NOT_FOUND},
            AiLegalRiskStatus.PARTIAL,
        ),
        (
            {"contract_status": AiDraftContractStatus.NOT_FOUND},
            AiLegalRiskStatus.PARTIAL,
        ),
        (
            {"technical_status": AiTechnicalSpecificationStatus.PARTIAL},
            AiLegalRiskStatus.PARTIAL,
        ),
        ({"context_truncated": True}, AiLegalRiskStatus.PARTIAL),
        (
            {"analysis_status": AiAnalysisStatus.PROVIDER_DISABLED},
            AiLegalRiskStatus.UNAVAILABLE,
        ),
        (
            {"analysis_status": AiAnalysisStatus.PROVIDER_ERROR},
            AiLegalRiskStatus.UNAVAILABLE,
        ),
        (
            {"analysis_status": AiAnalysisStatus.INVALID_RESPONSE},
            AiLegalRiskStatus.UNAVAILABLE,
        ),
        (
            {"analysis_status": AiAnalysisStatus.NO_DOCUMENTS},
            AiLegalRiskStatus.UNAVAILABLE,
        ),
    ),
)
def test_status_matrix(changes: dict[str, object], expected: AiLegalRiskStatus) -> None:
    section = changes.pop("section", None)
    field = changes.pop("field", None)
    assessment = assess_legal_risks(_analysis(section, field, **changes))  # type: ignore[arg-type]

    assert assessment.status is expected


def test_v7_payload_has_exact_legal_keys_and_round_trips() -> None:
    analysis = _with_assessment(_analysis("requirements", "licenses"))
    payload = analysis.to_payload()
    legal = payload["legal_risk_assessment"]
    assert isinstance(legal, dict)
    assert set(legal) == {"status", "policy_version", "items", "warnings"}
    item = legal["items"][0]
    assert set(item) == {
        "risk_id",
        "category",
        "review_priority",
        "title",
        "source_refs",
        "recommended_action",
    }
    assert set(item["source_refs"][0]) == {"section", "field", "citation_id"}

    restored = AiDocumentAnalysis.from_payload(json.loads(json.dumps(payload)))

    assert restored.payload_version == AI_ANALYSIS_SCHEMA_VERSION == 9
    assert restored.legal_risk_assessment == analysis.legal_risk_assessment


@pytest.mark.parametrize("legacy_version", range(1, 8))
def test_legacy_payload_never_promotes_legal_assessment(legacy_version: int) -> None:
    payload = _with_assessment(_analysis("requirements", "licenses")).to_payload()
    payload["payload_version"] = legacy_version

    restored = AiDocumentAnalysis.from_payload(payload)

    assert restored.legal_risk_assessment.status is AiLegalRiskStatus.UNAVAILABLE
    assert restored.legal_risk_assessment.items == ()


@pytest.mark.parametrize(
    ("path", "tampered"),
    (
        (("category",), "unknown"),
        (("review_priority",), "critical"),
        (("title",), "provider controlled"),
        (("recommended_action",), "provider controlled"),
        (("risk_id",), "legal_" + "0" * 32),
        (("source_refs", 0, "field"), "unknown_field"),
        (("source_refs", 0, "citation_id"), "cit_" + "0" * 32),
    ),
)
def test_tampered_current_legal_payload_is_not_trusted(
    path: tuple[object, ...], tampered: object
) -> None:
    analysis = _with_assessment(_analysis("requirements", "licenses"))
    payload = analysis.to_payload()
    target: object = payload["legal_risk_assessment"]["items"][0]
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = tampered  # type: ignore[index]

    restored = AiDocumentAnalysis.from_payload(payload)

    assert restored.legal_risk_assessment.status is AiLegalRiskStatus.PARTIAL
    assert "provider controlled" not in json.dumps(
        restored.legal_risk_assessment.to_payload(), ensure_ascii=False
    )
    assert restored.legal_risk_assessment.warnings


def test_duplicate_source_refs_in_payload_are_rejected() -> None:
    analysis = _with_assessment(_analysis("requirements", "licenses"))
    payload = analysis.to_payload()
    refs = payload["legal_risk_assessment"]["items"][0]["source_refs"]
    refs.append(dict(refs[0]))

    restored = AiDocumentAnalysis.from_payload(payload)

    assert restored.legal_risk_assessment.status is AiLegalRiskStatus.PARTIAL


def test_future_payload_is_incompatible_and_legal_assessment_unavailable() -> None:
    payload = _with_assessment(_analysis("requirements", "licenses")).to_payload()
    payload["payload_version"] = AI_ANALYSIS_SCHEMA_VERSION + 1

    restored = AiDocumentAnalysis.from_payload(payload)

    assert restored.status is AiAnalysisStatus.CACHE_INCOMPATIBLE
    assert restored.legal_risk_assessment.status is AiLegalRiskStatus.UNAVAILABLE


def test_source_ref_and_item_payloads_never_contain_external_metadata() -> None:
    assessment = assess_legal_risks(_analysis("requirements", "licenses"))
    rendered = json.dumps(assessment.to_payload(), ensure_ascii=False)

    assert "file://" not in rendered
    assert "C:\\Users" not in rendered
    assert "provider" not in rendered.casefold()
    assert "http://" not in rendered
    assert "https://" not in rendered


def test_public_domain_types_can_represent_fail_closed_result() -> None:
    result = AiLegalRiskAssessment(
        status=AiLegalRiskStatus.UNAVAILABLE,
        policy_version=AI_LEGAL_RISK_POLICY_VERSION,
        items=(),
        warnings=("Недостаточно проверяемых данных.",),
    )
    ref = AiLegalRiskSourceRef("requirements", "licenses", "cit_" + "a" * 32)
    item = AiLegalRiskItem(
        risk_id="legal_" + "b" * 32,
        category=AiLegalRiskCategory.ELIGIBILITY_AND_AUTHORIZATIONS,
        review_priority=AiLegalReviewPriority.ELEVATED,
        title="Проверка разрешений и допуска",
        source_refs=(ref,),
        recommended_action="Проверить применимость требования.",
    )

    assert result.to_payload()["status"] == "unavailable"
    assert item.to_payload()["source_refs"][0]["citation_id"] == ref.citation_id
