"""Saved tender-search profiles and built-in Corteris presets."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
import re
from typing import Mapping, Any

from app.tenders.corteris_filter import (
    TenderDirection,
    TenderFilterOptions,
)
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.models import (
    normalize_currency_code,
    normalize_money_amount,
)


_PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


class SearchProfileRuntimeQueryPolicy(StrEnum):
    """Versioned policy for transient text in the unified-search request."""

    REPLACE_KEYWORDS_IF_PRESENT = "replace_keywords_if_present"


@dataclass(frozen=True, slots=True)
class TenderSearchProfile:
    """A reusable search and business-filter configuration."""

    id: str
    name: str
    description: str = ""
    keywords: tuple[str, ...] = ()
    excluded_keywords: tuple[str, ...] = ()
    directions: tuple[TenderDirection, ...] = ()
    require_all_directions: bool = False
    regions: tuple[str, ...] = ()
    laws: tuple[str, ...] = ("44-ФЗ", "223-ФЗ")
    min_price: Decimal | int | float | str | None = None
    max_price: Decimal | int | float | str | None = None
    minimum_score: int = 24
    only_open: bool = True
    lookback_days: int | None = 30
    page_size: int = 50
    provider_ids: tuple[str, ...] = ("eis",)
    include_disabled_providers: bool = False
    enabled: bool = True
    is_builtin: bool = False
    created_at: str = ""
    updated_at: str = ""
    price_currency: str = "RUB"
    runtime_query_policy: SearchProfileRuntimeQueryPolicy = (
        SearchProfileRuntimeQueryPolicy.REPLACE_KEYWORDS_IF_PRESENT
    )

    def __post_init__(self) -> None:
        try:
            runtime_query_policy = SearchProfileRuntimeQueryPolicy(self.runtime_query_policy)
        except (TypeError, ValueError) as exc:
            raise ValueError("runtime_query_policy is unsupported") from exc
        object.__setattr__(self, "runtime_query_policy", runtime_query_policy)

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
        normalized_id = self.id.strip().casefold()
        if normalized_id != self.id:
            object.__setattr__(self, "id", normalized_id)
        object.__setattr__(self, "keywords", _string_tuple(self.keywords))
        object.__setattr__(
            self,
            "excluded_keywords",
            _string_tuple(self.excluded_keywords),
        )
        object.__setattr__(
            self,
            "directions",
            tuple(TenderDirection(item) for item in self.directions),
        )
        object.__setattr__(self, "regions", _string_tuple(self.regions))
        object.__setattr__(self, "laws", _string_tuple(self.laws))
        object.__setattr__(
            self,
            "provider_ids",
            _provider_id_tuple(self.provider_ids),
        )
        object.__setattr__(
            self,
            "created_at",
            _normalize_optional_timestamp(self.created_at, field_name="created_at"),
        )
        object.__setattr__(
            self,
            "updated_at",
            _normalize_optional_timestamp(self.updated_at, field_name="updated_at"),
        )
        if not _PROFILE_ID_RE.fullmatch(normalized_id):
            raise ValueError(
                "Profile id must contain 2-64 lowercase Latin letters, digits, '_' or '-'"
            )
        if not self.name.strip():
            raise ValueError("Profile name must not be empty")
        if not self.keywords and not self.directions:
            raise ValueError("Profile must contain keywords or directions")
        if not 0 <= self.minimum_score <= 100:
            raise ValueError("minimum_score must be between 0 and 100")
        if self.lookback_days is not None:
            if not 0 <= self.lookback_days <= 3650:
                raise ValueError("lookback_days must be between 0 and 3650")
        if not 1 <= self.page_size <= 500:
            raise ValueError("page_size must be between 1 and 500")
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price cannot be greater than max_price")

    def to_search_query(
        self,
        *,
        today: date | None = None,
        page: int = 1,
    ) -> TenderSearchQuery:
        current_date = today or date.today()
        date_from = None
        date_to = None
        if self.lookback_days is not None:
            date_to = current_date
            date_from = current_date - timedelta(days=self.lookback_days)

        return TenderSearchQuery(
            keywords=self.keywords,
            excluded_keywords=self.excluded_keywords,
            regions=self.regions,
            laws=self.laws,
            date_from=date_from,
            date_to=date_to,
            min_price=self.min_price,
            max_price=self.max_price,
            price_currency=self.price_currency,
            page=page,
            page_size=self.page_size,
        )

    def to_filter_options(self) -> TenderFilterOptions:
        return TenderFilterOptions(
            minimum_score=self.minimum_score,
            required_directions=self.directions,
            require_all_directions=self.require_all_directions,
            regions=self.regions,
            laws=self.laws,
            only_open=self.only_open,
            min_price=self.min_price,
            max_price=self.max_price,
            price_currency=self.price_currency,
        )

    def clone_as_custom(
        self,
        *,
        profile_id: str,
        name: str,
        now: datetime | None = None,
    ) -> "TenderSearchProfile":
        timestamp = _iso_timestamp(now)
        return replace(
            self,
            id=profile_id,
            name=name,
            is_builtin=False,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "keywords": list(self.keywords),
            "excluded_keywords": list(self.excluded_keywords),
            "directions": [direction.value for direction in self.directions],
            "require_all_directions": self.require_all_directions,
            "regions": list(self.regions),
            "laws": list(self.laws),
            "min_price": (str(self.min_price) if self.min_price is not None else None),
            "max_price": (str(self.max_price) if self.max_price is not None else None),
            "price_currency": self.price_currency,
            "minimum_score": self.minimum_score,
            "only_open": self.only_open,
            "lookback_days": self.lookback_days,
            "page_size": self.page_size,
            "provider_ids": list(self.provider_ids),
            "include_disabled_providers": (self.include_disabled_providers),
            "enabled": self.enabled,
            "is_builtin": self.is_builtin,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "runtime_query_policy": self.runtime_query_policy.value,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "TenderSearchProfile":
        directions_raw = payload.get("directions", ())
        if not isinstance(directions_raw, (list, tuple)):
            raise ValueError("directions must be an array")

        return cls(
            id=str(payload.get("id", "")),
            name=str(payload.get("name", "")),
            description=str(payload.get("description", "")),
            keywords=_string_tuple(payload.get("keywords", ())),
            excluded_keywords=_string_tuple(payload.get("excluded_keywords", ())),
            directions=tuple(TenderDirection(str(value)) for value in directions_raw),
            require_all_directions=bool(payload.get("require_all_directions", False)),
            regions=_string_tuple(payload.get("regions", ())),
            laws=_string_tuple(payload.get("laws", ("44-ФЗ", "223-ФЗ"))),
            min_price=_optional_decimal(payload.get("min_price")),
            max_price=_optional_decimal(payload.get("max_price")),
            price_currency=str(payload.get("price_currency", "RUB")),
            minimum_score=int(payload.get("minimum_score", 24)),
            only_open=bool(payload.get("only_open", True)),
            lookback_days=_optional_int(payload.get("lookback_days", 30)),
            page_size=int(payload.get("page_size", 50)),
            provider_ids=_string_tuple(payload.get("provider_ids", ("eis",))),
            include_disabled_providers=bool(
                payload.get(
                    "include_disabled_providers",
                    False,
                )
            ),
            enabled=bool(payload.get("enabled", True)),
            is_builtin=bool(payload.get("is_builtin", False)),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
            runtime_query_policy=SearchProfileRuntimeQueryPolicy(
                str(
                    payload.get(
                        "runtime_query_policy",
                        SearchProfileRuntimeQueryPolicy.REPLACE_KEYWORDS_IF_PRESENT.value,
                    )
                )
            ),
        )


def create_builtin_search_profiles(
    *,
    now: datetime | None = None,
) -> tuple[TenderSearchProfile, ...]:
    """Return the canonical Corteris search presets."""

    timestamp = _iso_timestamp(now)
    common = {
        "laws": ("44-ФЗ", "223-ФЗ"),
        "minimum_score": 24,
        "only_open": True,
        "lookback_days": 30,
        "page_size": 100,
        "provider_ids": ("eis",),
        "is_builtin": True,
        "created_at": timestamp,
        "updated_at": timestamp,
    }

    return (
        TenderSearchProfile(
            id="all-corteris",
            name="Все направления Кортерис",
            description=("Общий поиск по системам безопасности, монтажу и обслуживанию."),
            keywords=(
                "видеонаблюдение",
                "охранно-пожарная сигнализация",
                "СКУД",
                "шлагбаум",
                "распознавание номеров",
                "комплексная система безопасности",
            ),
            directions=(),
            **common,
        ),
        TenderSearchProfile(
            id="video-surveillance",
            name="Видеонаблюдение",
            description=("Камеры, регистраторы, видеоаналитика, Trassir, Hikvision и Dahua."),
            keywords=(
                "видеонаблюдение",
                "камера видеонаблюдения",
                "видеорегистратор",
                "видеоаналитика",
                "Trassir",
                "Hikvision",
                "Dahua",
            ),
            directions=(TenderDirection.VIDEO_SURVEILLANCE,),
            **common,
        ),
        TenderSearchProfile(
            id="ops",
            name="ОПС и пожарная автоматика",
            description=("Охранная и пожарная сигнализация, АПС, СОУЭ и пожарная автоматика."),
            keywords=(
                "охранно-пожарная сигнализация",
                "пожарная сигнализация",
                "охранная сигнализация",
                "АПС",
                "СОУЭ",
                "пожарная автоматика",
            ),
            directions=(TenderDirection.OPS,),
            **common,
        ),
        TenderSearchProfile(
            id="skud",
            name="СКУД и контроль доступа",
            description=("СКУД, турникеты, контроллеры, считыватели и электронные замки."),
            keywords=(
                "СКУД",
                "система контроля и управления доступом",
                "турникет",
                "контроллер доступа",
                "считыватель карт",
                "электромагнитный замок",
            ),
            directions=(TenderDirection.SKUD,),
            **common,
        ),
        TenderSearchProfile(
            id="barriers-anpr",
            name="Шлагбаумы и распознавание номеров",
            description=(
                "Шлагбаумы, автоматизация КПП, ANPR/LPR и контроль автомобильного проезда."
            ),
            keywords=(
                "шлагбаум",
                "автоматический шлагбаум",
                "распознавание автомобильных номеров",
                "распознавание номеров",
                "автоматизация КПП",
                "ANPR",
                "LPR",
                "Entercam",
            ),
            directions=(
                TenderDirection.BARRIERS,
                TenderDirection.ANPR,
            ),
            require_all_directions=False,
            **common,
        ),
        TenderSearchProfile(
            id="maintenance",
            name="Обслуживание систем безопасности",
            description=("Техническое и регламентное обслуживание, ремонт и аварийные выезды."),
            keywords=(
                "техническое обслуживание видеонаблюдения",
                "обслуживание СКУД",
                "обслуживание ОПС",
                "обслуживание пожарной сигнализации",
                "ремонт систем безопасности",
            ),
            directions=(TenderDirection.MAINTENANCE,),
            **common,
        ),
        TenderSearchProfile(
            id="integrated-security",
            name="Комплексные системы безопасности",
            description=(
                "Комплексные проекты с несколькими подсистемами "
                "безопасности и автоматизацией объекта."
            ),
            keywords=(
                "комплексная система безопасности",
                "интегрированная система безопасности",
                "инженерно-технические средства охраны",
                "комплекс технических средств охраны",
                "слаботочные системы",
            ),
            directions=(TenderDirection.INTEGRATED_SECURITY,),
            minimum_score=30,
            **{key: value for key, value in common.items() if key != "minimum_score"},
        ),
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if not isinstance(value, (list, tuple)):
        raise ValueError("Expected a string array")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        identity = text.casefold()
        if not text or identity in seen:
            continue
        seen.add(identity)
        result.append(text)
    return tuple(result)


def _provider_id_tuple(value: object) -> tuple[str, ...]:
    values = _string_tuple(value)
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        provider_id = item.casefold()
        if provider_id in seen:
            continue
        seen.add(provider_id)
        result.append(provider_id)
    return tuple(result)


def _optional_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    return normalize_money_amount(value)  # type: ignore[arg-type]


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _iso_timestamp(value: datetime | None = None) -> str:
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        raise ValueError("timestamp must include timezone information")
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _normalize_optional_timestamp(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO 8601 timestamp") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_optional_decimal_text(
    value: object,
    *,
    field_name: str = "price",
) -> Decimal | None:
    """Parse one optional UI money value without a float boundary."""

    text = str(value or "").strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        return None
    if "," in text:
        if "." in text or text.count(",") != 1:
            raise ValueError(f"{field_name} must be a decimal number")
        text = text.replace(",", ".")
    return normalize_money_amount(text, field_name=field_name)


def format_optional_decimal(value: object) -> str:
    """Render one optional money value exactly for a line-edit boundary."""

    if value in (None, ""):
        return ""
    return str(normalize_money_amount(value, field_name="price"))  # type: ignore[arg-type]


__all__ = [
    "SearchProfileRuntimeQueryPolicy",
    "TenderSearchProfile",
    "create_builtin_search_profiles",
    "format_optional_decimal",
    "parse_optional_decimal_text",
]
