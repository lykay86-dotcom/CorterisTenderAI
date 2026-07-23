from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest

from app.tenders.collector.aggregator_discovery import (
    AggregatorDiscoveryRepository,
    AggregatorDiscoveryStatus,
    AggregatorOfficialVerificationService,
    OfficialIdentityDecision,
    match_official_identity,
)
from app.tenders.models import TenderSource
from tests.collector_c3_helpers import make_tender


def _aggregator(*, external_id: str = "aggregator-1", raw_metadata=None):
    return make_tender(
        source=TenderSource.CUSTOM,
        external_id=external_id,
        amount="9999999",
        raw_metadata=raw_metadata
        or {
            "aggregator": True,
            "discovery_only": True,
            "source_kind": "aggregator",
        },
    )


def test_only_explicit_discovery_items_can_enter_queue(tmp_path) -> None:
    repository = AggregatorDiscoveryRepository(tmp_path / "registry.sqlite3")

    try:
        repository.enqueue(make_tender())
    except ValueError as exc:
        assert "aggregator" in str(exc)
    else:
        raise AssertionError("official tender must not enter aggregator queue")


def test_enqueue_is_deduplicated_and_cannot_influence_decision(tmp_path) -> None:
    repository = AggregatorDiscoveryRepository(tmp_path / "registry.sqlite3")

    first = repository.enqueue(_aggregator(), discovered_at="2026-07-13T08:00:00+00:00")
    second = repository.enqueue(_aggregator(), discovered_at="2026-07-13T09:00:00+00:00")

    assert first.discovery_id == second.discovery_id
    assert second.status == AggregatorDiscoveryStatus.PENDING_OFFICIAL_VERIFICATION
    assert second.first_discovered_at == "2026-07-13T08:00:00+00:00"
    assert second.last_discovered_at == "2026-07-13T09:00:00+00:00"
    assert not second.can_influence_decision
    assert second.candidate.price.amount == 9999999
    assert len(repository.list_pending()) == 1


def test_official_verification_accepts_only_eis_or_supplier_portal(tmp_path) -> None:
    repository = AggregatorDiscoveryRepository(tmp_path / "registry.sqlite3")
    discovery = repository.enqueue(_aggregator())

    try:
        repository.resolve(
            discovery.discovery_id,
            official_tender=make_tender(source=TenderSource.CUSTOM),
        )
    except ValueError as exc:
        assert "official" in str(exc)
    else:
        raise AssertionError("custom source must not confirm aggregator data")

    official = make_tender(source=TenderSource.EIS, external_id="official-1")
    resolved = repository.resolve(
        discovery.discovery_id,
        official_tender=official,
    )
    assert resolved.status == AggregatorDiscoveryStatus.OFFICIAL_MATCH_FOUND
    assert resolved.official_registry_key == official.identity_key
    attempts = repository.list_attempts(discovery.discovery_id)
    assert len(attempts) == 1
    assert attempts[0]["outcome"] == OfficialIdentityDecision.MATCH.value


def test_official_candidate_with_different_strong_number_is_rejected(tmp_path) -> None:
    repository = AggregatorDiscoveryRepository(tmp_path / "registry.sqlite3")
    discovery = repository.enqueue(_aggregator())
    wrong = make_tender(
        source=TenderSource.EIS,
        external_id="wrong",
        procurement_number="0373100000126009999",
    )

    resolved = repository.resolve(discovery.discovery_id, official_tender=wrong)

    assert resolved.status == AggregatorDiscoveryStatus.OFFICIAL_MATCH_NOT_FOUND
    assert not resolved.official_registry_key
    assert repository.list_attempts(discovery.discovery_id)[0]["outcome"] == "reject"


def test_weak_identity_requires_manual_review() -> None:
    discovery = make_tender(
        source=TenderSource.CUSTOM,
        external_id="aggregator-weak",
        procurement_number="aggregator-weak",
        customer_inn="",
        raw_metadata={"aggregator": True},
    )
    official = make_tender(source=TenderSource.MOS_SUPPLIER)

    result = match_official_identity(discovery, official)

    assert result.decision == OfficialIdentityDecision.MANUAL_REVIEW


def test_reverification_keeps_immutable_attempt_history(tmp_path) -> None:
    repository = AggregatorDiscoveryRepository(tmp_path / "registry.sqlite3")
    discovery = repository.enqueue(_aggregator())
    repository.resolve(discovery.discovery_id, official_tender=None, note="first")
    repository.enqueue(_aggregator())
    official = make_tender(source=TenderSource.EIS, external_id="official-1")
    repository.resolve(discovery.discovery_id, official_tender=official, note="second")

    attempts = repository.list_attempts(discovery.discovery_id)

    assert [attempt["outcome"] for attempt in attempts] == ["reject", "match"]
    assert [attempt["note"] for attempt in attempts] == ["first", "second"]


def test_failed_lookup_is_recorded_in_attempt_history(tmp_path) -> None:
    repository = AggregatorDiscoveryRepository(tmp_path / "registry.sqlite3")
    discovery = repository.enqueue(_aggregator())

    result = repository.mark_failed(discovery.discovery_id, "network unavailable")

    assert result.status == AggregatorDiscoveryStatus.FAILED
    attempts = repository.list_attempts(discovery.discovery_id)
    assert attempts[0]["outcome"] == "failed"
    assert attempts[0]["note"] == ("Официальная проверка завершилась с безопасно скрытой ошибкой.")
    assert attempts[0]["evidence"] == ("provider_internal_error",)


