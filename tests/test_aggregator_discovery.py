from __future__ import annotations

from app.tenders.collector.aggregator_discovery import (
    AggregatorDiscoveryRepository,
    AggregatorDiscoveryStatus,
    AggregatorOfficialVerificationService,
    OfficialIdentityDecision,
    match_official_identity,
)
from app.tenders.models import TenderSource
from tests.collector_c3_helpers import make_tender


def _aggregator():
    return make_tender(
        source=TenderSource.CUSTOM,
        external_id="aggregator-1",
        amount="9999999",
        raw_metadata={
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
    assert attempts[0]["note"] == "network unavailable"


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
