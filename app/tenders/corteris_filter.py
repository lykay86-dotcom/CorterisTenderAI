"""Corteris-specific tender classification, filtering and ranking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
import re
from typing import Iterable, Mapping, Sequence

from app.tenders.models import TenderStatus, UnifiedTender


class TenderDirection(StrEnum):
    VIDEO_SURVEILLANCE = "video_surveillance"
    OPS = "ops"
    SKUD = "skud"
    BARRIERS = "barriers"
    ANPR = "anpr"
    MAINTENANCE = "maintenance"
    INTEGRATED_SECURITY = "integrated_security"


class RelevanceGrade(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class DirectionRule:
    direction: TenderDirection
    strong_terms: tuple[str, ...]
    weak_terms: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CorterisSearchProfile:
    """Keyword and scoring profile for ООО «Кортерис»."""

    rules: tuple[DirectionRule, ...]
    action_terms: tuple[str, ...]
    hard_exclusion_terms: tuple[str, ...]
    minimum_score: int = 24
    medium_score: int = 40
    high_score: int = 65

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_score <= 100:
            raise ValueError("minimum_score must be between 0 and 100")
        if not (
            self.minimum_score
            <= self.medium_score
            <= self.high_score
            <= 100
        ):
            raise ValueError("Invalid relevance score thresholds")


@dataclass(frozen=True, slots=True)
class TenderRelevance:
    score: int
    grade: RelevanceGrade
    directions: tuple[TenderDirection, ...]
    matched_strong_terms: tuple[str, ...]
    matched_weak_terms: tuple[str, ...]
    matched_action_terms: tuple[str, ...]
    matched_exclusion_terms: tuple[str, ...]
    reasons: tuple[str, ...]
    hard_excluded: bool = False

    @property
    def relevant(self) -> bool:
        return (
            not self.hard_excluded
            and self.grade != RelevanceGrade.EXCLUDED
        )


@dataclass(frozen=True, slots=True)
class TenderFilterOptions:
    minimum_score: int | None = None
    required_directions: tuple[TenderDirection, ...] = ()
    require_all_directions: bool = False
    regions: tuple[str, ...] = ()
    laws: tuple[str, ...] = ()
    only_open: bool = True
    min_price: float | None = None
    max_price: float | None = None

    def __post_init__(self) -> None:
        if (
            self.minimum_score is not None
            and not 0 <= self.minimum_score <= 100
        ):
            raise ValueError(
                "minimum_score must be between 0 and 100"
            )
        if self.min_price is not None and self.min_price < 0:
            raise ValueError("min_price must be non-negative")
        if self.max_price is not None and self.max_price < 0:
            raise ValueError("max_price must be non-negative")
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError(
                "min_price cannot be greater than max_price"
            )


@dataclass(frozen=True, slots=True)
class EvaluatedTender:
    tender: UnifiedTender
    relevance: TenderRelevance
    accepted: bool
    rejection_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CorterisTenderFilterResult:
    accepted: tuple[EvaluatedTender, ...]
    rejected: tuple[EvaluatedTender, ...]
    total_count: int
    accepted_count: int
    rejected_count: int
    direction_counts: Mapping[TenderDirection, int] = field(
        default_factory=dict
    )

    @property
    def tenders(self) -> tuple[UnifiedTender, ...]:
        return tuple(item.tender for item in self.accepted)


DEFAULT_CORTERIS_PROFILE = CorterisSearchProfile(
    rules=(
        DirectionRule(
            TenderDirection.VIDEO_SURVEILLANCE,
            strong_terms=(
                "видеонаблюдение",
                "система видеонаблюдения",
                "охранное телевидение",
                "телевизионная система охраны",
                "cctv",
                "ip видеонаблюдение",
                "камера видеонаблюдения",
                "видеокамера",
                "видеорегистратор",
                "видеосервер",
                "видеоаналитика",
                "trassir",
                "трассир",
                "hikvision",
                "dahua",
            ),
            weak_terms=(
                "камера",
                "nvr",
                "vms",
                "архив видеозаписей",
                "объектив",
            ),
        ),
        DirectionRule(
            TenderDirection.OPS,
            strong_terms=(
                "охранно пожарная сигнализация",
                "пожарная сигнализация",
                "охранная сигнализация",
                "автоматическая пожарная сигнализация",
                "опс",
                "апс",
                "соуэ",
                "пожарная автоматика",
                "прибор приемно контрольный",
            ),
            weak_terms=(
                "пожарный извещатель",
                "дымовой извещатель",
                "болид",
                "стрелец",
                "рубеж",
            ),
        ),
        DirectionRule(
            TenderDirection.SKUD,
            strong_terms=(
                "скуд",
                "система контроля и управления доступом",
                "контроль и управление доступом",
                "контроль доступа",
                "турникет",
                "электромагнитный замок",
                "электромеханический замок",
                "считыватель карт",
                "контроллер доступа",
            ),
            weak_terms=(
                "пропускная система",
                "домофон",
                "биометрический терминал",
                "карта доступа",
            ),
        ),
        DirectionRule(
            TenderDirection.BARRIERS,
            strong_terms=(
                "шлагбаум",
                "автоматический шлагбаум",
                "парковочный барьер",
                "автоматические ворота",
                "привод ворот",
                "боллард",
                "дорожный блокиратор",
            ),
            weak_terms=(
                "кпп",
                "контроль проезда",
                "парковочная система",
                "стрела шлагбаума",
            ),
        ),
        DirectionRule(
            TenderDirection.ANPR,
            strong_terms=(
                "распознавание автомобильных номеров",
                "распознавание номеров",
                "распознавание государственных номеров",
                "anpr",
                "lpr",
                "entercam",
                "автоматизация кпп",
            ),
            weak_terms=(
                "государственный регистрационный знак",
                "грз",
                "контроль въезда",
                "учет автотранспорта",
            ),
        ),
        DirectionRule(
            TenderDirection.MAINTENANCE,
            strong_terms=(
                "техническое обслуживание видеонаблюдения",
                "обслуживание системы видеонаблюдения",
                "обслуживание скуд",
                "обслуживание опс",
                "обслуживание пожарной сигнализации",
                "ремонт видеонаблюдения",
                "техническое обслуживание систем безопасности",
                "регламентное обслуживание систем безопасности",
            ),
            weak_terms=(
                "техническое обслуживание",
                "сервисное обслуживание",
                "аварийный выезд",
                "регламентные работы",
            ),
        ),
        DirectionRule(
            TenderDirection.INTEGRATED_SECURITY,
            strong_terms=(
                "комплексная система безопасности",
                "интегрированная система безопасности",
                "инженерно технические средства охраны",
                "система безопасности объекта",
                "итсо",
                "комплекс технических средств охраны",
            ),
            weak_terms=(
                "слаботочные системы",
                "проектирование систем безопасности",
                "монтаж систем безопасности",
                "пусконаладочные работы",
            ),
        ),
    ),
    action_terms=(
        "поставка",
        "монтаж",
        "установка",
        "проектирование",
        "модернизация",
        "ремонт",
        "обслуживание",
        "пусконаладочные работы",
        "техническое обслуживание",
    ),
    hard_exclusion_terms=(
        "эндоскопическая камера",
        "медицинская камера",
        "холодильная камера",
        "морозильная камера",
        "камера хранения",
        "камера окраски",
        "камера сгорания",
        "камера термической обработки",
        "экшн камера",
        "веб камера",
        "фотокамера",
        "доступ к информационной системе",
        "предоставление доступа к базе данных",
    ),
)


class CorterisTenderClassifier:
    """Score a tender against the Corteris security-system profile."""

    TITLE_STRONG_WEIGHT = 18
    TITLE_WEAK_WEIGHT = 7
    BODY_STRONG_WEIGHT = 8
    BODY_WEAK_WEIGHT = 3
    TAG_STRONG_WEIGHT = 12
    TAG_WEAK_WEIGHT = 5
    ACTION_BONUS = 6
    MULTI_DIRECTION_BONUS = 8

    def __init__(
        self,
        profile: CorterisSearchProfile = DEFAULT_CORTERIS_PROFILE,
    ) -> None:
        self.profile = profile

    def evaluate(self, tender: UnifiedTender) -> TenderRelevance:
        title = normalize_text(tender.title)
        body = normalize_text(
            " ".join(
                (
                    tender.description,
                    tender.region,
                    tender.customer.name,
                    tender.law,
                    " ".join(tender.classification_codes),
                )
            )
        )
        tags = normalize_text(" ".join(tender.tags))
        combined = f" {title} {body} {tags} "

        exclusion_matches = _matched_terms(
            combined,
            self.profile.hard_exclusion_terms,
        )

        score = 0
        directions: list[TenderDirection] = []
        strong_matches: list[str] = []
        weak_matches: list[str] = []
        reasons: list[str] = []

        for rule in self.profile.rules:
            rule_score = 0
            rule_strong: list[str] = []
            rule_weak: list[str] = []

            for term in rule.strong_terms:
                normalized_term = normalize_text(term)
                if _contains_phrase(title, normalized_term):
                    rule_score += self.TITLE_STRONG_WEIGHT
                    rule_strong.append(term)
                elif _contains_phrase(tags, normalized_term):
                    rule_score += self.TAG_STRONG_WEIGHT
                    rule_strong.append(term)
                elif _contains_phrase(body, normalized_term):
                    rule_score += self.BODY_STRONG_WEIGHT
                    rule_strong.append(term)

            for term in rule.weak_terms:
                normalized_term = normalize_text(term)
                if _contains_phrase(title, normalized_term):
                    rule_score += self.TITLE_WEAK_WEIGHT
                    rule_weak.append(term)
                elif _contains_phrase(tags, normalized_term):
                    rule_score += self.TAG_WEAK_WEIGHT
                    rule_weak.append(term)
                elif _contains_phrase(body, normalized_term):
                    rule_score += self.BODY_WEAK_WEIGHT
                    rule_weak.append(term)

            rule_score = min(rule_score, 42)
            if rule_score:
                directions.append(rule.direction)
                score += rule_score
                strong_matches.extend(rule_strong)
                weak_matches.extend(rule_weak)
                reasons.append(
                    f"{rule.direction.value}: {rule_score} балл."
                )

        action_matches = _matched_terms(
            f" {title} {body} ",
            self.profile.action_terms,
        )
        if directions and action_matches:
            score += self.ACTION_BONUS
            reasons.append(
                "Есть работы/поставка по профильному направлению."
            )

        if len(directions) >= 2:
            score += self.MULTI_DIRECTION_BONUS
            reasons.append(
                "Закупка объединяет несколько направлений Кортерис."
            )

        has_strong_security_match = bool(strong_matches)
        hard_excluded = bool(
            exclusion_matches and not has_strong_security_match
        )
        if hard_excluded:
            score = 0
            reasons.append(
                "Обнаружена непрофильная трактовка ключевого слова."
            )

        score = max(0, min(100, score))
        grade = self._grade(score, hard_excluded)

        return TenderRelevance(
            score=score,
            grade=grade,
            directions=_ordered_unique_enum(directions),
            matched_strong_terms=_ordered_unique(strong_matches),
            matched_weak_terms=_ordered_unique(weak_matches),
            matched_action_terms=_ordered_unique(action_matches),
            matched_exclusion_terms=_ordered_unique(
                exclusion_matches
            ),
            reasons=tuple(reasons),
            hard_excluded=hard_excluded,
        )

    def _grade(
        self,
        score: int,
        hard_excluded: bool,
    ) -> RelevanceGrade:
        if hard_excluded or score < self.profile.minimum_score:
            return RelevanceGrade.EXCLUDED
        if score >= self.profile.high_score:
            return RelevanceGrade.HIGH
        if score >= self.profile.medium_score:
            return RelevanceGrade.MEDIUM
        return RelevanceGrade.LOW


class CorterisTenderFilter:
    """Apply business filters and rank accepted tenders."""

    def __init__(
        self,
        classifier: CorterisTenderClassifier | None = None,
    ) -> None:
        self.classifier = classifier or CorterisTenderClassifier()

    def filter(
        self,
        tenders: Iterable[UnifiedTender],
        options: TenderFilterOptions | None = None,
    ) -> CorterisTenderFilterResult:
        options = options or TenderFilterOptions()
        minimum_score = (
            self.classifier.profile.minimum_score
            if options.minimum_score is None
            else options.minimum_score
        )

        accepted: list[EvaluatedTender] = []
        rejected: list[EvaluatedTender] = []
        direction_counts: dict[TenderDirection, int] = {}

        for tender in tenders:
            relevance = self.classifier.evaluate(tender)
            rejection_reasons = self._rejection_reasons(
                tender,
                relevance,
                options,
                minimum_score,
            )
            evaluated = EvaluatedTender(
                tender=tender,
                relevance=relevance,
                accepted=not rejection_reasons,
                rejection_reasons=tuple(rejection_reasons),
            )

            if rejection_reasons:
                rejected.append(evaluated)
                continue

            accepted.append(evaluated)
            for direction in relevance.directions:
                direction_counts[direction] = (
                    direction_counts.get(direction, 0) + 1
                )

        accepted.sort(key=self._ranking_key)

        return CorterisTenderFilterResult(
            accepted=tuple(accepted),
            rejected=tuple(rejected),
            total_count=len(accepted) + len(rejected),
            accepted_count=len(accepted),
            rejected_count=len(rejected),
            direction_counts=dict(direction_counts),
        )

    @staticmethod
    def _rejection_reasons(
        tender: UnifiedTender,
        relevance: TenderRelevance,
        options: TenderFilterOptions,
        minimum_score: int,
    ) -> list[str]:
        reasons: list[str] = []

        if relevance.hard_excluded:
            reasons.append("Непрофильная закупка")
        elif relevance.score < minimum_score:
            reasons.append(
                f"Релевантность ниже порога: "
                f"{relevance.score} < {minimum_score}"
            )

        if options.only_open and tender.status not in {
            TenderStatus.PUBLISHED,
            TenderStatus.ACCEPTING_APPLICATIONS,
        }:
            reasons.append("Приём заявок не открыт")

        required = set(options.required_directions)
        actual = set(relevance.directions)
        if required:
            matched = required.intersection(actual)
            if options.require_all_directions:
                if matched != required:
                    reasons.append(
                        "Найдены не все обязательные направления"
                    )
            elif not matched:
                reasons.append(
                    "Нет требуемого направления Кортерис"
                )

        if options.regions:
            region = normalize_text(
                tender.region or tender.customer.region
            )
            allowed = tuple(
                normalize_text(value)
                for value in options.regions
            )
            if not any(
                _contains_phrase(region, value)
                for value in allowed
            ):
                reasons.append("Регион не входит в фильтр")

        if options.laws:
            law = normalize_text(tender.law)
            allowed_laws = {
                normalize_text(value)
                for value in options.laws
            }
            if law not in allowed_laws:
                reasons.append("Закон закупки не входит в фильтр")

        amount = (
            float(tender.price.amount)
            if tender.price is not None
            else None
        )
        if (
            options.min_price is not None
            and amount is not None
            and amount < options.min_price
        ):
            reasons.append("Цена ниже минимальной")
        if (
            options.max_price is not None
            and amount is not None
            and amount > options.max_price
        ):
            reasons.append("Цена выше максимальной")

        return reasons

    @staticmethod
    def _ranking_key(
        item: EvaluatedTender,
    ) -> tuple[int, datetime, str]:
        deadline = item.tender.application_deadline or datetime.max
        return (
            -item.relevance.score,
            deadline,
            item.tender.title.casefold(),
        )


def normalize_text(value: str) -> str:
    normalized = value.casefold().replace("ё", "е")
    normalized = re.sub(r"[^0-9a-zа-я]+", " ", normalized)
    return " ".join(normalized.split())


def _contains_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    return f" {phrase} " in f" {text} "


def _matched_terms(
    text: str,
    terms: Sequence[str],
) -> tuple[str, ...]:
    matches = [
        term
        for term in terms
        if _contains_phrase(text, normalize_text(term))
    ]
    return _ordered_unique(matches)


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        identity = normalized.casefold()
        if not normalized or identity in seen:
            continue
        seen.add(identity)
        result.append(normalized)
    return tuple(result)


def _ordered_unique_enum(
    values: Iterable[TenderDirection],
) -> tuple[TenderDirection, ...]:
    result: list[TenderDirection] = []
    seen: set[TenderDirection] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return tuple(result)


__all__ = [
    "CorterisSearchProfile",
    "CorterisTenderClassifier",
    "CorterisTenderFilter",
    "CorterisTenderFilterResult",
    "DEFAULT_CORTERIS_PROFILE",
    "DirectionRule",
    "EvaluatedTender",
    "RelevanceGrade",
    "TenderDirection",
    "TenderFilterOptions",
    "TenderRelevance",
    "normalize_text",
]
