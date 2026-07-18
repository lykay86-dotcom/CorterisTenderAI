from datetime import datetime, timedelta, timezone

from app.tenders.collector.source_monitoring import (
    SourceFreshness,
    SourceMonitoringPolicy,
    classify_freshness,
)


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


def test_exact_ttl_boundary_is_stale() -> None:
    ttl = timedelta(hours=24)
    assert classify_freshness((NOW - ttl + timedelta(seconds=1)).isoformat(), NOW, ttl) is SourceFreshness.CURRENT
    assert classify_freshness((NOW - ttl).isoformat(), NOW, ttl) is SourceFreshness.STALE
    assert classify_freshness((NOW - ttl - timedelta(seconds=1)).isoformat(), NOW, ttl) is SourceFreshness.STALE


def test_naive_malformed_and_excess_future_fail_closed() -> None:
    policy = SourceMonitoringPolicy()
    ttl = policy.connection_ttl
    assert classify_freshness("2026-07-18T12:00:00", NOW, ttl) is SourceFreshness.INVALID
    assert classify_freshness("not-a-time", NOW, ttl) is SourceFreshness.INVALID
    future = NOW + policy.max_future_skew + timedelta(seconds=1)
    assert classify_freshness(future.isoformat(), NOW, ttl) is SourceFreshness.INVALID


def test_small_aware_future_skew_is_current() -> None:
    policy = SourceMonitoringPolicy()
    value = NOW + policy.max_future_skew
    assert classify_freshness(value.isoformat(), NOW, policy.connection_ttl) is SourceFreshness.CURRENT
