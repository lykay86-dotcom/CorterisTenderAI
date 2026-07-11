"""Saved tender-search profiles and built-in Corteris presets."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
import re
from typing import Iterable, Mapping, Any

from app.tenders.corteris_filter import (
    TenderDirection,
    TenderFilterOptions,
)
from app.tenders.provider_base import TenderSearchQuery


_PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


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
    min_price: float | None = None
    max_price: float | None = None
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

    def __post_init__(self) -> None:
        normalized_id = self.id.strip().casefold()
        if normalized_id != self.id:
            object.__setattr__(self, "id", normalized_id)
        if not _PROFILE_ID_RE.fullmatch(normalized_id):
            raise ValueError(
                "Profile id must contain 2-64 lowercase Latin "
                "letters, digits, '_' or '-'"
            )
        if not self.name.strip():
            raise ValueError("Profile name must not be empty")
        if not self.keywords and not self.directions:
            raise ValueError(
                "Profile must contain keywords or directions"
            )
        if not 0 <= self.minimum_score <= 100:
            raise ValueError(
                "minimum_score must be between 0 and 100"
            )
        if self.lookback_days is not None:
            if not 0 <= self.lookback_days <= 3650:
                raise ValueError(
                    "lookback_days must be between 0 and 3650"
                )
        if not 1 <= self.page_size <= 500:
            raise ValueError("page_size must be between 1 and 500")
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
        if any(not item.strip() for item in self.provider_ids):
            raise ValueError("provider_ids cannot contain empty values")
        if len(set(self.provider_ids)) != len(self.provider_ids):
            raise ValueError("provider_ids must be unique")

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
            date_from = current_date - timedelta(
                days=self.lookback_days
            )

        return TenderSearchQuery(
            keywords=self.keywords,
            excluded_keywords=self.excluded_keywords,
            regions=self.regions,
            laws=self.laws,
            date_from=date_from,
            date_to=date_to,
            min_price=self.min_price,
            max_price=self.max_price,
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
            "directions": [
                direction.value for direction in self.directions
            ],
            "require_all_directions": self.require_all_directions,
            "regions": list(self.regions),
            "laws": list(self.laws),
            "min_price": self.min_price,
            "max_price": self.max_price,
            "minimum_score": self.minimum_score,
            "only_open": self.only_open,
            "lookback_days": self.lookback_days,
            "page_size": self.page_size,
            "provider_ids": list(self.provider_ids),
            "include_disabled_providers": (
                self.include_disabled_providers
            ),
            "enabled": self.enabled,
            "is_builtin": self.is_builtin,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
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
            excluded_keywords=_string_tuple(
                payload.get("excluded_keywords", ())
            ),
            directions=tuple(
                TenderDirection(str(value))
                for value in directions_raw
            ),
            require_all_directions=bool(
                payload.get("require_all_directions", False)
            ),
            regions=_string_tuple(payload.get("regions", ())),
            laws=_string_tuple(
                payload.get("laws", ("44-ФЗ", "223-ФЗ"))
            ),
            min_price=_optional_float(payload.get("min_price")),
            max_price=_optional_float(payload.get("max_price")),
            minimum_score=int(payload.get("minimum_score", 24)),
            only_open=bool(payload.get("only_open", True)),
            lookback_days=_optional_int(
                payload.get("lookback_days", 30)
            ),
            page_size=int(payload.get("page_size", 50)),
            provider_ids=_string_tuple(
                payload.get("provider_ids", ("eis",))
            ),
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
            description=(
                "Общий поиск по системам безопасности, монтажу "
                "и обслуживанию."
            ),
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
            description=(
                "Камеры, регистраторы, видеоаналитика, "
                "Trassir, Hikvision и Dahua."
            ),
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
            description=(
                "Охранная и пожарная сигнализация, АПС, "
                "СОУЭ и пожарная автоматика."
            ),
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
            description=(
                "СКУД, турникеты, контроллеры, считыватели "
                "и электронные замки."
            ),
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
                "Шлагбаумы, автоматизация КПП, ANPR/LPR "
                "и контроль автомобильного проезда."
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
            description=(
                "Техническое и регламентное обслуживание, "
                "ремонт и аварийные выезды."
            ),
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
            **{
                key: value
                for key, value in common.items()
                if key != "minimum_score"
            },
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


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _iso_timestamp(value: datetime | None = None) -> str:
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(
        timespec="seconds"
    )


__all__ = [
    "TenderSearchProfile",
    "create_builtin_search_profiles",
]