def test_queue_processor_builds_official_query_without_using_aggregator_values(tmp_path) -> None:
    repository = AggregatorDiscoveryRepository(tmp_path / "registry.sqlite3")
    repository.enqueue(_aggregator())
    queries = []

    def lookup(query):
        queries.append(query)
        return None

    results = AggregatorOfficialVerificationService(repository, lookup).verify_pending()

    assert results[0].status == AggregatorDiscoveryStatus.OFFICIAL_MATCH_NOT_FOUND
    assert queries[0].keywords == (_aggregator().procurement_number,)
    assert queries[0].extra["official_verification"] is True
    assert not repository.list_pending()


def test_queue_capacity_evicts_oldest_terminal_record_but_never_pending(tmp_path) -> None:
    repository = AggregatorDiscoveryRepository(
        tmp_path / "registry.sqlite3",
        max_records=2,
    )
    terminal = repository.enqueue(_aggregator(external_id="terminal"))
    repository.resolve(terminal.discovery_id, official_tender=None)
    pending = repository.enqueue(_aggregator(external_id="pending"))

    newest = repository.enqueue(_aggregator(external_id="newest"))

    with pytest.raises(KeyError):
        repository.get(terminal.discovery_id)
    assert repository.list_attempts(terminal.discovery_id) == ()
    assert repository.get(pending.discovery_id).status == (
        AggregatorDiscoveryStatus.PENDING_OFFICIAL_VERIFICATION
    )
    assert repository.get(newest.discovery_id).status == (
        AggregatorDiscoveryStatus.PENDING_OFFICIAL_VERIFICATION
    )
    with pytest.raises(RuntimeError, match="безопасный лимит"):
        repository.enqueue(_aggregator(external_id="overflow"))


def test_queue_capacity_is_atomic_across_repository_instances(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"
    first = AggregatorDiscoveryRepository(path, max_records=1)
    second = AggregatorDiscoveryRepository(path, max_records=1)
    first.initialize()
    barrier = Barrier(2)

    def enqueue(repository, external_id):
        barrier.wait()
        try:
            repository.enqueue(_aggregator(external_id=external_id))
        except RuntimeError as exc:
            assert "безопасный лимит" in str(exc)
            return "capacity"
        return "success"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            future.result()
            for future in (
                pool.submit(enqueue, first, "first"),
                pool.submit(enqueue, second, "second"),
            )
        )

    assert sorted(results) == ["capacity", "success"]
    assert len(first.list_all()) == 1


def test_attempt_retention_keeps_only_latest_bounded_history(tmp_path) -> None:
    repository = AggregatorDiscoveryRepository(
        tmp_path / "registry.sqlite3",
        max_attempts_per_discovery=2,
    )
    discovery = repository.enqueue(_aggregator())

    for note in ("first", "second", "third"):
        repository.resolve(discovery.discovery_id, official_tender=None, note=note)
        repository.enqueue(_aggregator())

    attempts = repository.list_attempts(discovery.discovery_id)

    assert [attempt["note"] for attempt in attempts] == ["second", "third"]


def test_failure_retry_is_explicit_single_attempt_and_secret_safe(tmp_path) -> None:
    secret = "P8_DISCOVERY_SECRET_SENTINEL"
    repository = AggregatorDiscoveryRepository(tmp_path / "registry.sqlite3")
    repository.enqueue(_aggregator())
    calls = 0

    def lookup(_query):
        nonlocal calls
        calls += 1
        raise RuntimeError(
            f"Authorization: Bearer {secret}; "
            f"https://user:{secret}@example.test/path?token={secret}"
        )

    service = AggregatorOfficialVerificationService(repository, lookup)

    first = service.verify_pending()
    second = service.verify_pending()

    assert calls == 1
    assert first[0].status == AggregatorDiscoveryStatus.FAILED
    assert second == ()
    assert secret not in repr(first)
    assert secret not in repr(repository.list_attempts(first[0].discovery_id))
    assert "example.test" not in repr(repository.list_attempts(first[0].discovery_id))

    repository.enqueue(_aggregator())
    service.verify_pending()
    assert calls == 2


def test_queue_payload_and_manual_note_are_minimized_bounded_and_sanitized(tmp_path) -> None:
    secret = "P8_QUEUE_SECRET_SENTINEL"
    candidate = replace(
        _aggregator(
            raw_metadata={
                "aggregator": True,
                "discovery_only": True,
                "source_kind": "aggregator",
                "api_code": secret,
            }
        ),
        source_url=f"https://example.test/tender/1?api_code={secret}#private",
        description=secret,
    )
    repository = AggregatorDiscoveryRepository(tmp_path / "registry.sqlite3")
    discovery = repository.enqueue(candidate)
    official = make_tender(source=TenderSource.EIS, external_id="official-1")

    resolved = repository.resolve(
        discovery.discovery_id,
        official_tender=official,
        note=f"token={secret} https://example.test/private",
    )
    rendered = repr((resolved, repository.list_attempts(discovery.discovery_id)))

    assert secret not in rendered
    assert "api_code" not in resolved.candidate.raw_metadata
    assert resolved.candidate.description == ""
    assert resolved.candidate.documents == ()
    assert resolved.candidate.source_url.endswith("api_code=%2A%2A%2A")
    assert len(resolved.verification_note) <= 300


def test_oversized_minimized_payload_is_rejected_with_fixed_capacity_error(tmp_path) -> None:
    repository = AggregatorDiscoveryRepository(
        tmp_path / "registry.sqlite3",
        max_payload_bytes=512,
    )

    with pytest.raises(RuntimeError, match="безопасный лимит"):
        repository.enqueue(_aggregator(external_id="x" * 2000))
