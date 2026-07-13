"""Evidence-backed C16 stop-factor decisions made before participation scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
import hashlib
import re
from typing import Iterable

from app.tenders.collector.company_capability import CompanyCapabilityProfile
from app.tenders.corteris_filter import normalize_text
from app.tenders.models import UnifiedTender, is_timezone_aware
from app.tenders.requirement_analysis import (
    FindingSeverity,
    RequirementFinding,
    TenderRequirementAnalysis,
)


class StopFactorStatus(StrEnum):
    CLEAR = "clear"
    CONDITIONAL = "conditional"
    DATA_INSUFFICIENT = "data_insufficient"
    BLOCKED_BY_REQUIREMENT = "blocked_by_requirement"


class StopFactorKind(StrEnum):
    DEADLINE_EXPIRED = "deadline_expired"
    DEADLINE_TIMEZONE_UNKNOWN = "deadline_timezone_unknown"
    COMPANY_PROFILE_INCOMPLETE = "company_profile_incomplete"
    REQUIREMENTS_UNVERIFIED = "requirements_unverified"
    REQUIRED_LICENSE_MISSING = "required_license_missing"
    REQUIRED_SRO_MISSING = "required_sro_missing"
    REQUIRED_EXPERIENCE_UNCONFIRMED = "required_experience_unconfirmed"
    SECURITY_CAPACITY_EXCEEDED = "security_capacity_exceeded"
    REQUIREMENT_BLOCK = "requirement_block"
    DOCUMENTS_MISSING = "documents_missing"
    DIRECTION_MISMATCH = "direction_mismatch"


@dataclass(frozen=True, slots=True)
class StopFactorEvidence:
    document: str
    page: str
    section: str
    quote: str
    confidence: float
    remediation: str

    def __post_init__(self) -> None:
        for field_name in ("document", "page", "section", "quote", "remediation"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def to_payload(self) -> dict[str, object]:
        return {
            "document": self.document,
            "page": self.page,
            "section": self.section,
            "quote": self.quote,
            "confidence": self.confidence,
            "remediation": self.remediation,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "StopFactorEvidence":
        return cls(
            document=str(payload.get("document", "")),
            page=str(payload.get("page", "")),
            section=str(payload.get("section", "")),
            quote=str(payload.get("quote", "")),
            confidence=float(payload.get("confidence", 0.0)),
            remediation=str(payload.get("remediation", "")),
        )


@dataclass(frozen=True, slots=True)
class StopFactor:
    factor_id: str
    kind: StopFactorKind
    status: StopFactorStatus
    title: str
    description: str
    criticality: str
    evidence: StopFactorEvidence

    def __post_init__(self) -> None:
        if not self.factor_id.strip() or not self.title.strip():
            raise ValueError("factor_id and title must not be empty")
        if self.status == StopFactorStatus.CLEAR:
            raise ValueError("a stop factor cannot have CLEAR status")

    def to_payload(self) -> dict[str, object]:
        return {
            "factor_id": self.factor_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "criticality": self.criticality,
            "evidence": self.evidence.to_payload(),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "StopFactor":
        raw_evidence = payload.get("evidence", {})
        return cls(
            factor_id=str(payload.get("factor_id", "")),
            kind=StopFactorKind(str(payload.get("kind", "requirements_unverified"))),
            status=StopFactorStatus(str(payload.get("status", "data_insufficient"))),
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            criticality=str(payload.get("criticality", "")),
            evidence=StopFactorEvidence.from_payload(
                dict(raw_evidence) if isinstance(raw_evidence, dict) else {}
            ),
        )


@dataclass(frozen=True, slots=True)
class StopFactorAssessment:
    registry_key: str
    status: StopFactorStatus
    factors: tuple[StopFactor, ...]
    evaluated_at: str
    input_fingerprint: str

    def __post_init__(self) -> None:
        if not self.registry_key.strip() or not self.input_fingerprint.strip():
            raise ValueError("registry_key and input_fingerprint must not be empty")
        expected = _status_for_factors(self.factors)
        if self.status != expected:
            raise ValueError("assessment status does not match its factors")

    @property
    def blocks_participation(self) -> bool:
        return self.status == StopFactorStatus.BLOCKED_BY_REQUIREMENT

    def to_payload(self) -> dict[str, object]:
        return {
            "registry_key": self.registry_key,
            "status": self.status.value,
            "factors": [item.to_payload() for item in self.factors],
            "evaluated_at": self.evaluated_at,
            "input_fingerprint": self.input_fingerprint,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "StopFactorAssessment":
        raw_factors = payload.get("factors", ())
        return cls(
            registry_key=str(payload.get("registry_key", "")),
            status=StopFactorStatus(str(payload.get("status", "clear"))),
            factors=tuple(
                StopFactor.from_payload(dict(item))
                for item in raw_factors
                if isinstance(item, dict)
            )
            if isinstance(raw_factors, (list, tuple))
            else (),
            evaluated_at=str(payload.get("evaluated_at", "")),
            input_fingerprint=str(payload.get("input_fingerprint", "")),
        )


class StopFactorEngine:
    """Evaluate hard gates without allowing a score to override them."""

    def __init__(self, profile: CompanyCapabilityProfile | None = None) -> None:
        self.profile = profile or CompanyCapabilityProfile()

    def evaluate(
        self,
        registry_key: str,
        tender: UnifiedTender,
        *,
        analysis: TenderRequirementAnalysis | None = None,
        now: datetime | None = None,
    ) -> StopFactorAssessment:
        moment = now or datetime.now(timezone.utc)
        if not is_timezone_aware(moment):
            raise ValueError("Stop-factor evaluation time must be timezone-aware")
        moment = moment.astimezone(timezone.utc)
        factors: list[StopFactor] = []

        deadline = tender.application_deadline
        if deadline is not None and not is_timezone_aware(deadline):
            factors.append(
                self._factor(
                    StopFactorKind.DEADLINE_TIMEZONE_UNKNOWN,
                    StopFactorStatus.DATA_INSUFFICIENT,
                    "Часовой пояс срока подачи не подтверждён",
                    "Срок нельзя безопасно сравнить с текущим временем без часового пояса.",
                    "high",
                    _card_evidence(
                        "Срок подачи заявки",
                        deadline.isoformat(),
                        1.0,
                        "Проверить часовой пояс в последней официальной редакции извещения.",
                    ),
                )
            )
        elif deadline is not None and deadline.astimezone(timezone.utc) <= moment:
            factors.append(
                self._factor(
                    StopFactorKind.DEADLINE_EXPIRED,
                    StopFactorStatus.BLOCKED_BY_REQUIREMENT,
                    "Срок подачи заявки истёк",
                    "Подать заявку после официального срока невозможно.",
                    "critical",
                    _card_evidence(
                        "Срок подачи заявки",
                        deadline.isoformat(),
                        1.0,
                        "Проверить последнюю официальную редакцию извещения; участвовать можно только при продлении срока.",
                    ),
                )
            )

        if not self.profile.is_configured:
            missing = ", ".join(self.profile.missing_sections) or "профиль не подтверждён"
            factors.append(
                self._factor(
                    StopFactorKind.COMPANY_PROFILE_INCOMPLETE,
                    StopFactorStatus.DATA_INSUFFICIENT,
                    "Недостаточно данных о возможностях компании",
                    missing,
                    "high",
                    StopFactorEvidence(
                        document="Профиль возможностей компании",
                        page="не применимо",
                        section="Обязательные разделы",
                        quote=missing,
                        confidence=1.0,
                        remediation="Заполнить и явно подтвердить профиль компании в интерфейсе.",
                    ),
                )
            )

        if analysis is None:
            factors.append(
                self._factor(
                    StopFactorKind.REQUIREMENTS_UNVERIFIED,
                    StopFactorStatus.DATA_INSUFFICIENT,
                    "Критические требования не проверены",
                    "Нет структурированного анализа локальных документов закупки.",
                    "high",
                    StopFactorEvidence(
                        document="Комплект документов закупки",
                        page="не определена",
                        section="Требования к участнику",
                        quote="Структурированный анализ требований отсутствует.",
                        confidence=1.0,
                        remediation="Скачать документы из официального источника и выполнить полный анализ требований.",
                    ),
                )
            )
        else:
            factors.extend(self._analysis_factors(analysis, tender))

        profile_terms = normalize_text(
            " ".join(
                (
                    *self.profile.business_directions,
                    *self.profile.self_performed_directions,
                    *self.profile.subcontracted_directions,
                )
            )
        )
        if self.profile.is_configured and profile_terms:
            tender_text = normalize_text(f"{tender.title} {tender.description}")
            if tender_text and not any(
                normalize_text(term) in tender_text
                for term in self.profile.business_directions
                if normalize_text(term)
            ):
                factors.append(
                    self._factor(
                        StopFactorKind.DIRECTION_MISMATCH,
                        StopFactorStatus.CONDITIONAL,
                        "Направление закупки не подтверждено профилем",
                        "Предмет закупки не совпал с подтверждёнными направлениями компании.",
                        "medium",
                        _card_evidence(
                            "Предмет закупки",
                            tender.title or "Наименование отсутствует",
                            0.75,
                            "Подтвердить применимое направление или возможность привлечения субподрядчика.",
                        ),
                    )
                )

        ordered = _deduplicate(factors)
        fingerprint = hashlib.sha256(
            repr(
                (
                    registry_key,
                    tender.application_deadline,
                    analysis.source_fingerprint if analysis else "",
                    self.profile.to_dict(),
                )
            ).encode("utf-8")
        ).hexdigest()
        return StopFactorAssessment(
            registry_key=registry_key,
            status=_status_for_factors(ordered),
            factors=ordered,
            evaluated_at=moment.isoformat(timespec="seconds"),
            input_fingerprint=fingerprint,
        )

    def _analysis_factors(
        self,
        analysis: TenderRequirementAnalysis,
        tender: UnifiedTender,
    ) -> tuple[StopFactor, ...]:
        result: list[StopFactor] = []
        capabilities = normalize_text(
            " ".join(
                (
                    *self.profile.licenses,
                    *self.profile.license_work_types,
                    *self.profile.sro_memberships,
                )
            )
        )
        for finding in analysis.stop_factors:
            required = _required_capability(finding.pattern_key)
            if required and required in capabilities:
                continue
            kind = (
                StopFactorKind.REQUIRED_SRO_MISSING
                if "sro" in finding.pattern_key
                else StopFactorKind.REQUIRED_LICENSE_MISSING
                if "license" in finding.pattern_key or "mchs" in finding.pattern_key
                else StopFactorKind.REQUIREMENT_BLOCK
            )
            result.append(
                self._from_finding(
                    finding,
                    kind,
                    StopFactorStatus.BLOCKED_BY_REQUIREMENT,
                    "Подтвердить соответствие требованию документом либо отказаться от участия.",
                )
            )

        for finding in analysis.license_requirements:
            required = _required_capability(finding.pattern_key)
            if not required or required not in capabilities:
                status = (
                    StopFactorStatus.BLOCKED_BY_REQUIREMENT
                    if finding.severity == FindingSeverity.CRITICAL
                    else StopFactorStatus.CONDITIONAL
                )
                result.append(
                    self._from_finding(
                        finding,
                        StopFactorKind.REQUIRED_SRO_MISSING
                        if "sro" in finding.pattern_key
                        else StopFactorKind.REQUIRED_LICENSE_MISSING,
                        status,
                        "Добавить подтверждающий документ в профиль или проверить допустимость привлечения партнёра.",
                    )
                )

        if analysis.experience_requirements:
            for finding in analysis.experience_requirements:
                confirmed = bool(self.profile.confirmed_experience)
                result.append(
                    self._from_finding(
                        finding,
                        StopFactorKind.REQUIRED_EXPERIENCE_UNCONFIRMED,
                        StopFactorStatus.CONDITIONAL,
                        (
                            "Сопоставить требование с подтверждённым опытом и приложить документы исполнения."
                            if confirmed
                            else "Добавить исполненные контракты в профиль и приложить подтверждение опыта."
                        ),
                    )
                )

        for finding in analysis.security_requirements:
            limit = (
                self.profile.max_bid_security
                if finding.pattern_key == "application_security"
                else self.profile.max_contract_security
            )
            required_amount = _security_amount(finding.value, tender)
            if required_amount is not None and limit is not None and required_amount > limit:
                factor = self._from_finding(
                    finding,
                    StopFactorKind.SECURITY_CAPACITY_EXCEEDED,
                    StopFactorStatus.BLOCKED_BY_REQUIREMENT,
                    "Увеличить подтверждённый лимит обеспечения или получить банковскую гарантию.",
                )
                result.append(
                    StopFactor(
                        factor.factor_id,
                        factor.kind,
                        factor.status,
                        factor.title,
                        f"Требуется {required_amount}; подтверждённый лимит {limit}.",
                        factor.criticality,
                        factor.evidence,
                    )
                )
            elif required_amount is not None and limit is None:
                result.append(
                    self._from_finding(
                        finding,
                        StopFactorKind.SECURITY_CAPACITY_EXCEEDED,
                        StopFactorStatus.DATA_INSUFFICIENT,
                        "Указать подтверждённый лимит обеспечения в профиле компании.",
                    )
                )

        if analysis.missing_documents:
            missing = ", ".join(analysis.missing_documents)
            result.append(
                self._factor(
                    StopFactorKind.DOCUMENTS_MISSING,
                    StopFactorStatus.DATA_INSUFFICIENT,
                    "Комплект документов неполный",
                    missing,
                    "high",
                    StopFactorEvidence(
                        document="Комплект документов закупки",
                        page="не определена",
                        section="Полнота комплекта",
                        quote=missing,
                        confidence=1.0,
                        remediation="Получить недостающие документы из официального источника и повторить анализ.",
                    ),
                )
            )
        return _deduplicate(result)

    def _from_finding(
        self,
        finding: RequirementFinding,
        kind: StopFactorKind,
        status: StopFactorStatus,
        remediation: str,
    ) -> StopFactor:
        return self._factor(
            kind,
            status,
            finding.title,
            finding.value or finding.snippet,
            finding.severity.value,
            StopFactorEvidence(
                document=finding.source_name,
                page=_page_from_snippet(finding.snippet),
                section=finding.category.value,
                quote=finding.snippet or finding.value,
                confidence=finding.confidence,
                remediation=remediation,
            ),
        )

    @staticmethod
    def _factor(
        kind: StopFactorKind,
        status: StopFactorStatus,
        title: str,
        description: str,
        criticality: str,
        evidence: StopFactorEvidence,
    ) -> StopFactor:
        identity = hashlib.sha256(
            repr((kind.value, status.value, title, evidence.document, evidence.quote)).encode(
                "utf-8"
            )
        ).hexdigest()[:24]
        return StopFactor(identity, kind, status, title, description, criticality, evidence)


def _card_evidence(
    section: str, quote: str, confidence: float, remediation: str
) -> StopFactorEvidence:
    return StopFactorEvidence(
        "Карточка закупки", "не применимо", section, quote, confidence, remediation
    )


def _page_from_snippet(snippet: str) -> str:
    match = re.search(r"(?:стр(?:аница)?\.?|page)\s*(\d{1,4})", snippet, re.IGNORECASE)
    return match.group(1) if match else "не определена (текстовый слой)"


def _required_capability(pattern_key: str) -> str:
    return {
        "license_mchs": "мчс",
        "mandatory_mchs": "мчс",
        "license_fsb": "фсб",
        "sro_membership": "сро",
        "mandatory_sro": "сро",
    }.get(pattern_key, "")


def _security_amount(value: str, tender: UnifiedTender) -> Decimal | None:
    rendered = value.replace("\xa0", " ").strip()
    percent = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*%", rendered)
    if percent and tender.price is not None:
        ratio = Decimal(percent.group(1).replace(",", ".")) / Decimal("100")
        return (tender.price.amount * ratio).quantize(Decimal("0.01"))
    money = re.search(r"(\d[\d\s]*(?:[.,]\d+)?)\s*(?:руб|₽)", rendered, re.IGNORECASE)
    if money:
        return Decimal(money.group(1).replace(" ", "").replace(",", "."))
    return None


def _status_for_factors(factors: Iterable[StopFactor]) -> StopFactorStatus:
    statuses = {item.status for item in factors}
    for status in (
        StopFactorStatus.BLOCKED_BY_REQUIREMENT,
        StopFactorStatus.DATA_INSUFFICIENT,
        StopFactorStatus.CONDITIONAL,
    ):
        if status in statuses:
            return status
    return StopFactorStatus.CLEAR


def _deduplicate(factors: Iterable[StopFactor]) -> tuple[StopFactor, ...]:
    result: list[StopFactor] = []
    seen: set[tuple[StopFactorKind, str, str]] = set()
    for item in factors:
        key = (item.kind, item.evidence.document.casefold(), item.evidence.quote.casefold())
        if key not in seen:
            seen.add(key)
            result.append(item)
    return tuple(result)


__all__ = [
    "StopFactor",
    "StopFactorAssessment",
    "StopFactorEngine",
    "StopFactorEvidence",
    "StopFactorKind",
    "StopFactorStatus",
]
