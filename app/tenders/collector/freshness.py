"""Deadline normalization and adaptive reverification policy.

The service keeps the provider's original deadline representation, resolves
an explicit source timezone when possible, stores UTC/user-local projections,
and decides when a tender needs another verification pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from enum import StrEnum
import re
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.tenders.collector.verification import (
    TenderVerificationResult,
    TenderVerificationStatus,
    VerificationBatchResult,
)
from app.tenders.models import UnifiedTender


class DeadlineTimezoneStatus(StrEnum):
    """How the source deadline timezone was established."""

    MISSING = "missing"
    EXPLICIT = "explicit"
    SOURCE_ZONE = "source_zone"
    UNKNOWN = "unknown"
    INVALID = "invalid"


class TenderFreshnessStatus(StrEnum):
    """Operational freshness visible to the user and scheduler."""

    FRESH = "fresh"
    DUE_SOON = "due_soon"
    STALE = "stale"
    EXPIRED = "expired"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class DeadlineNormalization:
    original_value: str
    source_timezone: str
    timezone_status: DeadlineTimezoneStatus
    deadline_utc: str
    user_timezone: str
    deadline_user_local: str
    seconds_remaining: int | None

    @property
    def timezone_confirmed(self) -> bool:
        return self.timezone_status in {
            DeadlineTimezoneStatus.EXPLICIT,
            DeadlineTimezoneStatus.SOURCE_ZONE,
        }


@dataclass(frozen=True, slots=True)
class TenderFreshnessState:
    canonical_key: str
    status: TenderFreshnessStatus
    last_verified_at: str
    verification_due_at: str
    is_stale: bool
    stale_reason: str
    deadline_original: str
    source_timezone: str
    timezone_status: DeadlineTimezoneStatus
    deadline_utc: str
    user_timezone: str
    deadline_user_local: str
    seconds_remaining: int | None
    recheck_interval_minutes: int
    deadline_expired: bool
    updated_at: str

    @property
    def requires_reverification(self) -> bool:
        return self.is_stale and not self.deadline_expired


@dataclass(frozen=True, slots=True)
class FreshnessBatchResult:
    items: tuple[TenderFreshnessState, ...]
    evaluated_at: str

    @property
    def by_canonical_key(self) -> Mapping[str, TenderFreshnessState]:
        return {item.canonical_key: item for item in self.items}

    @property
    def stale_count(self) -> int:
        return sum(item.is_stale for item in self.items)

    @property
    def due_soon_count(self) -> int:
        return sum(
            item.status == TenderFreshnessStatus.DUE_SOON
            for item in self.items
        )

    @property
    def expired_count(self) -> int:
        return sum(item.deadline_expired for item in self.items)


class TenderFreshnessService:
    """Normalize deadlines and calculate a conservative recheck schedule."""

    def __init__(
        self,
        *,
        user_timezone: str | tzinfo | None = None,
    ) -> None:
        self._user_timezone = _resolve_user_timezone(user_timezone)

    def evaluate(
        self,
        verification: VerificationBatchResult,
        *,
        now: datetime | str | None = None,
    ) -> FreshnessBatchResult:
        current = _aware_datetime(now) if now is not None else _utc_now_dt()
        items = tuple(
            self.evaluate_item(item, now=current)
            for item in verification.items
        )
        return FreshnessBatchResult(
            items=items,
            evaluated_at=_iso_utc(current),
        )

    def evaluate_item(
        self,
        verification: TenderVerificationResult,
        *,
        now: datetime | str | None = None,
    ) -> TenderFreshnessState:
        current = _aware_datetime(now) if now is not None else _utc_now_dt()
        deadline = normalize_application_deadline(
            verification.tender,
            now=current,
            user_timezone=self._user_timezone,
        )
        last_verified = _aware_datetime(verification.verified_at)
        interval, forced_reason = _recheck_policy(
            verification,
            deadline,
        )
        due = last_verified + timedelta(minutes=interval)
        deadline_expired = (
            deadline.seconds_remaining is not None
            and deadline.seconds_remaining <= 0
        )

        if deadline_expired:
            status = TenderFreshnessStatus.EXPIRED
            is_stale = False
            reason = "Срок подачи заявок завершён."
            due_text = ""
        else:
            is_stale = bool(forced_reason) or current >= due
            if verification.status in {
                TenderVerificationStatus.MISSING,
                TenderVerificationStatus.UNVERIFIED,
            }:
                status = TenderFreshnessStatus.UNVERIFIED
            elif is_stale:
                status = TenderFreshnessStatus.STALE
            elif (
                deadline.seconds_remaining is not None
                and deadline.seconds_remaining <= 48 * 60 * 60
            ):
                status = TenderFreshnessStatus.DUE_SOON
            else:
                status = TenderFreshnessStatus.FRESH
            reason = forced_reason or (
                "Наступило время повторной проверки."
                if is_stale
                else _fresh_reason(deadline, interval)
            )
            due_text = _iso_utc(due)

        return TenderFreshnessState(
            canonical_key=verification.canonical_key,
            status=status,
            last_verified_at=_iso_utc(last_verified),
            verification_due_at=due_text,
            is_stale=is_stale,
            stale_reason=reason,
            deadline_original=deadline.original_value,
            source_timezone=deadline.source_timezone,
            timezone_status=deadline.timezone_status,
            deadline_utc=deadline.deadline_utc,
            user_timezone=deadline.user_timezone,
            deadline_user_local=deadline.deadline_user_local,
            seconds_remaining=deadline.seconds_remaining,
            recheck_interval_minutes=interval,
            deadline_expired=deadline_expired,
            updated_at=_iso_utc(current),
        )


def normalize_application_deadline(
    tender: UnifiedTender,
    *,
    now: datetime | str | None = None,
    user_timezone: str | tzinfo | None = None,
) -> DeadlineNormalization:
    """Preserve the source value and produce UTC/user-local projections.

    Naive datetimes are never silently treated as Moscow time. They are only
    localized when the provider explicitly supplied a valid timezone name or
    offset. Otherwise the timezone is marked unknown and UTC is left empty.
    """

    current = _aware_datetime(now) if now is not None else _utc_now_dt()
    user_zone = _resolve_user_timezone(user_timezone)
    user_zone_name = _timezone_name(user_zone)
    metadata = tender.raw_metadata
    field_metadata = _deadline_field_metadata(metadata)

    original = str(
        field_metadata.get("original_value")
        or field_metadata.get("original")
        or metadata.get("application_deadline_original")
        or metadata.get("deadline_original")
        or (
            tender.application_deadline.isoformat()
            if tender.application_deadline is not None
            else ""
        )
    ).strip()
    source_timezone = str(
        field_metadata.get("source_timezone")
        or field_metadata.get("timezone")
        or metadata.get("application_deadline_timezone")
        or metadata.get("deadline_timezone")
        or ""
    ).strip()

    value = tender.application_deadline
    if value is None:
        return DeadlineNormalization(
            original_value=original,
            source_timezone=source_timezone,
            timezone_status=DeadlineTimezoneStatus.MISSING,
            deadline_utc="",
            user_timezone=user_zone_name,
            deadline_user_local="",
            seconds_remaining=None,
        )

    if value.tzinfo is not None and value.utcoffset() is not None:
        aware = value
        timezone_status = DeadlineTimezoneStatus.EXPLICIT
        if not source_timezone:
            source_timezone = _timezone_name(value.tzinfo)
    else:
        source_zone = _parse_timezone(source_timezone)
        if source_zone is None:
            status = (
                DeadlineTimezoneStatus.INVALID
                if source_timezone
                else DeadlineTimezoneStatus.UNKNOWN
            )
            return DeadlineNormalization(
                original_value=original,
                source_timezone=source_timezone,
                timezone_status=status,
                deadline_utc="",
                user_timezone=user_zone_name,
                deadline_user_local="",
                seconds_remaining=None,
            )
        aware = value.replace(tzinfo=source_zone)
        timezone_status = DeadlineTimezoneStatus.SOURCE_ZONE

    deadline_utc = aware.astimezone(timezone.utc)
    user_local = deadline_utc.astimezone(user_zone)
    remaining = int((deadline_utc - current.astimezone(timezone.utc)).total_seconds())
    return DeadlineNormalization(
        original_value=original,
        source_timezone=source_timezone,
        timezone_status=timezone_status,
        deadline_utc=_iso_utc(deadline_utc),
        user_timezone=user_zone_name,
        deadline_user_local=user_local.isoformat(timespec="seconds"),
        seconds_remaining=remaining,
    )


def _recheck_policy(
    verification: TenderVerificationResult,
    deadline: DeadlineNormalization,
) -> tuple[int, str]:
    metadata = verification.tender.raw_metadata
    if verification.status in {
        TenderVerificationStatus.MISSING,
        TenderVerificationStatus.UNVERIFIED,
    }:
        return 0, "Критичные данные ещё не были подтверждены."
    if verification.unresolved_conflict_count:
        return 0, "Есть нерешённый конфликт критичных данных."
    if (
        verification.tender.application_deadline is not None
        and not deadline.timezone_confirmed
    ):
        return 0, "Часовой пояс срока подачи не подтверждён."
    if _metadata_flag(
        metadata,
        "official_source_unavailable",
        "verification_required",
        "has_changes",
        "documents_changed",
        "clarifications_changed",
        "new_revision_available",
    ):
        return 0, "Источник сообщил об изменениях или требует перепроверки."

    remaining = deadline.seconds_remaining
    if remaining is not None:
        if remaining <= 6 * 60 * 60:
            return 30, ""
        if remaining <= 24 * 60 * 60:
            return 60, ""
        if remaining <= 48 * 60 * 60:
            return 180, ""

    if verification.status in {
        TenderVerificationStatus.AGGREGATOR_ONLY,
        TenderVerificationStatus.PUBLIC_CARD,
        TenderVerificationStatus.INCOMPLETE,
        TenderVerificationStatus.CONFLICT,
    }:
        return 60, ""
    if verification.status == TenderVerificationStatus.CUSTOMER_SITE:
        return 360, ""
    return 24 * 60, ""


def _fresh_reason(
    deadline: DeadlineNormalization,
    interval: int,
) -> str:
    if (
        deadline.seconds_remaining is not None
        and deadline.seconds_remaining <= 48 * 60 * 60
    ):
        return (
            "До окончания подачи менее 48 часов; назначена "
            f"повторная проверка через {interval} мин."
        )
    return f"Данные актуальны; повторная проверка через {interval} мин."


def _deadline_field_metadata(
    metadata: Mapping[str, object],
) -> Mapping[str, object]:
    raw = metadata.get("field_provenance")
    if isinstance(raw, Mapping):
        value = raw.get("application_deadline")
        if isinstance(value, Mapping):
            return value
    return {}


def _metadata_flag(
    metadata: Mapping[str, object],
    *keys: str,
) -> bool:
    return any(_metadata_bool(metadata.get(key)) for key in keys)


def _metadata_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        rendered = value.strip().casefold()
        if rendered in {"1", "true", "yes", "да", "on"}:
            return True
        if rendered in {"", "0", "false", "no", "нет", "off", "none", "null"}:
            return False
    return False


def _parse_timezone(value: str) -> tzinfo | None:
    rendered = value.strip()
    if not rendered:
        return None
    aliases = {
        "utc": timezone.utc,
        "z": timezone.utc,
        "gmt": timezone.utc,
        # MSK is an explicit UTC+03:00 source marker. Use a fixed offset so
        # Windows builds remain functional even without the optional IANA
        # timezone database package.
        "msk": timezone(timedelta(hours=3), name="MSK"),
        "мск": timezone(timedelta(hours=3), name="MSK"),
    }
    lowered = rendered.casefold()
    if lowered in aliases:
        return aliases[lowered]
    offset_match = re.fullmatch(
        r"(?:UTC|GMT)?\s*([+-])(\d{1,2})(?::?(\d{2}))?",
        rendered,
        flags=re.IGNORECASE,
    )
    if offset_match:
        sign = 1 if offset_match.group(1) == "+" else -1
        hours = int(offset_match.group(2))
        minutes = int(offset_match.group(3) or "0")
        if hours > 23 or minutes > 59:
            return None
        return timezone(sign * timedelta(hours=hours, minutes=minutes))
    try:
        return ZoneInfo(rendered)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def _resolve_user_timezone(value: str | tzinfo | None) -> tzinfo:
    if isinstance(value, tzinfo):
        return value
    if isinstance(value, str) and value.strip():
        parsed = _parse_timezone(value)
        if parsed is None:
            raise ValueError(f"Unknown user timezone: {value}")
        return parsed
    return datetime.now().astimezone().tzinfo or timezone.utc


def _timezone_name(value: tzinfo) -> str:
    key = getattr(value, "key", "")
    if key:
        return str(key)
    now = datetime.now(value)
    name = value.tzname(now)
    if name:
        return str(name)
    offset = value.utcoffset(now)
    if offset is None:
        return "UTC"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def _aware_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Freshness timestamps must be timezone-aware")
    return parsed


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "DeadlineNormalization",
    "DeadlineTimezoneStatus",
    "FreshnessBatchResult",
    "TenderFreshnessService",
    "TenderFreshnessState",
    "TenderFreshnessStatus",
    "normalize_application_deadline",
]
