from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import inspect
import json
from pathlib import Path

import pytest

from app.core.ai.documentation_completeness import (
    AI_DOCUMENTATION_COMPLETENESS_POLICY_VERSION,
    assess_documentation_completeness,
)
from app.core.ai.output_schema import (
    AI_PROVIDER_OUTPUT_SCHEMA_VERSION,
    AI_RESPONSE_FORMAT_NAME,
    build_provider_output_json_schema,
)
from app.core.ai.prompts import AI_PROMPT_VERSION
from app.core.ai.repository import AI_ANALYZER_VERSION, context_fingerprint
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiApplicationRequirementsStatus,
    AiDocumentAnalysis,
    AiDocumentationCompletenessAssessment,
    AiDocumentationCompletenessStatus,
    AiDocumentationDocumentSnapshot,
    AiDocumentationIssue,
    AiDocumentationIssueCode,
    AiDocumentationScope,
    AiDraftContractAnalysis,
    AiDraftContractStatus,
    AiTechnicalSpecificationAnalysis,
    AiTechnicalSpecificationStatus,
    TenderRequirements,
)
from app.core.document_classification import DocumentKind
from app.tenders.participation_decision_service import _current_verified_ai_findings


def _snapshot(
    document_id: str,
    kind: DocumentKind,
    *,
    checksum: str = "a" * 64,
    origin: str = "catalog",
    download_status: str = "downloaded",
    extraction_status: str = "extracted",
    available_locally: bool = True,
    text_available: bool = True,
    included_in_context: bool = True,
    context_truncated: bool = False,
    display_name: str = "document.pdf",
) -> AiDocumentationDocumentSnapshot:
    return AiDocumentationDocumentSnapshot(
        document_id=document_id,
        display_name=display_name,
        document_kind=kind,
        origin=origin,
        download_status=download_status,
        extraction_status=extraction_status,
        checksum_sha256=checksum,
        available_locally=available_locally,
        text_available=text_available,
        included_in_context=included_in_context,
        context_truncated=context_truncated,
    )


def _complete_inventory() -> tuple[AiDocumentationDocumentSnapshot, ...]:
    return (
        _snapshot("app", DocumentKind.APPLICATION_REQUIREMENTS, checksum="a" * 64),
        _snapshot("ts", DocumentKind.TECHNICAL_SPECIFICATION, checksum="b" * 64),
    )


def _analysis(
    inventory: tuple[AiDocumentationDocumentSnapshot, ...],
    *,
    missing_documents: tuple[str, ...] = (),
    draft_contract: AiDraftContractAnalysis | None = None,
) -> AiDocumentAnalysis:
    ts_ids = tuple(
        sorted(
            item.document_id
            for item in inventory
            if item.document_kind is DocumentKind.TECHNICAL_SPECIFICATION
        )
    )
    app_ids = tuple(
        sorted(
            item.document_id
            for item in inventory
            if item.document_kind
            in {
                DocumentKind.APPLICATION_REQUIREMENTS,
                DocumentKind.APPLICATION_FORM,
                DocumentKind.INSTRUCTIONS,
                DocumentKind.PROCUREMENT_NOTICE,
            }
        )
    )
    contract_ids = tuple(
        sorted(
            item.document_id
            for item in inventory
            if item.document_kind is DocumentKind.DRAFT_CONTRACT
        )
    )
    included = {item.document_id for item in inventory if item.included_in_context}
    return AiDocumentAnalysis(
        "procurement:test",
        "Safe",
        documentation_inventory=inventory,
        requirements=TenderRequirements(
            status=(
                AiApplicationRequirementsStatus.COMPLETE
                if app_ids
                else AiApplicationRequirementsStatus.NOT_FOUND
            ),
            document_ids=app_ids,
            included_document_ids=tuple(item for item in app_ids if item in included),
        ),
        technical_specification=AiTechnicalSpecificationAnalysis(
            status=(
                AiTechnicalSpecificationStatus.COMPLETE
                if ts_ids
                else AiTechnicalSpecificationStatus.NOT_FOUND
            ),
            document_ids=ts_ids,
            included_document_ids=tuple(item for item in ts_ids if item in included),
        ),
        draft_contract=draft_contract
        or AiDraftContractAnalysis(
            status=(
                AiDraftContractStatus.COMPLETE if contract_ids else AiDraftContractStatus.NOT_FOUND
            ),
            document_ids=contract_ids,
            included_document_ids=tuple(item for item in contract_ids if item in included),
        ),
        missing_documents=missing_documents,
    )


