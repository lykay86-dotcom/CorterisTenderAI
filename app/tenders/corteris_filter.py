"""Corteris-specific tender classification, filtering and ranking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
import re
from typing import Iterable, Mapping, Sequence

from app.tenders.models import (
    TenderStatus,
    UnifiedTender,
    normalize_currency_code,
    normalize_money_amount,
)


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
    okpd2_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CorterisSearchProfile:
    """Keyword and scoring profile for ООО «Кортерис»."""

    rules: tuple[DirectionRule, ...]
    action_terms: tuple[str, ...]
    hard_exclusion_terms: tuple[str, ...]
    minimum_score: int = 24
    medium_score: int = 40
    high_score: int = 65
    title_strong_weight: int = 18
    title_weak_weight: int = 7
    body_strong_weight: int = 8
    body_weak_weight: int = 3
    tag_strong_weight: int = 12
    tag_weak_weight: int = 5
    action_bonus: int = 6
    multi_direction_bonus: int = 8
    okpd2_weight: int = 10
    term_weight_percent: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_score <= 100:
            raise ValueError("minimum_score must be between 0 and 100")
        if not (self.minimum_score <= self.medium_score <= self.high_score <= 100):
            raise ValueError("Invalid relevance score thresholds")
        weights = (
            self.title_strong_weight,
            self.title_weak_weight,
            self.body_strong_weight,
            self.body_weak_weight,
            self.tag_strong_weight,
            self.tag_weak_weight,
            self.action_bonus,
            self.multi_direction_bonus,
            self.okpd2_weight,
        )
        if any(not 0 <= item <= 100 for item in weights):
            raise ValueError("matching weights must be between 0 and 100")
        if any(not 0 <= int(weight) <= 500 for _, weight in self.term_weight_percent):
            raise ValueError("term weight percent must be between 0 and 500")


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
    matched_okpd2: tuple[str, ...] = ()

    @property
    def relevant(self) -> bool:
        return not self.hard_excluded and self.grade != RelevanceGrade.EXCLUDED


@dataclass(frozen=True, slots=True)
class TenderFilterOptions:
    minimum_score: int | None = None
    required_directions: tuple[TenderDirection, ...] = ()
    require_all_directions: bool = False
    regions: tuple[str, ...] = ()
    laws: tuple[str, ...] = ()
    only_open: bool = True
    min_price: Decimal | int | float | str | None = None
    max_price: Decimal | int | float | str | None = None
    price_currency: str = "RUB"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "price_currency",
            normalize_currency_code(self.price_currency),
        )
        if self.min_price is not None:
            object.__setattr__(
                self,
                "min_price",
                normalize_money_amount(
                    self.min_price,
                    field_name="min_price",
                ),
            )
        if self.max_price is not None:
            object.__setattr__(
                self,
                "max_price",
                normalize_money_amount(
                    self.max_price,
                    field_name="max_price",
                ),
            )
        if self.minimum_score is not None and not 0 <= self.minimum_score <= 100:
            raise ValueError("minimum_score must be between 0 and 100")
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price cannot be greater than max_price")


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
    direction_counts: Mapping[TenderDirection, int] = field(default_factory=dict)

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
        "капитальное строительство здания целиком",
        "строительство здания под ключ",
        "строительство автомобильной дороги",
        "строительство дорог",
        "генеральный подряд",
        "генподряд",
        "строительство метро",
        "медицинская видеокамера",
        "медицинские видеокамеры",
        "бытовая веб камера",
        "аренда съемочного оборудования",
        "видеосъемка мероприятий",
        "ремонт автомобилей",
        "телестудийное оборудование",
        "оборудование телестудии",
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
        okpd2_matches: list[str] = []
        reasons: list[str] = []

        for rule in self.profile.rules:
            rule_score = 0
            rule_strong: list[str] = []
            rule_weak: list[str] = []

            for term in rule.strong_terms:
                normalized_term = normalize_text(term)
                if _contains_phrase(title, normalized_term):
                    rule_score += self._term_score(term, self.profile.title_strong_weight)
                    rule_strong.append(term)
                elif _contains_phrase(tags, normalized_term):
                    rule_score += self._term_score(term, self.profile.tag_strong_weight)
                    rule_strong.append(term)
                elif _contains_phrase(body, normalized_term):
                    rule_score += self._term_score(term, self.profile.body_strong_weight)
                    rule_strong.append(term)

            for term in rule.weak_terms:
                normalized_term = normalize_text(term)
                if _contains_phrase(title, normalized_term):
                    rule_score += self._term_score(term, self.profile.title_weak_weight)
                    rule_weak.append(term)
                elif _contains_phrase(tags, normalized_term):
                    rule_score += self._term_score(term, self.profile.tag_weak_weight)
                    rule_weak.append(term)
                elif _contains_phrase(body, normalized_term):
                    rule_score += self._term_score(term, self.profile.body_weak_weight)
                    rule_weak.append(term)

            rule_okpd2 = tuple(
                code
                for code in tender.classification_codes
                if any(
                    code.replace(" ", "").startswith(prefix.replace(" ", ""))
                    for prefix in rule.okpd2_codes
                )
            )
            if rule_okpd2:
                rule_score += self.profile.okpd2_weight
                okpd2_matches.extend(rule_okpd2)

            rule_score = min(rule_score, 42)
            if rule_score:
                directions.append(rule.direction)
                score += rule_score
                strong_matches.extend(rule_strong)
                weak_matches.extend(rule_weak)
                reasons.append(f"{rule.direction.value}: {rule_score} балл.")

        action_matches = _matched_terms(
            f" {title} {body} ",
            self.profile.action_terms,
        )
        if directions and action_matches:
            score += self.profile.action_bonus
            reasons.append("Есть работы/поставка по профильному направлению.")

        if len(directions) >= 2:
            score += self.profile.multi_direction_bonus
            reasons.append("Закупка объединяет несколько направлений Кортерис.")

        hard_excluded = bool(exclusion_matches)
        if hard_excluded:
            score = 0
            reasons.append("Обнаружена непрофильная трактовка ключевого слова.")

        score = max(0, min(100, score))
        grade = self._grade(score, hard_excluded)

        return TenderRelevance(
            score=score,
            grade=grade,
            directions=_ordered_unique_enum(directions),
            matched_strong_terms=_ordered_unique(strong_matches),
            matched_weak_terms=_ordered_unique(weak_matches),
            matched_action_terms=_ordered_unique(action_matches),
            matched_exclusion_terms=_ordered_unique(exclusion_matches),
            reasons=tuple(reasons),
            hard_excluded=hard_excluded,
            matched_okpd2=_ordered_unique(okpd2_matches),
        )

    def _term_score(self, term: str, base: int) -> int:
        configured = {
            normalize_text(key): int(value) for key, value in self.profile.term_weight_percent
        }.get(normalize_text(term), 100)
        return max(0, round(base * configured / 100))

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
                direction_counts[direction] = direction_counts.get(direction, 0) + 1

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
            reasons.append(f"Релевантность ниже порога: {relevance.score} < {minimum_score}")

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
                    reasons.append("Найдены не все обязательные направления")
            elif not matched:
                reasons.append("Нет требуемого направления Кортерис")

        if options.regions:
            region = normalize_text(tender.region or tender.customer.region)
            allowed = tuple(normalize_text(value) for value in options.regions)
            if not any(_contains_phrase(region, value) for value in allowed):
                reasons.append("Регион не входит в фильтр")

        if options.laws:
            law = normalize_text(tender.law)
            allowed_laws = {normalize_text(value) for value in options.laws}
            if law not in allowed_laws:
                reasons.append("Закон закупки не входит в фильтр")

        amount = tender.price.amount if tender.price is not None else None
        has_price_boundary = options.min_price is not None or options.max_price is not None
        if (
            has_price_boundary
            and tender.price is not None
            and tender.price.currency != options.price_currency
        ):
            reasons.append("Валюта цены не совпадает с валютой фильтра")
            return reasons
        if options.min_price is not None and amount is not None and amount < options.min_price:
            reasons.append("Цена ниже минимальной")
        if options.max_price is not None and amount is not None and amount > options.max_price:
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
    """Match normalized phrases with lightweight Russian inflection support."""
    if not text or not phrase:
        return False

    text_tokens = text.split()
    phrase_tokens = phrase.split()
    if not text_tokens or not phrase_tokens:
        return False
    if len(phrase_tokens) > len(text_tokens):
        return False

    window_size = len(phrase_tokens)
    for start in range(len(text_tokens) - window_size + 1):
        window = text_tokens[start : start + window_size]
        if all(
            _tokens_match(text_token, phrase_token)
            for text_token, phrase_token in zip(
                window,
                phrase_tokens,
                strict=True,
            )
        ):
            return True
    return False


_RUSSIAN_SUFFIXES = tuple(
    sorted(
        {
            "иями",
            "ями",
            "ами",
            "его",
            "ого",
            "ему",
            "ому",
            "ими",
            "ыми",
            "ией",
            "ией",
            "иям",
            "иях",
            "ием",
            "ью",
            "ей",
            "ий",
            "ый",
            "ой",
            "ая",
            "яя",
            "ое",
            "ее",
            "ие",
            "ые",
            "ую",
            "юю",
            "ов",
            "ев",
            "ам",
            "ям",
            "ах",
            "ях",
            "ия",
            "ья",
            "ию",
            "а",
            "я",
            "ы",
            "и",
            "у",
            "ю",
            "е",
            "о",
        },
        key=len,
        reverse=True,
    )
)


def _tokens_match(text_token: str, phrase_token: str) -> bool:
    if text_token == phrase_token:
        return True

    # Short abbreviations such as ОПС, АПС, NVR, VMS and LPR
    # are matched exactly to avoid accidental partial matches.
    if min(len(text_token), len(phrase_token)) <= 3:
        return False

    return _russian_stem(text_token) == _russian_stem(phrase_token)


def _russian_stem(token: str) -> str:
    if not re.fullmatch(r"[а-я]+", token):
        return token

    for suffix in _RUSSIAN_SUFFIXES:
        if token.endswith(suffix):
            stem = token[: -len(suffix)]
            if len(stem) >= 4:
                return stem
    return token


def _matched_terms(
    text: str,
    terms: Sequence[str],
) -> tuple[str, ...]:
    matches = [term for term in terms if _contains_phrase(text, normalize_text(term))]
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
