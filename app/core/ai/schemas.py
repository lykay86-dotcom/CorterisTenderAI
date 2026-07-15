"""Evidence-first, failure-safe contracts for Tender Intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
import math
import re
from typing import Any, Mapping, cast

from app.ai.provider import _safe_provider_id, _safe_provider_model
from app.core.document_classification import (
    APPLICATION_REQUIREMENTS_SOURCE_KINDS,
    DocumentKind,
)


AI_ANALYSIS_SCHEMA_VERSION = 7
_EXPECTED_PROVENANCE_PROMPT_VERSION = "6"
_EXPECTED_PROVENANCE_OUTPUT_SCHEMA_VERSION = "4"
_EXPECTED_PROVENANCE_ANALYZER_VERSION = "8"
_EXPECTED_PROVENANCE_CONTEXT_VERSION = "5"
_EXPECTED_PROVENANCE_CITATION_RESOLVER_VERSION = "1"
_MAX_TEXT_LENGTH = 12_000
_MAX_DOCUMENT_ID_LENGTH = 500
_MAX_DISPLAY_NAME_LENGTH = 500
_MAX_DOCUMENT_TYPE_LENGTH = 80
_MAX_STATUS_LENGTH = 80
_MAX_VERSION_LENGTH = 80
_MAX_ANALYSIS_ID_LENGTH = 200
_MAX_PROVIDER_ID_LENGTH = 80
_MAX_PROVIDER_MODEL_LENGTH = 200
_MAX_PROVIDER_RESPONSE_ID_LENGTH = 200
_MAX_SOURCES = 1_000
_CITATION_ID_PATTERN = re.compile(r"cit_[0-9a-f]{32}")
_LEGAL_RISK_ID_PATTERN = re.compile(r"legal_[0-9a-f]{32}")
_LEGAL_FIELD_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,79}")
_SOURCE_REF_PATTERN = re.compile(r"doc_[0-9a-f]{32}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}", re.IGNORECASE)
_PROVIDER_RESPONSE_REF_PATTERN = re.compile(r"resp_[0-9a-f]{64}")
_SOURCE_STATUS_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
_UNSAFE_SOURCE_DISPLAY_NAME_PATTERN = re.compile(r'[<>:"|?*\x00-\x1f]')
_UNSAFE_SOURCE_METADATA_WORDS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "bearer",
        "credential",
        "exception",
        "password",
        "secret",
        "token",
        "traceback",
    }
)


class AiAnalysisStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    NO_DOCUMENTS = "no_documents"
    PROVIDER_DISABLED = "provider_disabled"
    PROVIDER_ERROR = "provider_error"
    INVALID_RESPONSE = "invalid_response"
    CACHE_INCOMPATIBLE = "cache_incompatible"


class AiFindingStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class AiTechnicalSpecificationStatus(StrEnum):
    NOT_FOUND = "not_found"
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class AiDraftContractStatus(StrEnum):
    NOT_FOUND = "not_found"
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class AiApplicationRequirementsStatus(StrEnum):
    NOT_FOUND = "not_found"
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class AiLegalRiskStatus(StrEnum):
    NO_VERIFIED_RISKS = "no_verified_risks"
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class AiLegalReviewPriority(StrEnum):
    ROUTINE = "routine"
    ELEVATED = "elevated"
    URGENT = "urgent"


class AiLegalRiskCategory(StrEnum):
    APPLICATION_COMPOSITION_AND_DECLARATIONS = "application_composition_and_declarations"
    SUBMISSION_FORMAT_AND_SIGNATURE = "submission_format_and_signature"
    GROUNDS_FOR_REJECTION = "grounds_for_rejection"
    ELIGIBILITY_AND_AUTHORIZATIONS = "eligibility_and_authorizations"
    NATIONAL_REGIME_AND_ORIGIN = "national_regime_and_origin"
    SECURITY_AND_GUARANTEES = "security_and_guarantees"
    SCOPE_AND_CUSTOMER_DEPENDENCIES = "scope_and_customer_dependencies"
    PRICE_PAYMENT_AND_CHANGE_MECHANISM = "price_payment_and_change_mechanism"
    ACCEPTANCE_AND_CLOSING = "acceptance_and_closing"
    LIABILITY_PENALTIES_AND_DAMAGES = "liability_penalties_and_damages"
    CHANGE_SUSPENSION_AND_TERMINATION = "change_suspension_and_termination"
    WARRANTY_AND_REMEDIES = "warranty_and_remedies"
    SUBCONTRACTING_AND_THIRD_PARTIES = "subcontracting_and_third_parties"
    FORCE_MAJEURE_AND_NOTICES = "force_majeure_and_notices"
    DISPUTES_CONFIDENTIALITY_AND_IP = "disputes_confidentiality_and_ip"
    STANDARDS_AND_REGULATIONS = "standards_and_regulations"
    AMBIGUITIES_AND_CLARIFICATIONS = "ambiguities_and_clarifications"
    CONTRADICTIONS = "contradictions"


class AiEvidenceVerificationMethod(StrEnum):
    EXACT_QUOTE = "exact_quote"


@dataclass(frozen=True, slots=True)
class AiSourceSnapshot:
    document_id: str
    display_name: str
    document_type: str
    checksum_sha256: str
    verification_status: str
    received_at: str
    truncated: bool
    included_character_count: int
    original_character_count: int
    document_kind: str = DocumentKind.OTHER.value

    def __post_init__(self) -> None:
        document_id = _safe_source_value(self.document_id, _MAX_DOCUMENT_ID_LENGTH)
        if not document_id:
            raise ValueError("document_id must be non-empty")
        checksum = _bounded_text(self.checksum_sha256, 64)
        if _SHA256_PATTERN.fullmatch(checksum) is None:
            raise ValueError("checksum_sha256 must be a SHA-256 value")
        if (
            isinstance(self.included_character_count, bool)
            or not isinstance(self.included_character_count, int)
            or self.included_character_count < 0
            or isinstance(self.original_character_count, bool)
            or not isinstance(self.original_character_count, int)
            or self.original_character_count < self.included_character_count
        ):
            raise ValueError("source character counts must be non-negative and bounded")
        if not isinstance(self.truncated, bool):
            raise ValueError("truncated must be a boolean")
        object.__setattr__(self, "document_id", document_id)
        object.__setattr__(
            self,
            "display_name",
            _safe_display_name(self.display_name),
        )
        object.__setattr__(
            self,
            "document_type",
            _safe_document_type(self.document_type),
        )
        object.__setattr__(self, "checksum_sha256", checksum.lower())
        object.__setattr__(
            self,
            "verification_status",
            _safe_verification_status(self.verification_status),
        )
        object.__setattr__(self, "received_at", _known_timezone_aware(self.received_at))
        try:
            document_kind = DocumentKind(self.document_kind).value
        except (TypeError, ValueError):
            document_kind = DocumentKind.OTHER.value
        object.__setattr__(self, "document_kind", document_kind)

    def to_payload(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "display_name": self.display_name,
            "document_type": self.document_type,
            "checksum_sha256": self.checksum_sha256,
            "verification_status": self.verification_status,
            "received_at": self.received_at,
            "truncated": self.truncated,
            "included_character_count": self.included_character_count,
            "original_character_count": self.original_character_count,
            "document_kind": self.document_kind,
        }


@dataclass(frozen=True, slots=True)
class AiAnalysisProvenance:
    analysis_id: str
    context_fingerprint: str
    created_at: str
    prompt_version: str
    output_schema_version: str
    persisted_schema_version: int
    analyzer_version: str
    context_version: str
    citation_resolver_version: str
    provider_id: str
    provider_model: str
    provider_response_id: str
    sources: tuple[AiSourceSnapshot, ...]

    def __post_init__(self) -> None:
        analysis_id = _safe_metadata_text(self.analysis_id, _MAX_ANALYSIS_ID_LENGTH, "unknown")
        fingerprint = _bounded_text(self.context_fingerprint, 64)
        if _SHA256_PATTERN.fullmatch(fingerprint) is None:
            raise ValueError("context_fingerprint must be a SHA-256 value")
        if (
            isinstance(self.persisted_schema_version, bool)
            or not isinstance(self.persisted_schema_version, int)
            or self.persisted_schema_version < 1
        ):
            raise ValueError("persisted_schema_version must be a positive integer")
        if not isinstance(self.sources, tuple) or len(self.sources) > _MAX_SOURCES:
            raise ValueError("sources must be a bounded tuple")
        if not all(isinstance(item, AiSourceSnapshot) for item in self.sources):
            raise ValueError("sources must contain source snapshots")
        object.__setattr__(self, "analysis_id", analysis_id)
        object.__setattr__(self, "context_fingerprint", fingerprint.lower())
        object.__setattr__(self, "created_at", _required_timezone_aware(self.created_at))
        for name in (
            "prompt_version",
            "output_schema_version",
            "analyzer_version",
            "context_version",
            "citation_resolver_version",
        ):
            rendered = _bounded_text(getattr(self, name), _MAX_VERSION_LENGTH)
            if not rendered:
                raise ValueError(f"{name} must be non-empty")
            object.__setattr__(self, name, rendered)
        object.__setattr__(
            self,
            "provider_id",
            _safe_provider_id(self.provider_id),
        )
        object.__setattr__(
            self,
            "provider_model",
            _safe_provider_model(self.provider_model),
        )
        object.__setattr__(
            self,
            "provider_response_id",
            _safe_provider_response_reference(self.provider_response_id),
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "analysis_id": self.analysis_id,
            "context_fingerprint": self.context_fingerprint,
            "created_at": self.created_at,
            "prompt_version": self.prompt_version,
            "output_schema_version": self.output_schema_version,
            "persisted_schema_version": self.persisted_schema_version,
            "analyzer_version": self.analyzer_version,
            "context_version": self.context_version,
            "citation_resolver_version": self.citation_resolver_version,
            "provider_id": self.provider_id,
            "provider_model": self.provider_model,
            "provider_response_id": self.provider_response_id,
            "sources": [item.to_payload() for item in self.sources],
        }


@dataclass(frozen=True, slots=True)
class AiDocument:
    document_id: str
    name: str
    source: str
    document_type: str
    received_at: str
    verification_status: str
    text: str
    checksum_sha256: str = ""
    truncated: bool = False
    original_character_count: int = 0
    document_kind: str = "other"


@dataclass(frozen=True, slots=True)
class AiEvidence:
    citation_id: str
    document_id: str
    quote: str
    character_start: int
    character_end: int
    section: str
    page: int | None
    confidence: float
    verification_method: AiEvidenceVerificationMethod
    checksum_sha256: str
    source_ref: str
    context_fingerprint: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.citation_id, str)
            or _CITATION_ID_PATTERN.fullmatch(self.citation_id) is None
        ):
            raise ValueError("citation_id must be a canonical citation reference")
        if not isinstance(self.document_id, str) or not self.document_id:
            raise ValueError("document_id must be non-empty")
        if not isinstance(self.quote, str) or not self.quote:
            raise ValueError("quote must be non-empty")
        if (
            isinstance(self.character_start, bool)
            or not isinstance(self.character_start, int)
            or self.character_start < 0
            or isinstance(self.character_end, bool)
            or not isinstance(self.character_end, int)
            or self.character_end != self.character_start + len(self.quote)
        ):
            raise ValueError("character offsets must exactly bound quote")
        if not isinstance(self.section, str):
            raise ValueError("section must be text")
        if self.page is not None and (
            isinstance(self.page, bool) or not isinstance(self.page, int) or self.page < 1
        ):
            raise ValueError("page must be a positive integer or None")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence)
            or not 0.0 <= self.confidence <= 1.0
        ):
            raise ValueError("confidence must be a finite number between 0 and 1")
        if self.verification_method is not AiEvidenceVerificationMethod.EXACT_QUOTE:
            raise ValueError("verification_method must be exact_quote")
        if (
            not isinstance(self.checksum_sha256, str)
            or _SHA256_PATTERN.fullmatch(self.checksum_sha256) is None
        ):
            raise ValueError("checksum_sha256 must be a SHA-256 value")
        if (
            not isinstance(self.source_ref, str)
            or _SOURCE_REF_PATTERN.fullmatch(self.source_ref) is None
        ):
            raise ValueError("source_ref must be a canonical document reference")
        if (
            not isinstance(self.context_fingerprint, str)
            or _SHA256_PATTERN.fullmatch(self.context_fingerprint) is None
        ):
            raise ValueError("context_fingerprint must be a lowercase SHA-256 value")


@dataclass(frozen=True, slots=True)
class AiFinding:
    category: str
    statement: str
    evidence: AiEvidence | None
    status: AiFindingStatus

    @property
    def verified(self) -> bool:
        return self.status == AiFindingStatus.VERIFIED


@dataclass(frozen=True, slots=True)
class AiLegalRiskSourceRef:
    section: str
    field: str
    citation_id: str

    def __post_init__(self) -> None:
        if self.section not in {"requirements", "technical_specification", "draft_contract"}:
            raise ValueError("unsupported legal risk source section")
        if not isinstance(self.field, str) or _LEGAL_FIELD_PATTERN.fullmatch(self.field) is None:
            raise ValueError("unsupported legal risk source field")
        if (
            not isinstance(self.citation_id, str)
            or _CITATION_ID_PATTERN.fullmatch(self.citation_id) is None
        ):
            raise ValueError("legal risk source must use a canonical citation ID")

    def to_payload(self) -> dict[str, str]:
        return {
            "section": self.section,
            "field": self.field,
            "citation_id": self.citation_id,
        }


@dataclass(frozen=True, slots=True)
class AiLegalRiskItem:
    risk_id: str
    category: AiLegalRiskCategory | str
    review_priority: AiLegalReviewPriority | str
    title: str
    source_refs: tuple[AiLegalRiskSourceRef, ...]
    recommended_action: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.risk_id, str)
            or _LEGAL_RISK_ID_PATTERN.fullmatch(self.risk_id) is None
        ):
            raise ValueError("risk_id must be a canonical legal risk ID")
        try:
            category = AiLegalRiskCategory(self.category)
            priority = AiLegalReviewPriority(self.review_priority)
        except (TypeError, ValueError) as exc:
            raise ValueError("unsupported legal risk category or priority") from exc
        if (
            not isinstance(self.source_refs, tuple)
            or not self.source_refs
            or not all(isinstance(item, AiLegalRiskSourceRef) for item in self.source_refs)
            or len(set(self.source_refs)) != len(self.source_refs)
        ):
            raise ValueError("source_refs must be a non-empty unique tuple")
        title = _bounded_text(self.title, 500)
        action = _bounded_text(self.recommended_action, 1_000)
        if not title or not action:
            raise ValueError("legal risk title and action must be non-empty")
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "review_priority", priority)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "recommended_action", action)

    def to_payload(self) -> dict[str, object]:
        return {
            "risk_id": self.risk_id,
            "category": AiLegalRiskCategory(self.category).value,
            "review_priority": AiLegalReviewPriority(self.review_priority).value,
            "title": self.title,
            "source_refs": [item.to_payload() for item in self.source_refs],
            "recommended_action": self.recommended_action,
        }


@dataclass(frozen=True, slots=True)
class AiLegalRiskAssessment:
    status: AiLegalRiskStatus | str = AiLegalRiskStatus.UNAVAILABLE
    policy_version: str = "1"
    items: tuple[AiLegalRiskItem, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            status = AiLegalRiskStatus(self.status)
        except (TypeError, ValueError):
            status = AiLegalRiskStatus.UNAVAILABLE
        version = _bounded_text(self.policy_version, _MAX_VERSION_LENGTH)
        if not version:
            raise ValueError("policy_version must be non-empty")
        if not isinstance(self.items, tuple) or not all(
            isinstance(item, AiLegalRiskItem) for item in self.items
        ):
            raise ValueError("items must contain legal risk items")
        warnings = tuple(
            dict.fromkeys(text for item in self.warnings if (text := _text(item, 1_000)))
        )
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "policy_version", version)
        object.__setattr__(self, "warnings", warnings)

    def to_payload(self) -> dict[str, object]:
        return {
            "status": AiLegalRiskStatus(self.status).value,
            "policy_version": self.policy_version,
            "items": [item.to_payload() for item in self.items],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class TenderRequirements:
    status: AiApplicationRequirementsStatus | str = AiApplicationRequirementsStatus.UNAVAILABLE
    document_ids: tuple[str, ...] = ()
    included_document_ids: tuple[str, ...] = ()
    application_composition: tuple[AiFinding, ...] = ()
    participant_eligibility: tuple[AiFinding, ...] = ()
    declarations_and_consents: tuple[AiFinding, ...] = ()
    equipment: tuple[AiFinding, ...] = ()
    certificates: tuple[AiFinding, ...] = ()
    licenses: tuple[AiFinding, ...] = ()
    specialists: tuple[AiFinding, ...] = ()
    documents: tuple[AiFinding, ...] = ()
    experience: tuple[AiFinding, ...] = ()
    deadlines: tuple[AiFinding, ...] = ()
    warranty: tuple[AiFinding, ...] = ()
    bid_security: tuple[AiFinding, ...] = ()
    contract_security: tuple[AiFinding, ...] = ()
    bank_guarantee: tuple[AiFinding, ...] = ()
    submission_format_and_signature: tuple[AiFinding, ...] = ()
    national_regime_and_origin: tuple[AiFinding, ...] = ()
    price_proposal_and_estimate: tuple[AiFinding, ...] = ()
    grounds_for_rejection: tuple[AiFinding, ...] = ()
    ambiguities: tuple[AiFinding, ...] = ()
    contradictions: tuple[AiFinding, ...] = ()
    clarification_points: tuple[AiFinding, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            status = AiApplicationRequirementsStatus(self.status)
        except (TypeError, ValueError):
            status = AiApplicationRequirementsStatus.UNAVAILABLE
        object.__setattr__(self, "status", status)


_APPLICATION_REQUIREMENTS_FINDING_FIELDS = (
    "application_composition",
    "participant_eligibility",
    "declarations_and_consents",
    "equipment",
    "certificates",
    "licenses",
    "specialists",
    "documents",
    "experience",
    "deadlines",
    "warranty",
    "bid_security",
    "contract_security",
    "bank_guarantee",
    "submission_format_and_signature",
    "national_regime_and_origin",
    "price_proposal_and_estimate",
    "grounds_for_rejection",
    "ambiguities",
    "contradictions",
    "clarification_points",
)

_LEGACY_REQUIREMENT_FINDING_FIELDS = (
    "equipment",
    "certificates",
    "licenses",
    "specialists",
    "documents",
    "experience",
    "deadlines",
    "warranty",
    "bid_security",
    "contract_security",
    "bank_guarantee",
)


@dataclass(frozen=True, slots=True)
class AiTechnicalSpecificationAnalysis:
    status: AiTechnicalSpecificationStatus | str = AiTechnicalSpecificationStatus.UNAVAILABLE
    document_ids: tuple[str, ...] = ()
    included_document_ids: tuple[str, ...] = ()
    scope: tuple[AiFinding, ...] = ()
    deliverables: tuple[AiFinding, ...] = ()
    quantities_and_volumes: tuple[AiFinding, ...] = ()
    technical_characteristics: tuple[AiFinding, ...] = ()
    materials_and_equipment: tuple[AiFinding, ...] = ()
    standards_and_regulations: tuple[AiFinding, ...] = ()
    execution_conditions: tuple[AiFinding, ...] = ()
    stages_and_deadlines: tuple[AiFinding, ...] = ()
    acceptance_and_quality: tuple[AiFinding, ...] = ()
    customer_inputs_and_dependencies: tuple[AiFinding, ...] = ()
    ambiguities: tuple[AiFinding, ...] = ()
    contradictions: tuple[AiFinding, ...] = ()
    clarification_points: tuple[AiFinding, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            status = AiTechnicalSpecificationStatus(self.status)
        except (TypeError, ValueError):
            status = AiTechnicalSpecificationStatus.UNAVAILABLE
        object.__setattr__(self, "status", status)


@dataclass(frozen=True, slots=True)
class AiDraftContractAnalysis:
    status: AiDraftContractStatus | str = AiDraftContractStatus.UNAVAILABLE
    document_ids: tuple[str, ...] = ()
    included_document_ids: tuple[str, ...] = ()
    subject_and_scope: tuple[AiFinding, ...] = ()
    term_schedule_and_location: tuple[AiFinding, ...] = ()
    price_and_price_change: tuple[AiFinding, ...] = ()
    payment_terms: tuple[AiFinding, ...] = ()
    acceptance_and_closing_documents: tuple[AiFinding, ...] = ()
    performance_security: tuple[AiFinding, ...] = ()
    warranty_and_defect_remediation: tuple[AiFinding, ...] = ()
    customer_obligations_and_dependencies: tuple[AiFinding, ...] = ()
    contractor_obligations_and_subcontracting: tuple[AiFinding, ...] = ()
    liability_penalties_and_damages: tuple[AiFinding, ...] = ()
    change_suspension_and_termination: tuple[AiFinding, ...] = ()
    force_majeure_and_notifications: tuple[AiFinding, ...] = ()
    dispute_confidentiality_and_ip: tuple[AiFinding, ...] = ()
    ambiguities: tuple[AiFinding, ...] = ()
    contradictions: tuple[AiFinding, ...] = ()
    clarification_points: tuple[AiFinding, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            status = AiDraftContractStatus(self.status)
        except (TypeError, ValueError):
            status = AiDraftContractStatus.UNAVAILABLE
        object.__setattr__(self, "status", status)


@dataclass(frozen=True, slots=True)
class AiDocumentAnalysis:
    registry_key: str
    summary: str
    requirements: TenderRequirements = field(default_factory=TenderRequirements)
    risks: tuple[AiFinding, ...] = ()
    suspicious_conditions: tuple[AiFinding, ...] = ()
    contradictions: tuple[AiFinding, ...] = ()
    missing_documents: tuple[str, ...] = ()
    final_ai_conclusion: str = ""
    status: AiAnalysisStatus | str = AiAnalysisStatus.PARTIAL
    payload_version: int = AI_ANALYSIS_SCHEMA_VERSION
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    warnings: tuple[str, ...] = ()
    context_document_count: int = 0
    context_character_count: int = 0
    context_truncated: bool = False
    provenance: AiAnalysisProvenance | None = None
    technical_specification: AiTechnicalSpecificationAnalysis = field(
        default_factory=AiTechnicalSpecificationAnalysis
    )
    draft_contract: AiDraftContractAnalysis = field(default_factory=AiDraftContractAnalysis)
    legal_risk_assessment: AiLegalRiskAssessment = field(default_factory=AiLegalRiskAssessment)

    def __post_init__(self) -> None:
        try:
            status = AiAnalysisStatus(self.status)
        except (TypeError, ValueError):
            status = AiAnalysisStatus.INVALID_RESPONSE
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "created_at", _timezone_aware(self.created_at))

    def to_payload(self) -> dict[str, object]:
        def finding(item: AiFinding) -> dict[str, object]:
            return {
                "category": item.category,
                "statement": item.statement,
                "status": item.status.value,
                "evidence": (
                    {
                        "citation_id": item.evidence.citation_id,
                        "document_id": item.evidence.document_id,
                        "quote": item.evidence.quote,
                        "character_start": item.evidence.character_start,
                        "character_end": item.evidence.character_end,
                        "section": item.evidence.section,
                        "page": item.evidence.page,
                        "confidence": item.evidence.confidence,
                        "verification_method": item.evidence.verification_method.value,
                        "checksum_sha256": item.evidence.checksum_sha256,
                        "source_ref": item.evidence.source_ref,
                        "context_fingerprint": item.evidence.context_fingerprint,
                    }
                    if item.evidence
                    else None
                ),
            }

        payload: dict[str, object] = {
            "payload_version": self.payload_version,
            "registry_key": self.registry_key,
            "summary": self.summary,
            "requirements": {
                "status": AiApplicationRequirementsStatus(self.requirements.status).value,
                "document_ids": list(self.requirements.document_ids),
                "included_document_ids": list(self.requirements.included_document_ids),
                **{
                    name: [finding(item) for item in getattr(self.requirements, name)]
                    for name in _APPLICATION_REQUIREMENTS_FINDING_FIELDS
                },
                "warnings": list(self.requirements.warnings),
            },
            "technical_specification": {
                "status": AiTechnicalSpecificationStatus(self.technical_specification.status).value,
                "document_ids": list(self.technical_specification.document_ids),
                "included_document_ids": list(self.technical_specification.included_document_ids),
                **{
                    name: [finding(item) for item in getattr(self.technical_specification, name)]
                    for name in _TECHNICAL_SPECIFICATION_FINDING_FIELDS
                },
                "warnings": list(self.technical_specification.warnings),
            },
            "draft_contract": {
                "status": AiDraftContractStatus(self.draft_contract.status).value,
                "document_ids": list(self.draft_contract.document_ids),
                "included_document_ids": list(self.draft_contract.included_document_ids),
                **{
                    name: [finding(item) for item in getattr(self.draft_contract, name)]
                    for name in _DRAFT_CONTRACT_FINDING_FIELDS
                },
                "warnings": list(self.draft_contract.warnings),
            },
            "legal_risk_assessment": self.legal_risk_assessment.to_payload(),
            "risks": [finding(item) for item in self.risks],
            "suspicious_conditions": [finding(item) for item in self.suspicious_conditions],
            "contradictions": [finding(item) for item in self.contradictions],
            "missing_documents": list(self.missing_documents),
            "final_ai_conclusion": self.final_ai_conclusion,
            "status": AiAnalysisStatus(self.status).value,
            "created_at": self.created_at,
            "warnings": list(self.warnings),
            "context": {
                "document_count": self.context_document_count,
                "character_count": self.context_character_count,
                "truncated": self.context_truncated,
            },
        }
        if self.provenance is not None:
            payload["provenance"] = self.provenance.to_payload()
            payload["source_registry"] = [item.to_payload() for item in self.provenance.sources]
        return payload

    def is_current_verified(self, finding: AiFinding) -> bool:
        return (
            self.payload_version == AI_ANALYSIS_SCHEMA_VERSION
            and finding.status is AiFindingStatus.VERIFIED
            and finding.evidence is not None
            and self.provenance is not None
            and _evidence_matches_provenance(finding.evidence, self.provenance)
        )

    @classmethod
    def from_payload(cls, payload: object) -> "AiDocumentAnalysis":
        """Deserialize without allowing damaged values to become verified."""
        if not isinstance(payload, Mapping):
            return cls("", "", status=AiAnalysisStatus.INVALID_RESPONSE)

        raw_version = payload.get("payload_version", 1)
        registry_key = _text(payload.get("registry_key"))
        if type(raw_version) is not int:
            return cls(
                registry_key,
                "",
                status=AiAnalysisStatus.CACHE_INCOMPATIBLE,
                payload_version=0,
                warnings=("Сохранённый AI-анализ имеет несовместимую версию.",),
            )
        version = raw_version
        if version < 1 or version > AI_ANALYSIS_SCHEMA_VERSION:
            return cls(
                registry_key,
                "",
                status=AiAnalysisStatus.CACHE_INCOMPATIBLE,
                payload_version=version,
                warnings=("Сохранённый AI-анализ имеет несовместимую версию.",),
            )

        provenance = (
            _payload_provenance(payload.get("provenance"))
            if version == AI_ANALYSIS_SCHEMA_VERSION
            else None
        )
        source_registry = payload.get("source_registry")
        if (
            provenance is None
            or not isinstance(source_registry, list)
            or source_registry != [item.to_payload() for item in provenance.sources]
        ):
            provenance = None

        def findings(value: object) -> tuple[AiFinding, ...]:
            result: list[AiFinding] = []
            if not isinstance(value, (list, tuple)):
                return ()
            for item in value:
                if not isinstance(item, Mapping):
                    continue
                statement = _text(item.get("statement"), _MAX_TEXT_LENGTH)
                if not statement:
                    continue
                raw_evidence = item.get("evidence")
                evidence = _payload_evidence(raw_evidence)
                requested_verified = item.get("status") == AiFindingStatus.VERIFIED.value
                status = (
                    AiFindingStatus.VERIFIED
                    if (
                        version == AI_ANALYSIS_SCHEMA_VERSION
                        and requested_verified
                        and evidence is not None
                        and provenance is not None
                        and _evidence_matches_provenance(evidence, provenance)
                    )
                    else AiFindingStatus.UNVERIFIED
                )
                result.append(
                    AiFinding(
                        _text(item.get("category"), 200),
                        statement,
                        evidence if status == AiFindingStatus.VERIFIED else None,
                        status,
                    )
                )
            return tuple(result)

        raw_requirements = payload.get("requirements", {})
        current_requirements = (
            raw_requirements
            if version == AI_ANALYSIS_SCHEMA_VERSION
            and _valid_scoped_payload(
                raw_requirements,
                finding_fields=_APPLICATION_REQUIREMENTS_FINDING_FIELDS,
                status_type=AiApplicationRequirementsStatus,
            )
            else {}
        )
        legacy_requirements = (
            raw_requirements
            if version < AI_ANALYSIS_SCHEMA_VERSION and isinstance(raw_requirements, Mapping)
            else {}
        )
        requirement_map = current_requirements or legacy_requirements
        raw_status = payload.get("status", AiAnalysisStatus.PARTIAL.value)
        try:
            status = AiAnalysisStatus(raw_status)
        except (TypeError, ValueError):
            status = AiAnalysisStatus.INVALID_RESPONSE
        raw_missing = payload.get("missing_documents", ())
        missing = (
            tuple(text for item in raw_missing if (text := _text(item, 1_000)))
            if isinstance(raw_missing, (list, tuple))
            else ()
        )
        raw_warnings = payload.get("warnings", ())
        warnings = (
            tuple(text for item in raw_warnings if (text := _text(item, 1_000)))
            if isinstance(raw_warnings, (list, tuple))
            else ()
        )
        raw_context = payload.get("context", {})
        context = raw_context if isinstance(raw_context, Mapping) else {}
        raw_ts = payload.get("technical_specification", {})
        ts = (
            raw_ts
            if version == AI_ANALYSIS_SCHEMA_VERSION and _valid_technical_payload(raw_ts)
            else {}
        )
        raw_ts_ids = ts.get("document_ids", ())
        ts_ids = (
            tuple(
                text
                for item in raw_ts_ids
                if (text := _safe_source_value(item, _MAX_DOCUMENT_ID_LENGTH))
            )
            if isinstance(raw_ts_ids, (list, tuple))
            else ()
        )
        raw_ts_warnings = ts.get("warnings", ())
        ts_warnings = (
            tuple(text for item in raw_ts_warnings if (text := _text(item, 1_000)))
            if isinstance(raw_ts_warnings, (list, tuple))
            else ()
        )
        raw_included_ts_ids = ts.get("included_document_ids", ())
        included_ts_ids = (
            tuple(
                text
                for item in raw_included_ts_ids
                if (text := _safe_source_value(item, _MAX_DOCUMENT_ID_LENGTH))
            )
            if isinstance(raw_included_ts_ids, (list, tuple))
            else ()
        )
        raw_contract = payload.get("draft_contract", {})
        contract = (
            raw_contract
            if version == AI_ANALYSIS_SCHEMA_VERSION
            and _valid_scoped_payload(
                raw_contract,
                finding_fields=_DRAFT_CONTRACT_FINDING_FIELDS,
                status_type=AiDraftContractStatus,
            )
            else {}
        )
        contract_ids = _payload_document_ids(contract.get("document_ids", ()))
        included_contract_ids = _payload_document_ids(contract.get("included_document_ids", ()))
        contract_warnings = _payload_strings(contract.get("warnings", ()), 1_000)
        requirement_values = {
            name: (
                _scoped_payload_findings(
                    findings(requirement_map.get(name)),
                    provenance,
                    APPLICATION_REQUIREMENTS_SOURCE_KINDS,
                )
                if current_requirements
                else findings(requirement_map.get(name))
                if name in _LEGACY_REQUIREMENT_FINDING_FIELDS
                else ()
            )
            for name in _APPLICATION_REQUIREMENTS_FINDING_FIELDS
        }
        if current_requirements:
            requirement_status = AiApplicationRequirementsStatus(
                cast(str, current_requirements.get("status"))
            )
            requirement_ids = _payload_document_ids(current_requirements.get("document_ids", ()))
            included_requirement_ids = _payload_document_ids(
                current_requirements.get("included_document_ids", ())
            )
            requirement_warnings = _payload_strings(current_requirements.get("warnings", ()), 1_000)
            if requirement_status is AiApplicationRequirementsStatus.COMPLETE and any(
                not item.verified for items in requirement_values.values() for item in items
            ):
                requirement_status = AiApplicationRequirementsStatus.PARTIAL
                requirement_warnings = tuple(
                    dict.fromkeys(
                        (*requirement_warnings, "Часть сохранённых требований не подтверждена.")
                    )
                )
        elif version < AI_ANALYSIS_SCHEMA_VERSION:
            requirement_status = AiApplicationRequirementsStatus.UNAVAILABLE
            requirement_ids = ()
            included_requirement_ids = ()
            requirement_warnings = (
                "Сохранённый legacy-анализ требований не имеет проверяемой области документов.",
            )
        else:
            requirement_status = AiApplicationRequirementsStatus.UNAVAILABLE
            requirement_ids = ()
            included_requirement_ids = ()
            requirement_values = {name: () for name in _APPLICATION_REQUIREMENTS_FINDING_FIELDS}
            requirement_warnings = (
                "Сохранённый анализ требований к заявке имеет повреждённую форму.",
            )
        analysis = cls(
            registry_key=registry_key,
            summary=_text(payload.get("summary"), _MAX_TEXT_LENGTH),
            requirements=TenderRequirements(
                status=requirement_status,
                document_ids=requirement_ids,
                included_document_ids=included_requirement_ids,
                **requirement_values,
                warnings=requirement_warnings,
            ),
            risks=findings(payload.get("risks")),
            suspicious_conditions=findings(payload.get("suspicious_conditions")),
            contradictions=findings(payload.get("contradictions")),
            missing_documents=missing,
            final_ai_conclusion=_text(payload.get("final_ai_conclusion"), _MAX_TEXT_LENGTH),
            status=status,
            payload_version=version,
            created_at=_text(payload.get("created_at")),
            warnings=warnings,
            context_document_count=max(0, _safe_int(context.get("document_count"))),
            context_character_count=max(0, _safe_int(context.get("character_count"))),
            context_truncated=bool(context.get("truncated", False)),
            provenance=provenance,
            technical_specification=AiTechnicalSpecificationAnalysis(
                status=ts.get("status", AiTechnicalSpecificationStatus.UNAVAILABLE.value),
                document_ids=ts_ids,
                included_document_ids=included_ts_ids,
                **{
                    name: _technical_payload_findings(findings(ts.get(name)), provenance)
                    for name in _TECHNICAL_SPECIFICATION_FINDING_FIELDS
                },
                warnings=ts_warnings,
            ),
            draft_contract=AiDraftContractAnalysis(
                status=contract.get("status", AiDraftContractStatus.UNAVAILABLE.value),
                document_ids=contract_ids,
                included_document_ids=included_contract_ids,
                **{
                    name: _scoped_payload_findings(
                        findings(contract.get(name)),
                        provenance,
                        DocumentKind.DRAFT_CONTRACT,
                    )
                    for name in _DRAFT_CONTRACT_FINDING_FIELDS
                },
                warnings=contract_warnings,
            ),
        )
        if version < AI_ANALYSIS_SCHEMA_VERSION:
            return analysis

        from app.core.ai.legal_risk import assess_legal_risks

        computed_legal = assess_legal_risks(analysis)
        if payload.get("legal_risk_assessment") == computed_legal.to_payload():
            return replace(analysis, legal_risk_assessment=computed_legal)
        warning = "Сохранённая оценка юридических рисков повреждена и пересчитана локально."
        degraded_legal = replace(
            computed_legal,
            status=(
                AiLegalRiskStatus.UNAVAILABLE
                if computed_legal.status is AiLegalRiskStatus.UNAVAILABLE
                else AiLegalRiskStatus.PARTIAL
            ),
            warnings=tuple(dict.fromkeys((*computed_legal.warnings, warning))),
        )
        return replace(analysis, legal_risk_assessment=degraded_legal)


_TECHNICAL_SPECIFICATION_FINDING_FIELDS = tuple(
    name
    for name in AiTechnicalSpecificationAnalysis.__dataclass_fields__
    if name not in {"status", "document_ids", "included_document_ids", "warnings"}
)

_DRAFT_CONTRACT_FINDING_FIELDS = tuple(
    name
    for name in AiDraftContractAnalysis.__dataclass_fields__
    if name not in {"status", "document_ids", "included_document_ids", "warnings"}
)


def _valid_technical_payload(value: object) -> bool:
    return _valid_scoped_payload(
        value,
        finding_fields=_TECHNICAL_SPECIFICATION_FINDING_FIELDS,
        status_type=AiTechnicalSpecificationStatus,
    )


def _valid_scoped_payload(
    value: object,
    *,
    finding_fields: tuple[str, ...],
    status_type: (
        type[AiApplicationRequirementsStatus]
        | type[AiTechnicalSpecificationStatus]
        | type[AiDraftContractStatus]
    ),
) -> bool:
    if not isinstance(value, Mapping):
        return False
    expected = {
        "status",
        "document_ids",
        "included_document_ids",
        "warnings",
        *finding_fields,
    }
    if set(value) != expected:
        return False
    raw_status = value.get("status")
    if not isinstance(raw_status, str):
        return False
    try:
        status_type(raw_status)
    except (TypeError, ValueError):
        return False
    return all(
        isinstance(value.get(name), list)
        for name in (*finding_fields, "document_ids", "included_document_ids", "warnings")
    )


def _payload_document_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(
        text for item in value if (text := _safe_source_value(item, _MAX_DOCUMENT_ID_LENGTH))
    )


def _payload_strings(value: object, limit: int) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(text for item in value if (text := _text(item, limit)))


def _payload_provenance(value: object) -> AiAnalysisProvenance | None:
    if not isinstance(value, Mapping):
        return None
    if not _payload_has_current_provenance_versions(value):
        return None
    raw_provider_id = value.get("provider_id")
    raw_provider_model = value.get("provider_model")
    raw_provider_response_id = value.get("provider_response_id")
    if (
        raw_provider_id != _safe_provider_id(raw_provider_id)
        or raw_provider_model != _safe_provider_model(raw_provider_model)
        or raw_provider_response_id != _safe_provider_response_reference(raw_provider_response_id)
    ):
        return None
    raw_sources = value.get("sources")
    if not isinstance(raw_sources, list) or len(raw_sources) > _MAX_SOURCES:
        return None
    sources: list[AiSourceSnapshot] = []
    for raw_source in raw_sources:
        source = _payload_source_snapshot(raw_source)
        if source is None:
            return None
        sources.append(source)
    try:
        return AiAnalysisProvenance(
            analysis_id=cast(str, value.get("analysis_id")),
            context_fingerprint=cast(str, value.get("context_fingerprint")),
            created_at=cast(str, value.get("created_at")),
            prompt_version=cast(str, value.get("prompt_version")),
            output_schema_version=cast(str, value.get("output_schema_version")),
            persisted_schema_version=cast(int, value.get("persisted_schema_version")),
            analyzer_version=cast(str, value.get("analyzer_version")),
            context_version=cast(str, value.get("context_version")),
            citation_resolver_version=cast(str, value.get("citation_resolver_version")),
            provider_id=cast(str, value.get("provider_id")),
            provider_model=cast(str, value.get("provider_model")),
            provider_response_id=cast(str, value.get("provider_response_id")),
            sources=tuple(sources),
        )
    except (TypeError, ValueError):
        return None


def _payload_source_snapshot(value: object) -> AiSourceSnapshot | None:
    if not isinstance(value, Mapping):
        return None
    try:
        source = AiSourceSnapshot(
            document_id=cast(str, value.get("document_id")),
            display_name=cast(str, value.get("display_name")),
            document_type=cast(str, value.get("document_type")),
            checksum_sha256=cast(str, value.get("checksum_sha256")),
            verification_status=cast(str, value.get("verification_status")),
            received_at=cast(str, value.get("received_at")),
            truncated=cast(bool, value.get("truncated")),
            included_character_count=cast(int, value.get("included_character_count")),
            original_character_count=cast(int, value.get("original_character_count")),
            document_kind=cast(str, value.get("document_kind")),
        )
    except (TypeError, ValueError):
        return None
    if (
        value.get("display_name") != source.display_name
        or value.get("verification_status") != source.verification_status
    ):
        return None
    return source


def _technical_payload_findings(
    findings: tuple[AiFinding, ...],
    provenance: AiAnalysisProvenance | None,
) -> tuple[AiFinding, ...]:
    return _scoped_payload_findings(
        findings,
        provenance,
        DocumentKind.TECHNICAL_SPECIFICATION,
    )


def _scoped_payload_findings(
    findings: tuple[AiFinding, ...],
    provenance: AiAnalysisProvenance | None,
    document_kinds: DocumentKind | frozenset[DocumentKind],
) -> tuple[AiFinding, ...]:
    kinds = (
        frozenset({document_kinds}) if isinstance(document_kinds, DocumentKind) else document_kinds
    )
    allowed_ids = {
        source.document_id
        for source in (provenance.sources if provenance is not None else ())
        if source.document_kind in {kind.value for kind in kinds}
    }
    return tuple(
        item
        if item.evidence is not None and item.evidence.document_id in allowed_ids
        else AiFinding(item.category, item.statement, None, AiFindingStatus.UNVERIFIED)
        for item in findings
    )


def _evidence_matches_provenance(
    evidence: AiEvidence,
    provenance: AiAnalysisProvenance,
) -> bool:
    if (
        not _has_current_provenance_versions(provenance)
        or evidence.context_fingerprint != provenance.context_fingerprint
    ):
        return False
    matching_sources = tuple(
        item for item in provenance.sources if item.document_id == evidence.document_id
    )
    if len(matching_sources) != 1:
        return False
    source = matching_sources[0]
    if source.checksum_sha256 != evidence.checksum_sha256:
        return False
    source_digest = hashlib.sha256(evidence.document_id.encode("utf-8")).hexdigest()[:32]
    if evidence.source_ref != f"doc_{source_digest}":
        return False
    canonical = json.dumps(
        {
            "character_end": evidence.character_end,
            "character_start": evidence.character_start,
            "checksum_sha256": evidence.checksum_sha256,
            "context_fingerprint": evidence.context_fingerprint,
            "document_id": evidence.document_id,
            "quote": evidence.quote,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    citation_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return evidence.citation_id == f"cit_{citation_digest}"


def _payload_has_current_provenance_versions(value: Mapping[object, object]) -> bool:
    return (
        value.get("prompt_version") == _EXPECTED_PROVENANCE_PROMPT_VERSION
        and value.get("output_schema_version") == _EXPECTED_PROVENANCE_OUTPUT_SCHEMA_VERSION
        and type(value.get("persisted_schema_version")) is int
        and value.get("persisted_schema_version") == AI_ANALYSIS_SCHEMA_VERSION
        and value.get("analyzer_version") == _EXPECTED_PROVENANCE_ANALYZER_VERSION
        and value.get("context_version") == _EXPECTED_PROVENANCE_CONTEXT_VERSION
        and value.get("citation_resolver_version") == _EXPECTED_PROVENANCE_CITATION_RESOLVER_VERSION
    )


def _has_current_provenance_versions(provenance: AiAnalysisProvenance) -> bool:
    return (
        provenance.prompt_version == _EXPECTED_PROVENANCE_PROMPT_VERSION
        and provenance.output_schema_version == _EXPECTED_PROVENANCE_OUTPUT_SCHEMA_VERSION
        and provenance.persisted_schema_version == AI_ANALYSIS_SCHEMA_VERSION
        and provenance.analyzer_version == _EXPECTED_PROVENANCE_ANALYZER_VERSION
        and provenance.context_version == _EXPECTED_PROVENANCE_CONTEXT_VERSION
        and provenance.citation_resolver_version == _EXPECTED_PROVENANCE_CITATION_RESOLVER_VERSION
    )


def _payload_evidence(value: object) -> AiEvidence | None:
    if not isinstance(value, Mapping):
        return None
    citation_id = value.get("citation_id")
    document_id = value.get("document_id")
    quote = value.get("quote")
    character_start = value.get("character_start")
    character_end = value.get("character_end")
    section = value.get("section")
    confidence = _safe_confidence(value.get("confidence"))
    raw_page = value.get("page")
    page = _safe_page(raw_page)
    checksum = value.get("checksum_sha256")
    source_ref = value.get("source_ref")
    fingerprint = value.get("context_fingerprint")
    raw_verification_method = value.get("verification_method")
    if not isinstance(raw_verification_method, str):
        return None
    try:
        verification_method = AiEvidenceVerificationMethod(raw_verification_method)
    except ValueError:
        return None
    if (
        not isinstance(citation_id, str)
        or not isinstance(document_id, str)
        or not isinstance(quote, str)
        or isinstance(character_start, bool)
        or not isinstance(character_start, int)
        or isinstance(character_end, bool)
        or not isinstance(character_end, int)
        or not isinstance(section, str)
        or (raw_page is not None and page is None)
        or confidence is None
        or not isinstance(checksum, str)
        or not isinstance(source_ref, str)
        or not isinstance(fingerprint, str)
    ):
        return None
    try:
        return AiEvidence(
            citation_id=citation_id,
            document_id=document_id,
            quote=quote,
            character_start=character_start,
            character_end=character_end,
            section=section,
            page=page,
            confidence=confidence,
            verification_method=verification_method,
            checksum_sha256=checksum,
            source_ref=source_ref,
            context_fingerprint=fingerprint,
        )
    except (TypeError, ValueError):
        return None


def _safe_confidence(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    rendered = float(value)
    return rendered if math.isfinite(rendered) and 0.0 <= rendered <= 1.0 else None


def _safe_page(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def _safe_int(value: object, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(cast(Any, value))
    except (TypeError, ValueError, OverflowError):
        return default


def _text(value: object, limit: int = _MAX_TEXT_LENGTH) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return ""
    try:
        return str(value).strip()[:limit]
    except Exception:
        return ""


def _bounded_text(value: object, limit: int, default: str = "") -> str:
    if not isinstance(value, str):
        return default
    rendered = value.strip()
    if not rendered or any(ord(char) < 32 or ord(char) == 127 for char in rendered):
        return default
    return rendered[:limit]


def _safe_metadata_text(value: object, limit: int, default: str) -> str:
    rendered = _bounded_text(value, limit, default)
    lowered = rendered.casefold()
    if (
        re.search(r"(^|[\\/])[a-z]:[\\/]", rendered, re.IGNORECASE)
        or rendered.startswith(("\\\\", "//"))
        or lowered.startswith(("file:", "http:", "https:"))
    ):
        return default
    return rendered


def _safe_provider_response_reference(value: object) -> str:
    if value == "":
        return ""
    if not isinstance(value, str) or len(value) > _MAX_PROVIDER_RESPONSE_ID_LENGTH:
        return ""
    return value if _PROVIDER_RESPONSE_REF_PATTERN.fullmatch(value) is not None else ""


def _safe_source_value(value: object, limit: int, default: str = "") -> str:
    rendered = _bounded_text(value, limit, default)
    lowered = rendered.casefold()
    if (
        re.match(r"^[A-Za-z]:", rendered) is not None
        or "/" in rendered
        or "\\" in rendered
        or "://" in rendered
        or lowered.startswith(("file:", "http:", "https:", "data:", "javascript:"))
    ):
        return default
    return rendered


def _safe_document_type(value: object) -> str:
    rendered = _safe_source_value(value, _MAX_DOCUMENT_TYPE_LENGTH, "unknown").lstrip(".")
    return (
        rendered.lower()
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,79}", rendered)
        else "unknown"
    )


def _safe_display_name(value: object) -> str:
    rendered = _bounded_text(value, _MAX_TEXT_LENGTH, "unknown")
    basename = re.split(r"[\\/]", rendered)[-1]
    basename = _bounded_text(basename, _MAX_DISPLAY_NAME_LENGTH, "unknown")
    if _UNSAFE_SOURCE_DISPLAY_NAME_PATTERN.search(basename) or _has_unsafe_source_metadata(
        basename
    ):
        return "unknown"
    return basename


def _safe_verification_status(value: object) -> str:
    rendered = _bounded_text(value, _MAX_STATUS_LENGTH, "unknown")
    if _SOURCE_STATUS_PATTERN.fullmatch(rendered) is None or _has_unsafe_source_metadata(rendered):
        return "unknown"
    return rendered


def _has_unsafe_source_metadata(value: str) -> bool:
    lowered = value.casefold()
    words = {word for word in re.split(r"[^\w]+", lowered) if word}
    return bool(words & _UNSAFE_SOURCE_METADATA_WORDS)


def _known_timezone_aware(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "unknown"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return "unknown"
    if parsed.tzinfo is None:
        return "unknown"
    return parsed.isoformat(timespec="seconds")


def _required_timezone_aware(value: object) -> str:
    rendered = _known_timezone_aware(value)
    if rendered == "unknown":
        raise ValueError("created_at must be a timezone-aware ISO timestamp")
    return rendered


def _timezone_aware(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value) if value else datetime.now(timezone.utc)
    except (TypeError, ValueError):
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat(timespec="seconds")


__all__ = [
    "AI_ANALYSIS_SCHEMA_VERSION",
    "AiApplicationRequirementsStatus",
    "AiAnalysisStatus",
    "AiAnalysisProvenance",
    "AiDocument",
    "AiDocumentAnalysis",
    "AiDraftContractAnalysis",
    "AiDraftContractStatus",
    "AiEvidence",
    "AiEvidenceVerificationMethod",
    "AiFinding",
    "AiFindingStatus",
    "AiLegalReviewPriority",
    "AiLegalRiskAssessment",
    "AiLegalRiskCategory",
    "AiLegalRiskItem",
    "AiLegalRiskSourceRef",
    "AiLegalRiskStatus",
    "AiTechnicalSpecificationAnalysis",
    "AiTechnicalSpecificationStatus",
    "AiSourceSnapshot",
    "TenderRequirements",
    "_APPLICATION_REQUIREMENTS_FINDING_FIELDS",
]
