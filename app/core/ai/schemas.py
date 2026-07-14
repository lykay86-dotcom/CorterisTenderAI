"""Evidence-first, failure-safe contracts for Tender Intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import math
import re
from typing import Any, Mapping, cast


AI_ANALYSIS_SCHEMA_VERSION = 2
_MAX_TEXT_LENGTH = 12_000
_CITATION_ID_PATTERN = re.compile(r"cit_[0-9a-f]{32}")
_SOURCE_REF_PATTERN = re.compile(r"doc_[0-9a-f]{32}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}", re.IGNORECASE)


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


class AiEvidenceVerificationMethod(StrEnum):
    EXACT_QUOTE = "exact_quote"


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
class TenderRequirements:
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

        return {
            "payload_version": self.payload_version,
            "registry_key": self.registry_key,
            "summary": self.summary,
            "requirements": {
                name: [finding(item) for item in getattr(self.requirements, name)]
                for name in TenderRequirements.__dataclass_fields__
            },
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

    @classmethod
    def from_payload(cls, payload: object) -> "AiDocumentAnalysis":
        """Deserialize without allowing damaged values to become verified."""
        if not isinstance(payload, Mapping):
            return cls("", "", status=AiAnalysisStatus.INVALID_RESPONSE)

        version = _safe_int(payload.get("payload_version"), default=1)
        registry_key = _text(payload.get("registry_key"))
        if version < 1 or version > AI_ANALYSIS_SCHEMA_VERSION:
            return cls(
                registry_key,
                "",
                status=AiAnalysisStatus.CACHE_INCOMPATIBLE,
                payload_version=version,
                warnings=("Сохранённый AI-анализ имеет несовместимую версию.",),
            )

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
                    if requested_verified and evidence is not None
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
        requirement_map = raw_requirements if isinstance(raw_requirements, Mapping) else {}
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
        return cls(
            registry_key=registry_key,
            summary=_text(payload.get("summary"), _MAX_TEXT_LENGTH),
            requirements=TenderRequirements(
                **{
                    name: findings(requirement_map.get(name, []))
                    for name in TenderRequirements.__dataclass_fields__
                }
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
    "AiAnalysisStatus",
    "AiDocument",
    "AiDocumentAnalysis",
    "AiEvidence",
    "AiEvidenceVerificationMethod",
    "AiFinding",
    "AiFindingStatus",
    "TenderRequirements",
]
