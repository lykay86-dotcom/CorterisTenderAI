"""Deterministic in-memory aggregation owner for RM-147."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime, timedelta, tzinfo
import hashlib
import json

from app.tenders.analytics.contracts import (
    AnalyticsConflict,
    AnalyticsEvidence,
    AnalyticsEvidenceQuality,
    AnalyticsProviderOutcome,
    AnalyticsSourceCoverage,
    AnalyticsSourceObservation,
    AnalyticsState,
    AnalyticsTenderFact,
    TenderAnalyticsMetric,
    TenderAnalyticsPoint,
    TenderAnalyticsQuery,
    TenderAnalyticsSelection,
    TenderAnalyticsSnapshot,
)
from app.tenders.analytics.metric_catalog import METRIC_BY_ID
from app.tenders.analytics.time_contract import (
    iter_time_buckets,
    parse_aware_timestamp,
    resolve_timezone,
)


STATUS_ORDER = (
    "published",
    "accepting_applications",
    "applications_closed",
    "review",
    "completed",
    "cancelled",
    "unknown",
)
DEADLINE_ORDER = (
    "expired",
    "due_today",
    "due_1_3_days",
    "due_4_7_days",
    "due_later",
    "unknown_or_unconfirmed",
)
MAX_ANALYTICS_RECORDS = 10_000
_INCOMPLETE_OUTCOMES = frozenset(
    {
        "failed",
        "timed_out",
        "cancelled",
        "not_configured",
        "disabled",
        "unsupported",
        "skipped",
        "circuit_open",
        "unknown",
    }
)


def _status(value: str) -> str:
    normalized = value.strip().casefold()
    return normalized if normalized in STATUS_ORDER[:-1] else "unknown"


def _reason(field_name: str) -> str:
    normalized = field_name.strip().casefold()
    names = {
        "status": "unresolved_status_conflict",
        "application_deadline": "unresolved_deadline_conflict",
        "first_seen_at": "unresolved_discovery_time_conflict",
        "source": "unresolved_source_conflict",
        "source_id": "unresolved_source_conflict",
    }
    return names.get(normalized, "unresolved_metadata_conflict")


def _point_id(metric_id: str, version: str, query_fingerprint: str, bucket_key: str) -> str:
    material = f"{metric_id}|{version}|{query_fingerprint}|{bucket_key}".encode()
    return f"ta-{hashlib.sha256(material).hexdigest()[:24]}"


def _quality(state: AnalyticsState) -> AnalyticsEvidenceQuality:
    return {
        AnalyticsState.CONFLICTED: AnalyticsEvidenceQuality.CONFLICTED,
        AnalyticsState.PARTIAL: AnalyticsEvidenceQuality.PARTIAL,
        AnalyticsState.STALE: AnalyticsEvidenceQuality.STALE,
        AnalyticsState.ERROR: AnalyticsEvidenceQuality.UNKNOWN,
        AnalyticsState.TOO_LARGE: AnalyticsEvidenceQuality.UNKNOWN,
    }.get(state, AnalyticsEvidenceQuality.COMPLETE)


def _coverage(
    records: tuple[AnalyticsTenderFact, ...],
    requested_ids: tuple[str, ...],
    outcomes: tuple[AnalyticsProviderOutcome, ...],
) -> tuple[AnalyticsSourceCoverage, ...]:
    outcome_by_source: dict[str, AnalyticsProviderOutcome] = {}
    for ordered_outcome in sorted(
        outcomes,
        key=lambda item: (
            item.source_id,
            item.observed_at.isoformat() if item.observed_at is not None else "",
            item.run_id,
        ),
    ):
        outcome_by_source[ordered_outcome.source_id] = ordered_outcome
    record_sources = {record.source_id.strip().casefold() or "unknown" for record in records}
    source_ids = sorted(set(requested_ids) | record_sources | set(outcome_by_source))
    coverage: list[AnalyticsSourceCoverage] = []
    for source_id in source_ids:
        latest_outcome = outcome_by_source.get(source_id)
        requested = not requested_ids or source_id in requested_ids
        if latest_outcome is not None:
            coverage.append(
                AnalyticsSourceCoverage(
                    source_id=source_id,
                    requested=requested,
                    enabled=True,
                    outcome=latest_outcome.outcome,
                    observed_at=latest_outcome.observed_at,
                    freshness="unknown",
                    item_count=latest_outcome.item_count,
                    reason_code=latest_outcome.reason_code,
                )
            )
            continue
        source_records = tuple(record for record in records if record.source_id == source_id)
        observed = max(
            (
                parsed
                for record in source_records
                if (parsed := parse_aware_timestamp(record.last_seen_at, resolve_timezone("UTC")))
                is not None
            ),
            default=None,
        )
        coverage.append(
            AnalyticsSourceCoverage(
                source_id=source_id,
                requested=requested,
                enabled=True,
                outcome="success",
                observed_at=observed,
                freshness="unknown",
                item_count=len(source_records),
                reason_code="",
            )
        )
    return tuple(coverage)


def _metric_evidence(
    *,
    state: AnalyticsState,
    coverage: tuple[AnalyticsSourceCoverage, ...],
    contributor_count: int,
    missing_count: int = 0,
    excluded_count: int = 0,
    unknown_time_count: int = 0,
    conflict_count: int = 0,
    reason_codes: tuple[str, ...] = (),
) -> AnalyticsEvidence:
    run_ids: tuple[str, ...] = ()
    return AnalyticsEvidence(
        quality=_quality(state),
        source_ids=tuple(item.source_id for item in coverage),
        run_ids=run_ids,
        contributor_count=contributor_count,
        missing_count=missing_count,
        excluded_count=excluded_count,
        unknown_time_count=unknown_time_count,
        conflict_count=conflict_count,
        reason_codes=tuple(sorted(set(reason_codes))),
    )


def _point(
    *,
    metric_id: str,
    bucket_key: str,
    label: str,
    contributors: tuple[str, ...],
    query: TenderAnalyticsQuery,
    state: AnalyticsState,
    coverage: tuple[AnalyticsSourceCoverage, ...],
    value: int | None = None,
    conflict_count: int = 0,
    reasons: tuple[str, ...] = (),
    bucket_start: datetime | None = None,
    bucket_end: datetime | None = None,
) -> TenderAnalyticsPoint:
    definition = METRIC_BY_ID[metric_id]
    ordered = tuple(sorted(set(contributors)))
    evidence = _metric_evidence(
        state=state,
        coverage=coverage,
        contributor_count=len(ordered),
        conflict_count=conflict_count,
        reason_codes=reasons,
    )
    return TenderAnalyticsPoint(
        point_id=_point_id(metric_id, definition.version, query.fingerprint, bucket_key),
        bucket_key=bucket_key,
        bucket_label=label,
        value=len(ordered) if value is None else value,
        contributor_ids=ordered,
        evidence=evidence,
        bucket_start=bucket_start,
        bucket_end=bucket_end,
    )


def _semantic_fingerprint(
    query: TenderAnalyticsQuery,
    state: AnalyticsState,
    coverage: tuple[AnalyticsSourceCoverage, ...],
    metrics: tuple[TenderAnalyticsMetric, ...],
) -> str:
    projection = {
        "query": query.fingerprint,
        "state": state.value,
        "coverage": [
            {
                "source_id": item.source_id,
                "requested": item.requested,
                "outcome": item.outcome,
                "observed_at": item.observed_at.isoformat() if item.observed_at else None,
                "item_count": item.item_count,
                "reason_code": item.reason_code,
            }
            for item in coverage
        ],
        "metrics": [
            {
                "id": metric.metric_id,
                "state": metric.state.value,
                "points": [
                    {
                        "id": point.point_id,
                        "bucket": point.bucket_key,
                        "value": point.value,
                        "contributors": point.contributor_ids,
                        "conflicts": point.evidence.conflict_count,
                        "reasons": point.evidence.reason_codes,
                    }
                    for point in metric.points
                ],
                "unknown_time": metric.evidence.unknown_time_count,
            }
            for metric in metrics
        ],
    }
    encoded = json.dumps(projection, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class TenderAnalyticsService:
    """The sole owner of RM-147 metric membership and ordering."""

    def aggregate(
        self,
        query: TenderAnalyticsQuery,
        records: tuple[AnalyticsTenderFact, ...],
        *,
        source_observations: tuple[AnalyticsSourceObservation, ...] = (),
        provider_outcomes: tuple[AnalyticsProviderOutcome, ...] = (),
        conflicts: tuple[AnalyticsConflict, ...] = (),
        as_of: datetime,
        generation: int,
    ) -> TenderAnalyticsSnapshot:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        zone = resolve_timezone(query.interval.timezone_name)
        normalized_records = tuple(sorted(records, key=lambda item: item.registry_key))
        if len(normalized_records) > MAX_ANALYTICS_RECORDS:
            coverage = _coverage(normalized_records, query.source_ids, provider_outcomes)
            metrics = tuple(
                TenderAnalyticsMetric(
                    item.metric_id,
                    item.version,
                    item.title,
                    item.unit,
                    AnalyticsState.TOO_LARGE,
                    (),
                    _metric_evidence(
                        state=AnalyticsState.TOO_LARGE,
                        coverage=coverage,
                        contributor_count=0,
                        excluded_count=len(normalized_records),
                        reason_codes=("record_limit_exceeded",),
                    ),
                )
                for item in sorted(METRIC_BY_ID.values(), key=lambda value: value.order)
            )
            fingerprint = _semantic_fingerprint(
                query,
                AnalyticsState.TOO_LARGE,
                coverage,
                metrics,
            )
            return TenderAnalyticsSnapshot(
                query=query,
                generation=generation,
                as_of=as_of,
                state=AnalyticsState.TOO_LARGE,
                coverage=coverage,
                metrics=metrics,
                fingerprint=fingerprint,
                reason_codes=("record_limit_exceeded",),
            )
        conflict_fields: dict[str, set[str]] = defaultdict(set)
        for conflict in conflicts:
            if conflict.unresolved:
                conflict_fields[conflict.registry_key].add(conflict.field_name.casefold())

        filtered = tuple(
            record
            for record in normalized_records
            if (query.include_archived or not record.archived)
            and (not query.source_ids or record.source_id.casefold() in query.source_ids)
            and (not query.statuses or _status(record.status) in query.statuses)
            and (not query.laws or record.law.casefold() in query.laws)
        )
        coverage = _coverage(filtered, query.source_ids, provider_outcomes)
        has_partial = any(
            item.requested and item.outcome in _INCOMPLETE_OUTCOMES for item in coverage
        )
        bucket_conflicts = {
            key: fields
            for key, fields in conflict_fields.items()
            if fields & {"status", "application_deadline", "first_seen_at", "source", "source_id"}
        }
        if bucket_conflicts:
            snapshot_state = AnalyticsState.CONFLICTED
        elif has_partial:
            snapshot_state = AnalyticsState.PARTIAL
        elif not filtered and not source_observations:
            snapshot_state = AnalyticsState.EMPTY
        else:
            snapshot_state = AnalyticsState.READY

        metrics = (
            self._discovered(query, filtered, coverage, snapshot_state, conflict_fields, zone),
            self._statuses(query, filtered, coverage, snapshot_state, conflict_fields),
            self._sources(
                query,
                filtered,
                source_observations,
                coverage,
                snapshot_state,
                conflict_fields,
                zone,
            ),
            self._deadlines(
                query,
                filtered,
                coverage,
                snapshot_state,
                conflict_fields,
                as_of.astimezone(zone),
                zone,
            ),
        )
        fingerprint = _semantic_fingerprint(query, snapshot_state, coverage, metrics)
        return TenderAnalyticsSnapshot(
            query=query,
            generation=generation,
            as_of=as_of,
            state=snapshot_state,
            coverage=coverage,
            metrics=metrics,
            fingerprint=fingerprint,
        )

    @staticmethod
    def _discovered(
        query: TenderAnalyticsQuery,
        records: tuple[AnalyticsTenderFact, ...],
        coverage: tuple[AnalyticsSourceCoverage, ...],
        state: AnalyticsState,
        conflicts: Mapping[str, set[str]],
        zone: tzinfo,
    ) -> TenderAnalyticsMetric:
        definition = METRIC_BY_ID["tenders_discovered"]
        buckets = iter_time_buckets(query.interval, query.grain)
        memberships: dict[str, list[str]] = {item.bucket_key: [] for item in buckets}
        unknown_time = 0
        conflict_count = 0
        reasons: list[str] = []
        for record in records:
            if "first_seen_at" in conflicts.get(record.registry_key, set()):
                conflict_count += 1
                reasons.append(_reason("first_seen_at"))
                unknown_time += 1
                continue
            timestamp = parse_aware_timestamp(record.first_seen_at, zone)
            if timestamp is None:
                unknown_time += 1
                continue
            for bucket in buckets:
                if bucket.start_inclusive <= timestamp < bucket.end_exclusive:
                    memberships[bucket.bucket_key].append(record.registry_key)
                    break
        points = tuple(
            _point(
                metric_id=definition.metric_id,
                bucket_key=bucket.bucket_key,
                label=bucket.bucket_key,
                contributors=tuple(memberships[bucket.bucket_key]),
                query=query,
                state=state,
                coverage=coverage,
                bucket_start=bucket.start_inclusive,
                bucket_end=bucket.end_exclusive,
            )
            for bucket in buckets
        )
        evidence = _metric_evidence(
            state=state,
            coverage=coverage,
            contributor_count=sum(point.value for point in points),
            unknown_time_count=unknown_time,
            conflict_count=conflict_count,
            reason_codes=tuple(reasons),
        )
        return TenderAnalyticsMetric(
            definition.metric_id,
            definition.version,
            definition.title,
            definition.unit,
            state,
            points,
            evidence,
        )

    @staticmethod
    def _statuses(
        query: TenderAnalyticsQuery,
        records: tuple[AnalyticsTenderFact, ...],
        coverage: tuple[AnalyticsSourceCoverage, ...],
        state: AnalyticsState,
        conflicts: Mapping[str, set[str]],
    ) -> TenderAnalyticsMetric:
        definition = METRIC_BY_ID["tenders_by_status"]
        memberships: dict[str, list[str]] = {key: [] for key in STATUS_ORDER}
        point_conflicts: dict[str, int] = defaultdict(int)
        point_reasons: dict[str, list[str]] = defaultdict(list)
        for record in records:
            key = _status(record.status)
            if "status" in conflicts.get(record.registry_key, set()):
                key = "unknown"
                point_conflicts[key] += 1
                point_reasons[key].append(_reason("status"))
            memberships[key].append(record.registry_key)
        points = tuple(
            _point(
                metric_id=definition.metric_id,
                bucket_key=key,
                label=key,
                contributors=tuple(memberships[key]),
                query=query,
                state=state,
                coverage=coverage,
                conflict_count=point_conflicts[key],
                reasons=tuple(point_reasons[key]),
            )
            for key in STATUS_ORDER
        )
        evidence = _metric_evidence(
            state=state,
            coverage=coverage,
            contributor_count=len(records),
            conflict_count=sum(point_conflicts.values()),
            reason_codes=tuple(reason for values in point_reasons.values() for reason in values),
        )
        return TenderAnalyticsMetric(
            definition.metric_id,
            definition.version,
            definition.title,
            definition.unit,
            state,
            points,
            evidence,
        )

    @staticmethod
    def _sources(
        query: TenderAnalyticsQuery,
        records: tuple[AnalyticsTenderFact, ...],
        observations: tuple[AnalyticsSourceObservation, ...],
        coverage: tuple[AnalyticsSourceCoverage, ...],
        state: AnalyticsState,
        conflicts: Mapping[str, set[str]],
        zone: tzinfo,
    ) -> TenderAnalyticsMetric:
        definition = METRIC_BY_ID["source_observations"]
        allowed_keys = {record.registry_key for record in records}
        effective = observations or tuple(
            AnalyticsSourceObservation(
                record.registry_key,
                record.source_id,
                record.external_id,
                record.first_seen_at,
            )
            for record in records
        )
        identities: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
        contributors: dict[str, set[str]] = defaultdict(set)
        for item in effective:
            if item.registry_key not in allowed_keys:
                continue
            source_id = item.source_id.casefold() or "unknown"
            if query.source_ids and source_id not in query.source_ids:
                continue
            observed = parse_aware_timestamp(item.first_seen_at, zone)
            if observed is None or not (
                query.interval.start_inclusive.astimezone(zone)
                <= observed
                < query.interval.end_exclusive.astimezone(zone)
            ):
                continue
            identities[source_id].add((item.registry_key, source_id, item.external_id))
            contributors[source_id].add(item.registry_key)
        source_order = tuple(sorted(identities))
        points = tuple(
            _point(
                metric_id=definition.metric_id,
                bucket_key=source_id,
                label=source_id,
                contributors=tuple(contributors[source_id]),
                value=len(identities[source_id]),
                query=query,
                state=state,
                coverage=coverage,
            )
            for source_id in source_order
        )
        evidence = _metric_evidence(
            state=state,
            coverage=coverage,
            contributor_count=len({key for keys in contributors.values() for key in keys}),
        )
        return TenderAnalyticsMetric(
            definition.metric_id,
            definition.version,
            definition.title,
            definition.unit,
            state,
            points,
            evidence,
        )

    @staticmethod
    def _deadlines(
        query: TenderAnalyticsQuery,
        records: tuple[AnalyticsTenderFact, ...],
        coverage: tuple[AnalyticsSourceCoverage, ...],
        state: AnalyticsState,
        conflicts: Mapping[str, set[str]],
        as_of: datetime,
        zone: tzinfo,
    ) -> TenderAnalyticsMetric:
        definition = METRIC_BY_ID["application_deadline_horizon"]
        memberships: dict[str, list[str]] = {key: [] for key in DEADLINE_ORDER}
        point_conflicts: dict[str, int] = defaultdict(int)
        reasons: dict[str, list[str]] = defaultdict(list)
        today = as_of.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        day_four = today + timedelta(days=4)
        day_eight = today + timedelta(days=8)
        for record in records:
            key = "unknown_or_unconfirmed"
            if "application_deadline" in conflicts.get(record.registry_key, set()):
                point_conflicts[key] += 1
                reasons[key].append(_reason("application_deadline"))
            else:
                deadline = parse_aware_timestamp(record.application_deadline, zone)
                if deadline is not None:
                    if deadline < today:
                        key = "expired"
                    elif deadline < tomorrow:
                        key = "due_today"
                    elif deadline < day_four:
                        key = "due_1_3_days"
                    elif deadline < day_eight:
                        key = "due_4_7_days"
                    else:
                        key = "due_later"
            memberships[key].append(record.registry_key)
        points = tuple(
            _point(
                metric_id=definition.metric_id,
                bucket_key=key,
                label=key,
                contributors=tuple(memberships[key]),
                query=query,
                state=state,
                coverage=coverage,
                conflict_count=point_conflicts[key],
                reasons=tuple(reasons[key]),
            )
            for key in DEADLINE_ORDER
        )
        evidence = _metric_evidence(
            state=state,
            coverage=coverage,
            contributor_count=len(records),
            missing_count=0,
            conflict_count=sum(point_conflicts.values()),
            reason_codes=tuple(reason for values in reasons.values() for reason in values),
        )
        return TenderAnalyticsMetric(
            definition.metric_id,
            definition.version,
            definition.title,
            definition.unit,
            state,
            points,
            evidence,
        )


def resolve_selection(
    snapshot: TenderAnalyticsSnapshot,
    metric_id: str,
    point_id: str,
) -> TenderAnalyticsSelection:
    metric = next((item for item in snapshot.metrics if item.metric_id == metric_id), None)
    if metric is None:
        raise ValueError("unknown_metric")
    point = next((item for item in metric.points if item.point_id == point_id), None)
    if point is None:
        raise ValueError("unknown_point")
    return TenderAnalyticsSelection(
        metric_id=metric_id,
        point_id=point_id,
        snapshot_fingerprint=snapshot.fingerprint,
        contributor_ids=point.contributor_ids,
    )


__all__ = [
    "DEADLINE_ORDER",
    "MAX_ANALYTICS_RECORDS",
    "STATUS_ORDER",
    "TenderAnalyticsService",
    "resolve_selection",
]