def _codes(assessment: AiDocumentationCompletenessAssessment) -> set[AiDocumentationIssueCode]:
    return {AiDocumentationIssueCode(item.code) for item in assessment.issues}


def test_contract_values_and_versions_are_exact() -> None:
    assert {item.value for item in AiDocumentationCompletenessStatus} == {
        "complete",
        "partial",
        "no_documents",
        "unavailable",
    }
    assert {item.value for item in AiDocumentationScope} == {
        "package",
        "technical_specification",
        "application_requirements",
        "draft_contract",
        "procurement_notice",
        "estimate",
        "application_form",
        "instructions",
        "other",
    }
    assert AI_DOCUMENTATION_COMPLETENESS_POLICY_VERSION == "1"
    assert AI_ANALYSIS_SCHEMA_VERSION == 10
    assert AI_ANALYZER_VERSION == "11"
    assert AI_PROVIDER_OUTPUT_SCHEMA_VERSION == "4"
    assert AI_RESPONSE_FORMAT_NAME == "corteris_tender_analysis_v4"
    assert AI_PROMPT_VERSION == "6"


def test_schema_contracts_are_frozen_and_slotted() -> None:
    snapshot = _complete_inventory()[0]
    issue = AiDocumentationIssue(
        "documentation_" + "a" * 32,
        AiDocumentationIssueCode.EMPTY_TEXT,
        AiDocumentationScope.APPLICATION_REQUIREMENTS,
        ("app",),
        "Нет текста",
        "Повторить извлечение.",
    )
    assessment = AiDocumentationCompletenessAssessment(issues=(issue,))

    for value, field_name in (
        (snapshot, "display_name"),
        (issue, "title"),
        (assessment, "policy_version"),
    ):
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(value, field_name, "changed")


def test_empty_inventory_is_no_documents() -> None:
    assessment = assess_documentation_completeness(_analysis(()))
    assert assessment.status is AiDocumentationCompletenessStatus.NO_DOCUMENTS
    assert assessment.known_document_count == 0
    assert assessment.issues == ()


def test_fully_processed_required_scopes_are_complete() -> None:
    assessment = assess_documentation_completeness(_analysis(_complete_inventory()))
    assert assessment.status is AiDocumentationCompletenessStatus.COMPLETE
    assert (
        assessment.known_document_count,
        assessment.locally_available_count,
        assessment.text_available_count,
        assessment.included_document_count,
    ) == (2, 2, 2, 2)
    assert assessment.issues == ()


@pytest.mark.parametrize(
    ("changes", "expected_code"),
    [
        (
            {
                "download_status": "failed",
                "available_locally": False,
                "extraction_status": "not_recorded",
                "text_available": False,
                "included_in_context": False,
            },
            AiDocumentationIssueCode.DOWNLOAD_FAILED,
        ),
        (
            {
                "extraction_status": "failed",
                "text_available": False,
                "included_in_context": False,
            },
            AiDocumentationIssueCode.EXTRACTION_FAILED,
        ),
        (
            {
                "extraction_status": "unsupported",
                "text_available": False,
                "included_in_context": False,
            },
            AiDocumentationIssueCode.UNSUPPORTED_FORMAT,
        ),
        (
            {"extraction_status": "partial"},
            AiDocumentationIssueCode.EXTRACTION_PARTIAL,
        ),
        (
            {"text_available": False, "included_in_context": False},
            AiDocumentationIssueCode.EMPTY_TEXT,
        ),
        (
            {"context_truncated": True},
            AiDocumentationIssueCode.CONTEXT_TRUNCATED,
        ),
        (
            {"included_in_context": False},
            AiDocumentationIssueCode.CONTEXT_OMITTED,
        ),
    ],
)
def test_locally_verified_failures_are_partial(
    changes: dict[str, object],
    expected_code: AiDocumentationIssueCode,
) -> None:
    inventory = list(_complete_inventory())
    inventory[1] = replace(inventory[1], **changes)
    assessment = assess_documentation_completeness(_analysis(tuple(inventory)))
    assert assessment.status is AiDocumentationCompletenessStatus.PARTIAL
    assert expected_code in _codes(assessment)


