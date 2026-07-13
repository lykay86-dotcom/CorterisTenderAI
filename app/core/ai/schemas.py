"""Evidence-first, failure-safe contracts for Tender Intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import math
from typing import Mapping


AI_ANALYSIS_SCHEMA_VERSION = 2
_MAX_TEXT_LENGTH = 12_000


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
    document_id: str
    quote: str
    section: str = ""
    page: int | None = None
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be a finite number between 0 and 1")


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
                        "document_id": item.evidence.document_id,
                        "quote": item.evidence.quote,
                        "section": item.evidence.section,
                        "page": item.evidence.page,
                        "confidence": item.evidence.confidence,
                    }
                    if item.evidence else None
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
            "status": self.status.value,
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
            tuple(
                text
                for item in raw_missing
                if (text := _text(item, 1_000))
            )
            if isinstance(raw_missing, (list, tuple))
            else ()
        )
        raw_warnings = payload.get("warnings", ())
        warnings = (
            tuple(
                text
                for item in raw_warnings
                if (text := _text(item, 1_000))
            )
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
    document_id = _text(value.get("document_id"), 500)
    quote = _text(value.get("quote"), 8_000)
    confidence = _safe_confidence(value.get("confidence"))
    page = _safe_page(value.get("page"))
    if not document_id or not quote or confidence is None:
        return None
    return AiEvidence(
        document_id=document_id,
        quote=quote,
        section=_text(value.get("section"), 1_000),
        page=page,
        confidence=confidence,
    )


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
        return int(value)
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
    "AiFinding",
    "AiFindingStatus",
    "TenderRequirements",
]
