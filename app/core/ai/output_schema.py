"""Canonical strict raw-output contract for Tender Intelligence providers."""

from __future__ import annotations

import json
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


AI_PROVIDER_OUTPUT_SCHEMA_VERSION = "3"
AI_RESPONSE_FORMAT_NAME = "corteris_tender_analysis_v3"

MAX_SUMMARY_LENGTH = 12_000
MAX_STATEMENT_LENGTH = 4_000
MAX_DOCUMENT_ID_LENGTH = 500
MAX_QUOTE_LENGTH = 8_000
MAX_SECTION_LENGTH = 1_000
MAX_MISSING_DOCUMENT_LENGTH = 1_000
MAX_FINDINGS_PER_BUCKET = 200
MAX_MISSING_DOCUMENTS = 200

SummaryText = Annotated[str, Field(strict=True, max_length=MAX_SUMMARY_LENGTH)]
StatementText = Annotated[str, Field(strict=True, max_length=MAX_STATEMENT_LENGTH)]
DocumentIdText = Annotated[str, Field(strict=True, max_length=MAX_DOCUMENT_ID_LENGTH)]
QuoteText = Annotated[str, Field(strict=True, max_length=MAX_QUOTE_LENGTH)]
SectionText = Annotated[str, Field(strict=True, max_length=MAX_SECTION_LENGTH)]
MissingDocumentText = Annotated[
    str,
    Field(strict=True, max_length=MAX_MISSING_DOCUMENT_LENGTH),
]
PageNumber = Annotated[int, Field(strict=True, ge=1)]
ConfidenceNumber = Annotated[
    float,
    Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False),
]


class _StrictProviderModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class ProviderFindingPayload(_StrictProviderModel):
    statement: StatementText
    document_id: DocumentIdText
    quote: QuoteText
    section: SectionText
    page: PageNumber | None
    confidence: ConfidenceNumber


FindingList = Annotated[list[ProviderFindingPayload], Field(max_length=MAX_FINDINGS_PER_BUCKET)]


class ProviderRequirementsPayload(_StrictProviderModel):
    equipment: FindingList
    certificates: FindingList
    licenses: FindingList
    specialists: FindingList
    documents: FindingList
    experience: FindingList
    deadlines: FindingList
    warranty: FindingList
    bid_security: FindingList
    contract_security: FindingList
    bank_guarantee: FindingList


class ProviderTechnicalSpecificationPayload(_StrictProviderModel):
    scope: FindingList
    deliverables: FindingList
    quantities_and_volumes: FindingList
    technical_characteristics: FindingList
    materials_and_equipment: FindingList
    standards_and_regulations: FindingList
    execution_conditions: FindingList
    stages_and_deadlines: FindingList
    acceptance_and_quality: FindingList
    customer_inputs_and_dependencies: FindingList
    ambiguities: FindingList
    contradictions: FindingList
    clarification_points: FindingList


class ProviderDraftContractPayload(_StrictProviderModel):
    subject_and_scope: FindingList
    term_schedule_and_location: FindingList
    price_and_price_change: FindingList
    payment_terms: FindingList
    acceptance_and_closing_documents: FindingList
    performance_security: FindingList
    warranty_and_defect_remediation: FindingList
    customer_obligations_and_dependencies: FindingList
    contractor_obligations_and_subcontracting: FindingList
    liability_penalties_and_damages: FindingList
    change_suspension_and_termination: FindingList
    force_majeure_and_notifications: FindingList
    dispute_confidentiality_and_ip: FindingList
    ambiguities: FindingList
    contradictions: FindingList
    clarification_points: FindingList


class ProviderAnalysisPayload(_StrictProviderModel):
    summary: SummaryText
    requirements: ProviderRequirementsPayload
    technical_specification: ProviderTechnicalSpecificationPayload
    draft_contract: ProviderDraftContractPayload
    risks: FindingList
    suspicious_conditions: FindingList
    contradictions: FindingList
    missing_documents: Annotated[
        list[MissingDocumentText],
        Field(max_length=MAX_MISSING_DOCUMENTS),
    ]
    final_ai_conclusion: SummaryText


class _InvalidJsonValue(ValueError):
    pass


def build_provider_output_json_schema() -> dict[str, object]:
    """Generate the provider JSON Schema from the canonical Pydantic model."""
    return ProviderAnalysisPayload.model_json_schema()


def build_responses_text_format() -> dict[str, object]:
    """Build the Responses API ``text.format`` value for strict JSON output."""
    return {
        "type": "json_schema",
        "name": AI_RESPONSE_FORMAT_NAME,
        "strict": True,
        "schema": build_provider_output_json_schema(),
    }


def decode_and_validate_provider_output(value: object) -> ProviderAnalysisPayload | None:
    """Decode one JSON object and return only a fully validated provider payload."""
    if not isinstance(value, (str, bytes, bytearray)):
        return None
    try:
        rendered = (
            value if isinstance(value, str) else bytes(value).decode("utf-8", errors="strict")
        )
        parsed = json.loads(
            rendered,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        if not isinstance(parsed, dict):
            return None
        return ProviderAnalysisPayload.model_validate(parsed, strict=True)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        _InvalidJsonValue,
        TypeError,
        ValueError,
    ):
        return None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in pairs:
        if key in result:
            raise _InvalidJsonValue
        result[key] = item
    return result


def _reject_constant(_value: str) -> None:
    raise _InvalidJsonValue


__all__ = [
    "AI_PROVIDER_OUTPUT_SCHEMA_VERSION",
    "AI_RESPONSE_FORMAT_NAME",
    "ProviderAnalysisPayload",
    "build_provider_output_json_schema",
    "build_responses_text_format",
    "decode_and_validate_provider_output",
]