@pytest.mark.parametrize(
    ("removed_kind", "scope"),
    [
        (DocumentKind.TECHNICAL_SPECIFICATION, AiDocumentationScope.TECHNICAL_SPECIFICATION),
        (DocumentKind.APPLICATION_REQUIREMENTS, AiDocumentationScope.APPLICATION_REQUIREMENTS),
    ],
)
def test_missing_required_analysis_scope_is_partial_without_legal_claim(
    removed_kind: DocumentKind,
    scope: AiDocumentationScope,
) -> None:
    inventory = tuple(
        item for item in _complete_inventory() if item.document_kind is not removed_kind
    )
    assessment = assess_documentation_completeness(_analysis(inventory))
    issues = [
        item
        for item in assessment.issues
        if item.code is AiDocumentationIssueCode.REQUIRED_ANALYSIS_SCOPE_NOT_FOUND
    ]
    assert assessment.status is AiDocumentationCompletenessStatus.PARTIAL
    assert any(item.scope is scope for item in issues)
    assert all("наруш" not in item.title.casefold() for item in issues)


def test_absent_contract_does_not_create_missing_document_claim() -> None:
    assessment = assess_documentation_completeness(_analysis(_complete_inventory()))
    assert assessment.status is AiDocumentationCompletenessStatus.COMPLETE
    assert all(item.scope is not AiDocumentationScope.DRAFT_CONTRACT for item in assessment.issues)


def test_present_incomplete_contract_is_partial() -> None:
    contract = _snapshot(
        "contract",
        DocumentKind.DRAFT_CONTRACT,
        checksum="c" * 64,
        extraction_status="partial",
    )
    inventory = (*_complete_inventory(), contract)
    assessment = assess_documentation_completeness(_analysis(inventory))
    assert assessment.status is AiDocumentationCompletenessStatus.PARTIAL
    assert AiDocumentationIssueCode.EXTRACTION_PARTIAL in _codes(assessment)


def test_duplicate_and_unclassified_documents_are_informational() -> None:
    inventory = (
        *_complete_inventory(),
        _snapshot(
            "duplicate",
            DocumentKind.OTHER,
            checksum="a" * 64,
            included_in_context=False,
            display_name="other.bin",
        ),
    )
    assessment = assess_documentation_completeness(_analysis(inventory))
    assert assessment.status is AiDocumentationCompletenessStatus.COMPLETE
    assert AiDocumentationIssueCode.DUPLICATE_CONTENT in _codes(assessment)
    assert AiDocumentationIssueCode.UNCLASSIFIED_DOCUMENT in _codes(assessment)
    assert AiDocumentationIssueCode.CONTEXT_OMITTED not in _codes(assessment)


def test_provider_missing_documents_never_controls_local_assessment() -> None:
    baseline = assess_documentation_completeness(_analysis(_complete_inventory()))
    injected = assess_documentation_completeness(
        _analysis(_complete_inventory(), missing_documents=("Injected provider claim",))
    )
    assert injected == baseline


def test_issue_ids_and_order_are_stable_across_input_permutations() -> None:
    inventory = (
        replace(_complete_inventory()[0], extraction_status="partial"),
        replace(_complete_inventory()[1], context_truncated=True),
    )
    first = assess_documentation_completeness(_analysis(inventory))
    second = assess_documentation_completeness(_analysis(tuple(reversed(inventory))))
    assert first == second
    assert all(item.issue_id.startswith("documentation_") for item in first.issues)
    assert all(len(item.issue_id) == 46 for item in first.issues)
    assert len({item.issue_id for item in first.issues}) == len(first.issues)


