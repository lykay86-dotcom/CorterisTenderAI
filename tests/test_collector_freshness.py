"""Deadline timezone normalization and adaptive freshness tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.freshness import (
    DeadlineTimezoneStatus,
    TenderFreshnessService,
    TenderFreshnessStatus,
    normalize_application_deadline,
)
from app.tenders.collector.verification import TenderVerificationService
from app.tenders.models import TenderSource
from tests.collector_c3_helpers import make_tender


def _verification(tender, *, observed_at: str):
    return TenderVerificationService().verify(
        TenderDeduplicator().deduplicate((tender,)),
        observed_at=observed_at,
    )


def test_aware_deadline_is_projected_to_utc_and_user_timezone() -> None:
    tender = make_tender(
        deadline_day=14,
        raw_metadata={
            "application_deadline_original": "14.07.2026 12:00 UTC",
        },
    )

    normalized = normalize_application_deadline(
        tender,
        now="2026-07-12T12:00:00+00:00",
        user_timezone="+03:00",
    )

    assert normalized.timezone_status == DeadlineTimezoneStatus.EXPLICIT
    assert normalized.deadline_utc == "2026-07-14T12:00:00+00:00"
    assert normalized.deadline_user_local == "2026-07-14T15:00:00+03:00"
    assert normalized.seconds_remaining == 48 * 60 * 60
    assert normalized.original_value == "14.07.2026 12:00 UTC"


def test_naive_deadline_uses_only_explicit_source_timezone() -> None:
    tender = replace(
        make_tender(),
        published_at=None,
        application_deadline=datetime(2026, 7, 14, 12, 0),
        raw_metadata={
            "application_deadline_original": "14.07.2026 12:00",
            "application_deadline_timezone": "+05:00",
        },
    )

    normalized = normalize_application_deadline(
        tender,
        now="2026-07-12T12:00:00+00:00",
        user_timezone="UTC",
    )

    assert normalized.timezone_status == DeadlineTimezoneStatus.SOURCE_ZONE
    assert normalized.deadline_utc == "2026-07-14T07:00:00+00:00"
    assert normalized.source_timezone == "+05:00"


def test_deadline_uses_field_provenance_original_and_timezone() -> None:
    tender = replace(
        make_tender(),
        published_at=None,
        application_deadline=datetime(2026, 7, 14, 18, 30),
        raw_metadata={
            "application_deadline_original": "fallback",
            "application_deadline_timezone": "UTC",
            "field_provenance": {
                "application_deadline": {
                    "original_value": "14.07.2026 18:30 МСК",
                    "source_timezone": "MSK",
                }
            },
        },
    )

    normalized = normalize_application_deadline(
        tender,
        now="2026-07-12T12:00:00+00:00",
        user_timezone="UTC",
    )

    assert normalized.original_value == "14.07.2026 18:30 МСК"
    assert normalized.source_timezone == "MSK"
    assert normalized.deadline_utc == "2026-07-14T15:30:00+00:00"
    assert normalized.deadline_user_local == "2026-07-14T15:30:00+00:00"


def test_naive_deadline_without_timezone_is_marked_stale() -> None:
    tender = replace(
        make_tender(),
        published_at=None,
        application_deadline=datetime(2026, 7, 14, 12, 0),
    )
    verification = _verification(
        tender,
        observed_at="2026-07-12T12:00:00+00:00",
    )

    state = TenderFreshnessService(
        user_timezone="UTC"
    ).evaluate(
        verification,
        now="2026-07-12T12:00:00+00:00",
    ).items[0]

    assert state.status == TenderFreshnessStatus.STALE
    assert state.is_stale
    assert state.timezone_status == DeadlineTimezoneStatus.UNKNOWN
    assert not state.deadline_utc
    assert "часовой пояс" in state.stale_reason.casefold()


def test_deadline_under_48_hours_uses_adaptive_recheck() -> None:
    tender = make_tender(deadline_day=14)
    verification = _verification(
        tender,
        observed_at="2026-07-12T13:00:00+00:00",
    )

    state = TenderFreshnessService(
        user_timezone="UTC"
    ).evaluate(
        verification,
        now="2026-07-12T13:00:00+00:00",
    ).items[0]

    assert state.status == TenderFreshnessStatus.DUE_SOON
    assert state.recheck_interval_minutes == 180
    assert state.verification_due_at == "2026-07-12T16:00:00+00:00"
    assert not state.is_stale


def test_deadline_under_24_and_6_hours_uses_faster_rechecks() -> None:
    tender = make_tender(deadline_day=13)
    verification = _verification(
        tender,
        observed_at="2026-07-12T13:00:00+00:00",
    )
    under_24 = TenderFreshnessService(user_timezone="UTC").evaluate(
        verification,
        now="2026-07-12T13:00:00+00:00",
    ).items[0]

    near_deadline = replace(
        tender,
        application_deadline=datetime(
            2026,
            7,
            12,
            17,
            0,
            tzinfo=timezone.utc,
        ),
    )
    near_verification = _verification(
        near_deadline,
        observed_at="2026-07-12T13:00:00+00:00",
    )
    under_6 = TenderFreshnessService(user_timezone="UTC").evaluate(
        near_verification,
        now="2026-07-12T13:00:00+00:00",
    ).items[0]

    assert under_24.recheck_interval_minutes == 60
    assert under_6.recheck_interval_minutes == 30


def test_source_failure_and_document_change_force_stale() -> None:
    for flag in ("official_source_unavailable", "documents_changed"):
        tender = make_tender(
            raw_metadata={
                flag: True,
                "application_security": "0",
                "contract_security": "0",
                "documentation_url": "https://example.org/docs",
            }
        )
        verification = _verification(
            tender,
            observed_at="2026-07-12T12:00:00+00:00",
        )

        state = TenderFreshnessService(user_timezone="UTC").evaluate(
            verification,
            now="2026-07-12T12:00:00+00:00",
        ).items[0]

        assert state.status == TenderFreshnessStatus.STALE
        assert state.is_stale
        assert state.recheck_interval_minutes == 0
        assert state.verification_due_at == "2026-07-12T12:00:00+00:00"


def test_false_string_change_flag_does_not_force_stale() -> None:
    tender = make_tender(
        raw_metadata={
            "documents_changed": "false",
            "official_source_unavailable": "0",
            "application_security": "0",
            "contract_security": "0",
            "documentation_url": "https://example.org/docs",
        }
    )
    verification = _verification(
        tender,
        observed_at="2026-07-12T12:00:00+00:00",
    )

    state = TenderFreshnessService(user_timezone="UTC").evaluate(
        verification,
        now="2026-07-12T12:00:00+00:00",
    ).items[0]

    assert state.status == TenderFreshnessStatus.FRESH
    assert not state.is_stale
    assert state.recheck_interval_minutes == 24 * 60


def test_aggregator_only_is_rechecked_hourly() -> None:
    tender = make_tender(
        source=TenderSource.CUSTOM,
        raw_metadata={
            "aggregator": True,
            "source_kind": "aggregator",
            "application_security": "0",
            "contract_security": "0",
            "documentation_url": "https://example.org/docs",
        },
    )
    verification = _verification(
        tender,
        observed_at="2026-07-12T12:00:00+00:00",
    )

    state = TenderFreshnessService(
        user_timezone="UTC"
    ).evaluate(
        verification,
        now="2026-07-12T12:00:00+00:00",
    ).items[0]

    assert state.recheck_interval_minutes == 60
    assert state.verification_due_at == "2026-07-12T13:00:00+00:00"


def test_expired_deadline_is_not_scheduled_for_reverification() -> None:
    tender = make_tender(deadline_day=11)
    verification = _verification(
        tender,
        observed_at="2026-07-12T12:00:00+00:00",
    )

    state = TenderFreshnessService(
        user_timezone=timezone.utc
    ).evaluate(
        verification,
        now="2026-07-12T12:00:00+00:00",
    ).items[0]

    assert state.status == TenderFreshnessStatus.EXPIRED
    assert state.deadline_expired
    assert not state.is_stale
    assert not state.verification_due_at
