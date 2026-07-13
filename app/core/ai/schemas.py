"""Strict, evidence-first contracts for RM-109."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping


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


@dataclass(frozen=True, slots=True)
class AiEvidence:
    document_id: str
    quote: str
    section: str = ""
    page: int | None = None
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


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
    status: str = "partial"

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
            "status": self.status,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "AiDocumentAnalysis":
        def findings(value: object) -> tuple[AiFinding, ...]:
            result = []
            for item in value if isinstance(value, list) else ():
                if not isinstance(item, Mapping):
                    continue
                raw = item.get("evidence")
                evidence = AiEvidence(
                    document_id=str(raw.get("document_id", "")), quote=str(raw.get("quote", "")),
                    section=str(raw.get("section", "")), page=raw.get("page"),
                    confidence=float(raw.get("confidence", 0.0)),
                ) if isinstance(raw, Mapping) else None
                result.append(AiFinding(str(item.get("category", "")), str(item.get("statement", "")), evidence, AiFindingStatus(str(item.get("status", "unverified")))))
            return tuple(result)

        raw_requirements = payload.get("requirements", {})
        requirement_map = raw_requirements if isinstance(raw_requirements, Mapping) else {}
        return cls(
            registry_key=str(payload.get("registry_key", "")), summary=str(payload.get("summary", "")),
            requirements=TenderRequirements(**{name: findings(requirement_map.get(name, [])) for name in TenderRequirements.__dataclass_fields__}),
            risks=findings(payload.get("risks")), suspicious_conditions=findings(payload.get("suspicious_conditions")),
            contradictions=findings(payload.get("contradictions")),
            missing_documents=tuple(str(item) for item in payload.get("missing_documents", ()) if isinstance(payload.get("missing_documents"), (list, tuple))),
            final_ai_conclusion=str(payload.get("final_ai_conclusion", "")), status=str(payload.get("status", "partial")),
        )