def test_inventory_mismatch_is_fail_closed() -> None:
    analysis = replace(
        _analysis(_complete_inventory()),
        technical_specification=AiTechnicalSpecificationAnalysis(
            status=AiTechnicalSpecificationStatus.COMPLETE,
            document_ids=("foreign",),
            included_document_ids=("foreign",),
        ),
    )
    assessment = assess_documentation_completeness(analysis)
    assert assessment.status is AiDocumentationCompletenessStatus.PARTIAL
    assert AiDocumentationIssueCode.INVENTORY_MISMATCH in _codes(assessment)


def test_payload_has_exact_documentation_keys_and_round_trips() -> None:
    analysis = _analysis(_complete_inventory())
    assessment = assess_documentation_completeness(analysis)
    analysis = replace(analysis, documentation_completeness_assessment=assessment)
    payload = analysis.to_payload()

    assert set(payload["documentation_inventory"][0]) == {
        "document_id",
        "display_name",
        "document_kind",
        "origin",
        "download_status",
        "extraction_status",
        "checksum_sha256",
        "available_locally",
        "text_available",
        "included_in_context",
        "context_truncated",
    }
    assert set(payload["documentation_completeness_assessment"]) == {
        "status",
        "policy_version",
        "known_document_count",
        "locally_available_count",
        "text_available_count",
        "included_document_count",
        "issues",
        "warnings",
    }
    restored = AiDocumentAnalysis.from_payload(json.loads(json.dumps(payload)))
    assert restored.documentation_inventory == analysis.documentation_inventory
    assert restored.documentation_completeness_assessment == assessment


def test_tampered_current_assessment_is_recomputed_partial() -> None:
    analysis = _analysis(_complete_inventory())
    analysis = replace(
        analysis,
        documentation_completeness_assessment=assess_documentation_completeness(analysis),
    )
    payload = analysis.to_payload()
    payload["documentation_completeness_assessment"]["known_document_count"] = 999
    restored = AiDocumentAnalysis.from_payload(payload)
    assert restored.documentation_completeness_assessment.known_document_count == 2
    assert (
        restored.documentation_completeness_assessment.status
        is AiDocumentationCompletenessStatus.PARTIAL
    )
    assert restored.documentation_completeness_assessment.warnings


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("status",), "no_documents"),
        (("included_document_count",), 0),
        (("issues",), [{"issue_id": "documentation_" + "0" * 32}]),
    ],
)
def test_tampered_current_assessment_fields_are_never_trusted(
    path: tuple[str, ...], value: object
) -> None:
    analysis = _analysis(_complete_inventory())
    analysis = replace(
        analysis,
        documentation_completeness_assessment=assess_documentation_completeness(analysis),
    )
    payload = analysis.to_payload()
    payload["documentation_completeness_assessment"][path[0]] = value

    restored = AiDocumentAnalysis.from_payload(payload)

    assert (
        restored.documentation_completeness_assessment.status
        is AiDocumentationCompletenessStatus.PARTIAL
    )
    assert restored.documentation_completeness_assessment.warnings


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("document_id", "foreign"),
        ("document_kind", "draft_contract"),
        ("download_status", "failed"),
        ("extraction_status", "unsupported"),
    ],
)
def test_tampered_current_inventory_is_validated_and_recomputed(field: str, value: object) -> None:
    analysis = _analysis(_complete_inventory())
    analysis = replace(
        analysis,
        documentation_completeness_assessment=assess_documentation_completeness(analysis),
    )
    payload = analysis.to_payload()
    payload["documentation_inventory"][0][field] = value

    restored = AiDocumentAnalysis.from_payload(payload)

    assert (
        restored.documentation_completeness_assessment.status
        is not AiDocumentationCompletenessStatus.COMPLETE
    )


