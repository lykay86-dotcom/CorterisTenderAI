"""Strict, evidence-first contracts for RM-109."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


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

