"""Aware calendar boundary helpers for RM-147."""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta, timezone, tzinfo
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.tenders.analytics.contracts import (
    AnalyticsGrain,
    AnalyticsInterval,
    AnalyticsTimeBucket,
)


def resolve_timezone(name: str) -> tzinfo:
    normalized = name.strip()
    if normalized.casefold() in {"utc", "z", "gmt"}:
        return timezone.utc
    if normalized == "Europe/Moscow":
        try:
            return ZoneInfo(normalized)
        except ZoneInfoNotFoundError:
            return timezone(timedelta(hours=3), name="Europe/Moscow")
    match = re.fullmatch(r"([+-])(\d{2}):(\d{2})", normalized)
    if match:
        sign = 1 if match.group(1) == "+" else -1
        hours, minutes = int(match.group(2)), int(match.group(3))
        if hours > 23 or minutes > 59:
            raise ValueError("invalid timezone offset")
        return timezone(sign * timedelta(hours=hours, minutes=minutes))
    try:
        return ZoneInfo(normalized)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unsupported timezone: {name}") from exc


def _next_boundary(value: datetime, grain: AnalyticsGrain) -> datetime:
    if grain is AnalyticsGrain.DAY:
        return value + timedelta(days=1)
    if grain is AnalyticsGrain.WEEK:
        return value + timedelta(days=7)
    days = monthrange(value.year, value.month)[1]
    return (value + timedelta(days=days)).replace(day=1)


def _calendar_floor(value: datetime, grain: AnalyticsGrain) -> datetime:
    midnight = value.replace(hour=0, minute=0, second=0, microsecond=0)
    if grain is AnalyticsGrain.DAY:
        return midnight
    if grain is AnalyticsGrain.WEEK:
        return midnight - timedelta(days=midnight.weekday())
    return midnight.replace(day=1)


def iter_time_buckets(
    interval: AnalyticsInterval,
    grain: AnalyticsGrain,
) -> tuple[AnalyticsTimeBucket, ...]:
    zone = resolve_timezone(interval.timezone_name)
    start = interval.start_inclusive.astimezone(zone)
    end = interval.end_exclusive.astimezone(zone)
    cursor = start
    buckets: list[AnalyticsTimeBucket] = []
    while cursor < end:
        floor = _calendar_floor(cursor, grain)
        boundary = _next_boundary(floor, grain)
        bucket_end = min(boundary, end)
        key = {
            AnalyticsGrain.DAY: cursor.date().isoformat(),
            AnalyticsGrain.WEEK: f"{floor.date().isoformat()}-week",
            AnalyticsGrain.MONTH: floor.strftime("%Y-%m"),
        }[grain]
        buckets.append(AnalyticsTimeBucket(key, cursor, bucket_end))
        cursor = bucket_end
    return tuple(buckets)


def parse_aware_timestamp(value: str, zone: tzinfo) -> datetime | None:
    if not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(zone)


__all__ = ["iter_time_buckets", "parse_aware_timestamp", "resolve_timezone"]