def test_legacy_payload_has_unavailable_empty_assessment() -> None:
    payload = _analysis(_complete_inventory()).to_payload()
    payload["payload_version"] = 9
    payload.pop("documentation_inventory")
    payload.pop("documentation_completeness_assessment")
    restored = AiDocumentAnalysis.from_payload(payload)
    assert restored.documentation_inventory == ()
    assert (
        restored.documentation_completeness_assessment.status
        is AiDocumentationCompletenessStatus.UNAVAILABLE
    )


def test_inventory_changes_fingerprint_and_order_does_not() -> None:
    inventory = _complete_inventory()
    parameters = {"documentation_inventory": [item.to_payload() for item in inventory]}
    first = context_fingerprint((), context_parameters=parameters)
    reordered = context_fingerprint(
        (),
        context_parameters={
            "documentation_inventory": [item.to_payload() for item in reversed(inventory)]
        },
    )
    changed = context_fingerprint(
        (),
        context_parameters={
            "documentation_inventory": [
                replace(inventory[0], extraction_status="partial").to_payload(),
                inventory[1].to_payload(),
            ]
        },
    )
    assert first == reordered
    assert changed != first


@pytest.mark.parametrize(
    "changes",
    [
        {"checksum_sha256": "f" * 64},
        {"document_kind": DocumentKind.DRAFT_CONTRACT},
        {"download_status": "failed", "available_locally": False},
        {"extraction_status": "partial"},
        {"included_in_context": False},
        {"context_truncated": True},
    ],
)
def test_every_inventory_decision_field_changes_fingerprint(changes: dict[str, object]) -> None:
    inventory = _complete_inventory()
    baseline = context_fingerprint(
        (),
        context_parameters={"documentation_inventory": [item.to_payload() for item in inventory]},
    )
    changed = (replace(inventory[0], **changes), inventory[1])

    assert (
        context_fingerprint(
            (),
            context_parameters={"documentation_inventory": [item.to_payload() for item in changed]},
        )
        != baseline
    )


def test_provider_contract_and_rm107_verified_findings_ignore_documentation_section() -> None:
    schema = build_provider_output_json_schema()
    rendered = json.dumps(schema, sort_keys=True)
    assert "documentation_inventory" not in rendered
    assert "documentation_completeness" not in rendered

    analysis = _analysis(_complete_inventory())
    analysis = replace(
        analysis,
        documentation_completeness_assessment=assess_documentation_completeness(analysis),
    )
    assert _current_verified_ai_findings(analysis) == ()


def test_pure_policy_has_no_forbidden_dependencies_or_calls() -> None:
    source = inspect.getsource(inspect.getmodule(assess_documentation_completeness))
    forbidden = (
        "requests",
        "httpx",
        "sqlite3",
        "pathlib",
        "open(",
        "provider",
        "repository",
        "raw_metadata",
        "AnalysisEngine",
        "company_profile",
        "Decimal",
        "float(",
        "import re",
        "re.search",
        "re.match",
    )
    assert not any(item in source for item in forbidden)


def test_architecture_keeps_single_graph_and_running_ai_stage() -> None:
    root = Path(__file__).resolve().parents[1]
    analyzer = (root / "app/core/ai/analyzer.py").read_text(encoding="utf-8")
    orchestrator = (root / "app/core/ai/orchestrator.py").read_text(encoding="utf-8")
    repository = (root / "app/core/ai/repository.py").read_text(encoding="utf-8")
    full_analysis = (root / "app/tenders/full_analysis.py").read_text(encoding="utf-8")
    classifier = (root / "app/core/document_classification.py").read_text(encoding="utf-8")

    assert analyzer.count("self.provider.analyze(") == 1
    assert orchestrator.count("class TenderAiOrchestrator:") == 1
    assert repository.count("class AiDocumentAnalysisRepository:") == 1
    assert full_analysis.count('RUNNING_AI = "running_ai"') == 1
    assert full_analysis.count("FullAnalysisStage.RUNNING_AI") == 1
    assert classifier.count("def classify_document_kind(") == 1
