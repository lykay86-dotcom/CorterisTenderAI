"""Explainable participation scoring for ООО «КОРТЕРИС» tenders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
from typing import TYPE_CHECKING, Iterable, Mapping, Sequence

if TYPE_CHECKING:
    from app.tenders.collector.company_capability import CompanyCapabilityProfile

from app.tenders.corteris_filter import (
    CorterisTenderClassifier,
    normalize_text,
)
from app.tenders.collector.currency import (
    CurrencyRateUnavailableError,
    ExchangeRateBook,
)
from app.tenders.collector.stop_factor import (
    StopFactorAssessment,
    StopFactorStatus,
)
from app.tenders.models import UnifiedTender, normalize_currency_code
from app.tenders.requirement_analysis import (
    FindingSeverity,
    TenderRequirementAnalysis,
)


class ParticipationRecommendation(StrEnum):
    RECOMMENDED = "recommended"
    MANUAL_REVIEW = "manual_review"
    POSSIBLE_WITH_CONDITIONS = "possible_with_conditions"
    NOT_RECOMMENDED = "not_recommended"


@dataclass(frozen=True, slots=True)
class ParticipationScoreComponent:
    key: str
    title: str
    score: int
    maximum: int
    explanation: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("component key must not be empty")
        if self.maximum < 0:
            raise ValueError("component maximum must be non-negative")
        if self.score > self.maximum:
            raise ValueError("component score exceeds maximum")
        if self.maximum == 0 and self.score > 0:
            raise ValueError("risk component cannot be positive")


@dataclass(frozen=True, slots=True)
class CorterisParticipationScore:
    total_score: int
    recommendation: ParticipationRecommendation
    recommendation_text: str
    components: tuple[ParticipationScoreComponent, ...]
    positive_factors: tuple[str, ...]
    negative_factors: tuple[str, ...]
    matched_keywords: tuple[str, ...]
    matched_okpd2: tuple[str, ...]
    stop_factors: tuple[str, ...]
    missing_documents: tuple[str, ...]
    directions: tuple[str, ...]
    hard_excluded: bool
    scored_at: str
    profile_version: str
    input_fingerprint: str
    evidence_sources: tuple[str, ...] = ()
    stop_factor_assessment: StopFactorAssessment | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.total_score <= 100:
            raise ValueError("total_score must be between 0 and 100")
        if not self.input_fingerprint.strip():
            raise ValueError("input_fingerprint must not be empty")

    @property
    def accepted_for_registry(self) -> bool:
        return (
            not self.hard_excluded
            and (
                self.stop_factor_assessment is None
                or not self.stop_factor_assessment.blocks_participation
            )
            and self.recommendation
            != ParticipationRecommendation.NOT_RECOMMENDED
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "total_score": self.total_score,
            "recommendation": self.recommendation.value,
            "recommendation_text": self.recommendation_text,
            "components": [
                {
                    "key": item.key,
                    "title": item.title,
                    "score": item.score,
                    "maximum": item.maximum,
                    "explanation": item.explanation,
                }
                for item in self.components
            ],
            "positive_factors": list(self.positive_factors),
            "negative_factors": list(self.negative_factors),
            "matched_keywords": list(self.matched_keywords),
            "matched_okpd2": list(self.matched_okpd2),
            "stop_factors": list(self.stop_factors),
            "missing_documents": list(self.missing_documents),
            "directions": list(self.directions),
            "hard_excluded": self.hard_excluded,
            "scored_at": self.scored_at,
            "profile_version": self.profile_version,
            "input_fingerprint": self.input_fingerprint,
            "evidence_sources": list(self.evidence_sources),
            "stop_factor_assessment": (
                self.stop_factor_assessment.to_payload()
                if self.stop_factor_assessment is not None
                else None
            ),
        }

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, object],
    ) -> "CorterisParticipationScore":
        raw_components = payload.get("components", ())
        components: list[ParticipationScoreComponent] = []
        if isinstance(raw_components, (list, tuple)):
            for raw in raw_components:
                if not isinstance(raw, Mapping):
                    continue
                components.append(
                    ParticipationScoreComponent(
                        key=str(raw.get("key", "")),
                        title=str(raw.get("title", "")),
                        score=int(raw.get("score", 0)),
                        maximum=int(raw.get("maximum", 0)),
                        explanation=str(raw.get("explanation", "")),
                    )
                )
        raw_stop_assessment = payload.get("stop_factor_assessment")
        return cls(
            total_score=int(payload.get("total_score", 0)),
            recommendation=ParticipationRecommendation(
                str(
                    payload.get(
                        "recommendation",
                        ParticipationRecommendation.NOT_RECOMMENDED.value,
                    )
                )
            ),
            recommendation_text=str(
                payload.get("recommendation_text", "")
            ),
            components=tuple(components),
            positive_factors=_string_tuple(
                payload.get("positive_factors", ())
            ),
            negative_factors=_string_tuple(
                payload.get("negative_factors", ())
            ),
            matched_keywords=_string_tuple(
                payload.get("matched_keywords", ())
            ),
            matched_okpd2=_string_tuple(
                payload.get("matched_okpd2", ())
            ),
            stop_factors=_string_tuple(
                payload.get("stop_factors", ())
            ),
            missing_documents=_string_tuple(
                payload.get("missing_documents", ())
            ),
            directions=_string_tuple(payload.get("directions", ())),
            hard_excluded=bool(payload.get("hard_excluded", False)),
            scored_at=str(payload.get("scored_at", "")),
            profile_version=str(payload.get("profile_version", "")),
            input_fingerprint=str(
                payload.get("input_fingerprint", "")
            ),
            evidence_sources=_string_tuple(
                payload.get("evidence_sources", ())
            ),
            stop_factor_assessment=(
                StopFactorAssessment.from_payload(dict(raw_stop_assessment))
                if isinstance(raw_stop_assessment, Mapping)
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class CorterisCompanyProfile:
    """Scoring projection of the editable capability profile."""

    version: str = "corteris-security-v1"
    priority_regions: tuple[str, ...] = (
        "москва",
        "московская область",
        "санкт петербург",
        "ленинградская область",
    )
    nationwide_regions: tuple[str, ...] = (
        "российская федерация",
        "вся россия",
        "россия",
    )
    preferred_price_min: Decimal = Decimal("100000")
    preferred_price_max: Decimal = Decimal("30000000")
    extended_price_max: Decimal = Decimal("80000000")
    price_currency: str = "RUB"
    known_licenses: tuple[str, ...] = ()
    equipment_terms: tuple[str, ...] = (
        "trassir",
        "трассир",
        "hikvision",
        "dahua",
        "entercam",
        "doorhan",
        "болид",
        "рубеж",
        "стрелец",
        "ip камера",
        "видеорегистратор",
        "контроллер доступа",
        "считыватель",
        "турникет",
        "шлагбаум",
        "пожарный извещатель",
    )
    okpd2_prefixes: tuple[str, ...] = (
        "26.30",
        "26.40.33",
        "27.90.70",
        "33.13",
        "43.21",
        "71.12",
        "80.20",
    )
    configured: bool = True
    missing_capability_fields: tuple[str, ...] = ()
    business_directions: tuple[str, ...] = ()
    confirmed_experience: tuple[str, ...] = ()
    financial_confirmed: bool = True
    strict_capabilities: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "price_currency",
            normalize_currency_code(self.price_currency),
        )
        if not self.version.strip():
            raise ValueError("profile version must not be empty")
        if self.preferred_price_min < 0:
            raise ValueError("preferred_price_min must be non-negative")
        if self.preferred_price_max < self.preferred_price_min:
            raise ValueError("invalid preferred price range")
        if self.extended_price_max < self.preferred_price_max:
            raise ValueError("invalid extended price range")

    @classmethod
    def from_capability(
        cls,
        capability: "CompanyCapabilityProfile",
    ) -> "CorterisCompanyProfile":
        max_project = capability.max_project_amount or Decimal("0")
        terms = _ordered_unique(
            (
                *capability.equipment,
                *capability.brands,
                *capability.suppliers,
                *capability.stock_items,
            )
        )
        licenses = _ordered_unique(
            (
                *capability.licenses,
                *capability.license_work_types,
                *capability.sro_memberships,
            )
        )
        return cls(
            version=(
                "company-capability:"
                + (capability.updated_at or capability.confirmed_at or "empty")
            ),
            priority_regions=_ordered_unique(
                (*capability.self_install_regions, *capability.partner_regions)
            ),
            nationwide_regions=(),
            preferred_price_min=Decimal("0"),
            preferred_price_max=max_project,
            extended_price_max=max_project,
            known_licenses=licenses,
            equipment_terms=terms,
            okpd2_prefixes=(),
            configured=capability.is_configured,
            missing_capability_fields=capability.missing_sections,
            business_directions=capability.business_directions,
            confirmed_experience=capability.confirmed_experience,
            financial_confirmed=(
                capability.max_project_amount is not None
                and capability.working_capital is not None
            ),
            strict_capabilities=True,
        )


@dataclass(frozen=True, slots=True)
class ParticipationScoringContext:
    document_texts: tuple[str, ...] = ()
    requirement_analysis: TenderRequirementAnalysis | None = None
    now: datetime | None = None
    evidence_sources: tuple[str, ...] = ()
    exchange_rates: ExchangeRateBook | None = None
    stop_factor_assessment: StopFactorAssessment | None = None

    @property
    def document_text(self) -> str:
        return "\n".join(
            item for item in self.document_texts if item.strip()
        )


DEFAULT_CORTERIS_COMPANY_PROFILE = CorterisCompanyProfile()

_SOFT_RISK_TERMS = (
    "общестроительные работы",
    "благоустройство территории",
    "комплекс работ по строительству",
    "работы по реконструкции здания",
    "субподряд",
    "поэтапная оплата",
    "оплата после ввода объекта",
)

_FINANCIAL_RISK_TERMS = (
    "без аванса",
    "аванс не предусмотрен",
    "казначейское сопровождение",
    "оплата в течение 60",
    "оплата в течение 90",
    "удержание",
)

_ADVANCE_TERMS = (
    "аванс предусмотрен",
    "предусмотрен аванс",
    "авансовый платеж",
)

_LICENSE_ALIASES = {
    "license_mchs": "МЧС",
    "license_fsb": "ФСБ",
    "sro_membership": "СРО",
    "general_license": "лицензия/разрешение",
}


class CorterisParticipationRanker:
    """Calculate a deterministic and explainable 0–100 score."""

    def __init__(
        self,
        profile: CorterisCompanyProfile = (
            DEFAULT_CORTERIS_COMPANY_PROFILE
        ),
        *,
        classifier: CorterisTenderClassifier | None = None,
    ) -> None:
        self.profile = profile
        self.classifier = classifier or CorterisTenderClassifier()

    def score(
        self,
        tender: UnifiedTender,
        context: ParticipationScoringContext | None = None,
    ) -> CorterisParticipationScore:
        context = context or ParticipationScoringContext()
        now = context.now or datetime.now().astimezone()
        relevance = self.classifier.evaluate(tender)

        metadata_text = " ".join(
            (
                tender.title,
                tender.description,
                tender.region,
                tender.customer.region,
                tender.customer.name,
                tender.law,
                " ".join(tender.tags),
                " ".join(tender.classification_codes),
            )
        )
        document_text = context.document_text
        normalized = normalize_text(
            f"{metadata_text}\n{document_text}"
        )

        hard_matches = relevance.matched_exclusion_terms
        hard_excluded = relevance.hard_excluded

        matched_keywords = _ordered_unique(
            (
                *relevance.matched_strong_terms,
                *relevance.matched_weak_terms,
                *relevance.matched_action_terms,
                *_document_keyword_matches(document_text),
            )
        )
        matched_okpd2 = _match_okpd2(
            tender.classification_codes,
            self.profile.okpd2_prefixes,
        )

        positive: list[str] = []
        negative: list[str] = []
        stop_factors: list[str] = []
        components: list[ParticipationScoreComponent] = []

        direction_score = _direction_score(relevance.score)
        direction_reason = (
            f"Базовая релевантность {relevance.score}/100; "
            f"направления: "
            f"{', '.join(item.value for item in relevance.directions) or 'не определены'}."
        )
        if self.profile.business_directions:
            matched_directions = _find_terms(
                normalized,
                self.profile.business_directions,
            )
            if not matched_directions:
                direction_score = 0
                direction_reason = (
                    "Предмет закупки не совпал с подтверждёнными "
                    "направлениями компании."
                )
            else:
                direction_reason += (
                    " Подтверждённые направления: "
                    + ", ".join(matched_directions)
                    + "."
                )
        elif self.profile.strict_capabilities and not self.profile.configured:
            direction_score = 0
            direction_reason = "Недостаточно данных о направлениях компании."
        components.append(
            ParticipationScoreComponent(
                "direction",
                "Соответствие направлениям Кортерис",
                direction_score,
                30,
                direction_reason,
            )
        )
        if direction_score:
            positive.append(
                "Предмет закупки соответствует направлениям Кортерис."
            )

        region_score, region_reason = self._region_score(tender)
        components.append(
            ParticipationScoreComponent(
                "region",
                "Регион",
                region_score,
                10,
                region_reason,
            )
        )
        if region_score >= 8:
            positive.append(region_reason)
        elif region_score <= 3:
            negative.append(region_reason)

        price_score, price_reason = self._price_score(
            tender,
            context=context,
            as_of=now.date(),
        )
        components.append(
            ParticipationScoreComponent(
                "price",
                "Подходящий диапазон НМЦК",
                price_score,
                10,
                price_reason,
            )
        )
        if price_score >= 8:
            positive.append(price_reason)
        elif price_score <= 3:
            negative.append(price_reason)

        equipment_matches = _find_terms(
            normalized,
            self.profile.equipment_terms,
        )
        equipment_score = min(
            15,
            len(equipment_matches) * 3
            + (3 if matched_okpd2 else 0),
        )
        equipment_reason = (
            "Найдены оборудование/бренды: "
            + ", ".join(equipment_matches[:8])
            if equipment_matches
            else "Конкретное оборудование из профиля Кортерис не найдено."
        )
        if matched_okpd2:
            equipment_reason += (
                "; совпадения ОКПД2: "
                + ", ".join(matched_okpd2)
            )
        if self.profile.strict_capabilities and not self.profile.configured:
            equipment_score = 0
            equipment_reason = (
                "Недостаточно данных об оборудовании и поставщиках компании."
            )
        components.append(
            ParticipationScoreComponent(
                "equipment",
                "Наличие оборудования в профиле",
                equipment_score,
                15,
                equipment_reason,
            )
        )
        if equipment_score >= 9:
            positive.append(equipment_reason)
        elif equipment_score == 0:
            negative.append(equipment_reason)

        experience_score, experience_reason = _experience_score(
            context.requirement_analysis,
            confirmed_experience=self.profile.confirmed_experience,
            profile_configured=self.profile.configured,
            strict_capabilities=self.profile.strict_capabilities,
        )
        components.append(
            ParticipationScoreComponent(
                "experience",
                "Соответствие опыту компании",
                experience_score,
                10,
                experience_reason,
            )
        )
        if experience_score <= 4:
            negative.append(experience_reason)

        license_score, license_reason, license_stops = (
            self._license_score(context.requirement_analysis)
        )
        components.append(
            ParticipationScoreComponent(
                "licenses",
                "Лицензии и допуски",
                license_score,
                10,
                license_reason,
            )
        )
        stop_factors.extend(license_stops)
        if license_score <= 4:
            negative.append(license_reason)

        financial_score, financial_reason = _financial_score(
            normalized,
            context.requirement_analysis,
            profile_configured=self.profile.configured,
            financial_confirmed=self.profile.financial_confirmed,
            strict_capabilities=self.profile.strict_capabilities,
        )
        components.append(
            ParticipationScoreComponent(
                "financial",
                "Финансовая привлекательность",
                financial_score,
                10,
                financial_reason,
            )
        )
        if financial_score >= 8:
            positive.append(financial_reason)
        elif financial_score <= 4:
            negative.append(financial_reason)

        preparation_score, preparation_reason = _preparation_score(
            tender,
            now,
        )
        components.append(
            ParticipationScoreComponent(
                "preparation",
                "Достаточный срок подготовки",
                preparation_score,
                5,
                preparation_reason,
            )
        )
        if preparation_score >= 4:
            positive.append(preparation_reason)
        elif preparation_score <= 1:
            negative.append(preparation_reason)

        missing_documents = _missing_documents(
            tender,
            context.requirement_analysis,
        )
        risk_score, risk_reason, risk_stops = _risk_score(
            normalized,
            context.requirement_analysis,
            missing_documents,
            hard_matches if hard_excluded else (),
        )
        components.append(
            ParticipationScoreComponent(
                "risks",
                "Договорные и финансовые риски",
                risk_score,
                0,
                risk_reason,
            )
        )
        if risk_score < 0:
            negative.append(risk_reason)
        stop_factors.extend(risk_stops)

        raw_total = sum(item.score for item in components)
        if hard_excluded:
            raw_total = 0
            stop_factors.extend(hard_matches)
            negative.append(
                "Обнаружено жёсткое непрофильное исключение."
            )
        total = max(0, min(100, raw_total))
        if self.profile.strict_capabilities and not self.profile.configured:
            negative.append(
                "Недостаточно данных о возможностях компании: "
                + ", ".join(
                    self.profile.missing_capability_fields
                    or ("профиль не заполнен",)
                )
                + "."
            )
            total = min(total, 64)
        structured_stop = context.stop_factor_assessment
        if structured_stop is not None:
            stop_factors.extend(item.title for item in structured_stop.factors)
        recommendation = _recommendation(total, hard_excluded)
        if structured_stop is not None:
            if structured_stop.status == StopFactorStatus.BLOCKED_BY_REQUIREMENT:
                recommendation = ParticipationRecommendation.NOT_RECOMMENDED
            elif structured_stop.status == StopFactorStatus.DATA_INSUFFICIENT:
                recommendation = ParticipationRecommendation.MANUAL_REVIEW
            elif structured_stop.status == StopFactorStatus.CONDITIONAL:
                recommendation = ParticipationRecommendation.POSSIBLE_WITH_CONDITIONS

        if missing_documents:
            negative.append(
                "Недостающие документы: "
                + ", ".join(missing_documents)
            )

        return CorterisParticipationScore(
            total_score=total,
            recommendation=recommendation,
            recommendation_text=_recommendation_text(
                recommendation
            ),
            components=tuple(components),
            positive_factors=_ordered_unique(positive),
            negative_factors=_ordered_unique(negative),
            matched_keywords=matched_keywords,
            matched_okpd2=matched_okpd2,
            stop_factors=_ordered_unique(stop_factors),
            missing_documents=missing_documents,
            directions=tuple(
                item.value for item in relevance.directions
            ),
            hard_excluded=hard_excluded,
            scored_at=now.isoformat(timespec="seconds"),
            profile_version=self.profile.version,
            input_fingerprint=_input_fingerprint(
                tender,
                context,
                self.profile.version,
            ),
            evidence_sources=_ordered_unique(
                context.evidence_sources
            ),
            stop_factor_assessment=structured_stop,
        )

    def _region_score(
        self,
        tender: UnifiedTender,
    ) -> tuple[int, str]:
        if self.profile.strict_capabilities and (not self.profile.configured or not (
            self.profile.priority_regions or self.profile.nationwide_regions
        )):
            return 4, "Недостаточно данных о регионах работы компании."
        raw_region = tender.region or tender.customer.region
        region = normalize_text(raw_region)
        if not region:
            return 4, "Регион не указан — требуется ручная проверка."
        if any(
            normalize_text(item) in region
            for item in self.profile.priority_regions
        ):
            return 10, f"Приоритетный регион: {raw_region}."
        if any(
            normalize_text(item) in region
            for item in self.profile.nationwide_regions
        ):
            return 7, "Закупка допускает выполнение по России."
        return 6, f"Регион вне основного приоритета: {raw_region}."

    def _price_score(
        self,
        tender: UnifiedTender,
        *,
        context: ParticipationScoringContext,
        as_of: date,
    ) -> tuple[int, str]:
        if tender.price is None:
            return 4, "НМЦК не указана — финансовая оценка неполная."
        if self.profile.strict_capabilities and (
            not self.profile.configured or not self.profile.financial_confirmed
        ):
            return 4, "Недостаточно данных о финансовых возможностях компании."
        conversion_note = ""
        amount = tender.price.amount
        if tender.price.currency != self.profile.price_currency:
            if context.exchange_rates is None:
                return (
                    4,
                    "НМЦК указана в валюте "
                    f"{tender.price.currency}; рабочий диапазон задан в "
                    f"{self.profile.price_currency}. Требуется ручной курс.",
                )
            try:
                conversion = context.exchange_rates.convert(
                    tender.price,
                    self.profile.price_currency,
                    as_of=as_of,
                )
            except CurrencyRateUnavailableError:
                return (
                    4,
                    "Для НМЦК в валюте "
                    f"{tender.price.currency} нет действующего "
                    "подтверждённого курса. Требуется ручная проверка.",
                )
            amount = conversion.converted.amount
            conversion_note = conversion.audit_text() + ". "
        if (
            self.profile.preferred_price_min
            <= amount
            <= self.profile.preferred_price_max
        ):
            return 10, (
                conversion_note
                + f"НМЦК {amount} входит в основной рабочий диапазон."
            )
        if amount < Decimal("50000"):
            return 2, (
                conversion_note
                + f"НМЦК {amount} слишком мала для типового проекта."
            )
        if amount < self.profile.preferred_price_min:
            return 6, (
                conversion_note
                + f"НМЦК {amount} ниже основного диапазона."
            )
        if amount <= self.profile.extended_price_max:
            return 6, (
                conversion_note
                + f"НМЦК {amount} требует оценки ресурсов и финансирования."
            )
        return 3, (
            conversion_note
            + f"НМЦК {amount} существенно выше типового диапазона."
        )

    def _license_score(
        self,
        analysis: TenderRequirementAnalysis | None,
    ) -> tuple[int, str, tuple[str, ...]]:
        if self.profile.strict_capabilities and not self.profile.configured:
            return 4, "Недостаточно данных о лицензиях и допусках компании.", ()
        if analysis is None:
            return (
                7,
                "Документация ещё не проверена на лицензии и допуски.",
                (),
            )
        findings = analysis.license_requirements
        if not findings:
            return 10, "Обязательные лицензии в анализе не выявлены.", ()

        required = _ordered_unique(
            _LICENSE_ALIASES.get(
                finding.pattern_key,
                finding.title,
            )
            for finding in findings
        )
        known = {
            normalize_text(item)
            for item in self.profile.known_licenses
        }
        unknown = tuple(
            item
            for item in required
            if normalize_text(item) not in known
        )
        critical = any(
            finding.severity == FindingSeverity.CRITICAL
            for finding in findings
        )
        if unknown:
            score = 1 if critical else 4
            return (
                score,
                "Требуется подтвердить допуски: "
                + ", ".join(unknown),
                tuple(
                    f"Не подтверждён допуск: {item}"
                    for item in unknown
                ),
            )
        return 9, "Требуемые допуски отмечены в профиле компании.", ()


def _direction_score(relevance_score: int) -> int:
    if relevance_score >= 80:
        return 30
    if relevance_score >= 65:
        return 27
    if relevance_score >= 45:
        return 23
    if relevance_score >= 24:
        return 16
    if relevance_score > 0:
        return 7
    return 0


def _experience_score(
    analysis: TenderRequirementAnalysis | None,
    *,
    confirmed_experience: tuple[str, ...] = (),
    profile_configured: bool = True,
    strict_capabilities: bool = False,
) -> tuple[int, str]:
    if strict_capabilities and (
        not profile_configured or not confirmed_experience
    ):
        return 4, "Недостаточно данных о подтверждённом опыте компании."
    if analysis is None:
        return 7, "Требования к опыту ещё не извлечены из документации."
    findings = analysis.experience_requirements
    if not findings:
        return 10, "Специальные требования к опыту не выявлены."
    if any(
        item.severity == FindingSeverity.CRITICAL
        for item in findings
    ):
        return 2, "Выявлены критические требования к подтверждённому опыту."
    if len(findings) >= 3:
        return 4, "Несколько требований к опыту требуют документальной проверки."
    return 6, "Есть требования к опыту; нужна проверка исполненных контрактов."


def _financial_score(
    text: str,
    analysis: TenderRequirementAnalysis | None,
    *,
    profile_configured: bool = True,
    financial_confirmed: bool = True,
    strict_capabilities: bool = False,
) -> tuple[int, str]:
    if strict_capabilities and (
        not profile_configured or not financial_confirmed
    ):
        return 4, "Недостаточно данных о финансовых возможностях компании."
    score = 6
    factors: list[str] = []
    advance = _find_terms(text, _ADVANCE_TERMS)
    risks = _find_terms(text, _FINANCIAL_RISK_TERMS)
    if advance:
        score += 2
        factors.append("предусмотрен аванс")
    if risks:
        score -= min(4, len(risks) * 2)
        factors.append("есть финансовые ограничения")
    if analysis is not None:
        security = analysis.security_requirements
        contract_risks = analysis.contract_risks
        score -= min(3, len(security))
        score -= min(3, len(contract_risks))
        if security:
            factors.append("есть обеспечение")
        if contract_risks:
            factors.append("есть договорные риски")
    score = max(0, min(10, score))
    if not factors:
        return score, "Финансовые условия требуют проверки проекта договора."
    return score, "Факторы: " + ", ".join(factors) + "."


def _preparation_score(
    tender: UnifiedTender,
    now: datetime,
) -> tuple[int, str]:
    deadline = tender.application_deadline
    if deadline is None:
        return 2, "Срок подачи не указан."
    reference = now
    if deadline.tzinfo is None and reference.tzinfo is not None:
        reference = reference.replace(tzinfo=None)
    elif deadline.tzinfo is not None and reference.tzinfo is None:
        reference = reference.astimezone()
    days = (deadline - reference).total_seconds() / 86400
    if days <= 0:
        return 0, "Срок подачи уже истёк."
    if days >= 10:
        return 5, f"До окончания подачи около {int(days)} дней."
    if days >= 7:
        return 4, f"До окончания подачи около {int(days)} дней."
    if days >= 4:
        return 2, f"На подготовку осталось около {int(days)} дней."
    return 0, f"На подготовку осталось менее {max(1, int(days) + 1)} дней."


def _risk_score(
    text: str,
    analysis: TenderRequirementAnalysis | None,
    missing_documents: tuple[str, ...],
    hard_matches: tuple[str, ...],
) -> tuple[int, str, tuple[str, ...]]:
    penalty = 0
    reasons: list[str] = []
    stops: list[str] = []

    soft = _find_terms(text, _SOFT_RISK_TERMS)
    if soft:
        penalty += min(8, len(soft) * 3)
        reasons.append("смешанный строительный объём")
    if missing_documents:
        penalty += min(4, len(missing_documents) * 2)
        reasons.append("неполная документация")
    if analysis is not None:
        if analysis.critical_count:
            penalty += min(10, analysis.critical_count * 5)
            reasons.append(
                f"критические требования: {analysis.critical_count}"
            )
            stops.extend(item.title for item in analysis.stop_factors)
        if analysis.warning_count:
            penalty += min(6, analysis.warning_count)
            reasons.append(
                f"предупреждения анализа: {analysis.warning_count}"
            )
    if hard_matches:
        penalty = 20
        reasons.append("жёсткое непрофильное исключение")
        stops.extend(hard_matches)

    penalty = min(20, penalty)
    if not reasons:
        return 0, "Явные договорные стоп-факторы пока не выявлены.", ()
    return (
        -penalty,
        "Риски: " + ", ".join(reasons) + f"; штраф {penalty} балл.",
        _ordered_unique(stops),
    )


def _missing_documents(
    tender: UnifiedTender,
    analysis: TenderRequirementAnalysis | None,
) -> tuple[str, ...]:
    if analysis is not None:
        return _ordered_unique(analysis.missing_documents)
    if tender.documents:
        return ()
    return (
        "Техническое задание / описание объекта закупки",
        "Проект контракта / договора",
    )


def _document_keyword_matches(value: str) -> tuple[str, ...]:
    if not value.strip():
        return ()
    normalized = normalize_text(value)
    return _find_terms(
        normalized,
        (
            "видеонаблюдение",
            "скуд",
            "контроль доступа",
            "пожарная сигнализация",
            "охранная сигнализация",
            "шлагбаум",
            "распознавание номеров",
            "соуэ",
            "слаботочные системы",
            "техническое обслуживание",
        ),
    )


def _match_okpd2(
    codes: Sequence[str],
    prefixes: Sequence[str],
) -> tuple[str, ...]:
    result: list[str] = []
    for code in codes:
        normalized = code.strip().replace(" ", "")
        if any(normalized.startswith(prefix) for prefix in prefixes):
            result.append(normalized)
    return _ordered_unique(result)


def _find_terms(
    normalized_text: str,
    terms: Sequence[str],
) -> tuple[str, ...]:
    if not normalized_text:
        return ()
    wrapped = f" {normalized_text} "
    result = []
    for term in terms:
        normalized = normalize_text(term)
        if normalized and f" {normalized} " in wrapped:
            result.append(term)
    return _ordered_unique(result)


def _recommendation(
    total: int,
    hard_excluded: bool,
) -> ParticipationRecommendation:
    if hard_excluded:
        return ParticipationRecommendation.NOT_RECOMMENDED
    if total >= 80:
        return ParticipationRecommendation.RECOMMENDED
    if total >= 65:
        return ParticipationRecommendation.MANUAL_REVIEW
    if total >= 45:
        return ParticipationRecommendation.POSSIBLE_WITH_CONDITIONS
    return ParticipationRecommendation.NOT_RECOMMENDED


def _recommendation_text(
    recommendation: ParticipationRecommendation,
) -> str:
    return {
        ParticipationRecommendation.RECOMMENDED: (
            "Рекомендуется участвовать"
        ),
        ParticipationRecommendation.MANUAL_REVIEW: (
            "Требуется ручная проверка"
        ),
        ParticipationRecommendation.POSSIBLE_WITH_CONDITIONS: (
            "Возможно участие при дополнительных условиях"
        ),
        ParticipationRecommendation.NOT_RECOMMENDED: (
            "Не рекомендуется"
        ),
    }[recommendation]


def _input_fingerprint(
    tender: UnifiedTender,
    context: ParticipationScoringContext,
    profile_version: str,
) -> str:
    analysis_fingerprint = (
        context.requirement_analysis.source_fingerprint
        if context.requirement_analysis is not None
        else ""
    )
    payload = {
        "identity": tender.identity_key,
        "number": tender.procurement_number,
        "title": tender.title,
        "description": tender.description,
        "region": tender.region,
        "price": (
            str(tender.price.amount)
            if tender.price is not None
            else ""
        ),
        "price_currency": (
            tender.price.currency
            if tender.price is not None
            else ""
        ),
        "deadline": (
            tender.application_deadline.isoformat()
            if tender.application_deadline is not None
            else ""
        ),
        "codes": list(tender.classification_codes),
        "tags": list(tender.tags),
        "documents": [
            (item.id, item.name, item.checksum_sha256)
            for item in tender.documents
        ],
        "document_text_hashes": [
            hashlib.sha256(item.encode("utf-8")).hexdigest()
            for item in context.document_texts
            if item
        ],
        "analysis": analysis_fingerprint,
        "exchange_rates": (
            context.exchange_rates.fingerprint
            if context.exchange_rates is not None
            else ""
        ),
        "stop_factor_assessment": (
            context.stop_factor_assessment.input_fingerprint
            if context.stop_factor_assessment is not None
            else ""
        ),
        "profile": profile_version,
    }
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        rendered = str(value).strip()
        identity = rendered.casefold()
        if not rendered or identity in seen:
            continue
        seen.add(identity)
        result.append(rendered)
    return tuple(result)


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(str(item) for item in value)


__all__ = [
    "CorterisCompanyProfile",
    "CorterisParticipationRanker",
    "CorterisParticipationScore",
    "DEFAULT_CORTERIS_COMPANY_PROFILE",
    "ParticipationRecommendation",
    "ParticipationScoreComponent",
    "ParticipationScoringContext",
]
