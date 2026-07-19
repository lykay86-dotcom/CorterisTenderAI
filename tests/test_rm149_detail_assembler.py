from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.tenders.collector.freshness import (
    DeadlineTimezoneStatus,
    TenderFreshnessState,
    TenderFreshnessStatus,
)
from app.tenders.collector.participation_score import (
    CorterisParticipationScore,
    ParticipationRecommendation,
)
from app.tenders.collector.verification import (
    TenderVerificationState,
    TenderVerificationStatus,
)
from app.tenders.detail import (
    TenderDetailAssembler,
    TenderDetailState,
    TenderIdentity,
    TenderIdentityKind,
    TenderSeverity,
    project_tender_card,
)
from app.tenders.tender_registry import TenderRegistryOccurrence, TenderRegistryRecord


NOW = datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc)


def _record(**changes: Any) -> TenderRegistryRecord:
    values: dict[str, Any] = {
        "registry_key": "registry-key",
        "procurement_number": "0373100000126000001",
        "identity_key": "source:external-1",
        "source": "eis",
        "external_id": "external-1",
        "title": "Supply <script>alert(1)</script>",
        "customer_name": "Customer & Co",
        "customer_inn": "7700000000",
        "region": "Moscow",
        "price_amount": Decimal("1234567.80"),
        "currency": "RUB",
        "status": "published",
        "application_deadline": "2026-07-25T12:00:00+03:00",
        "source_url": "https://zakupki.gov.ru/tender/1",
        "first_seen_at": "2026-07-18T10:00:00+00:00",
        "last_seen_at": "2026-07-19T08:00:00+00:00",
        "seen_count": 2,
        "relevance_score": 92,
        "relevance_grade": "high",
        "last_accepted": True,
        "archived": False,
    }
    values.update(changes)
    return TenderRegistryRecord(**values)


def _occurrence(run_id: str = "run-1") -> TenderRegistryOccurrence:
    return TenderRegistryOccurrence(
        run_id=run_id,
        profile_id="profile-1",
        profile_name="Security",
        executed_at="2026-07-19T08:00:00+00:00",
        accepted=True,
        relevance_score=92,
        relevance_grade="high",
        directions=("video", "access"),
        reasons=("matched",),
        rejection_reasons=(),
        timezone_status="aware",
    )


class RegistryFake:
    def __init__(self, record: TenderRegistryRecord | None) -> None:
        self.record = record
        self.calls: list[tuple[object, ...]] = []

    def get_record(self, registry_key: str) -> TenderRegistryRecord | None:
        self.calls.append(("get_record", registry_key))
        return self.record if self.record and self.record.registry_key == registry_key else None

    def list_tender_occurrences(
        self, registry_key: str, *, limit: int = 100
    ) -> tuple[TenderRegistryOccurrence, ...]:
        self.calls.append(("list_tender_occurrences", registry_key, limit))
        return (_occurrence(),)


class StateFake:
    def __init__(
        self,
        *,
        score: CorterisParticipationScore | None = None,
        decision: dict[str, object] | None = None,
        verification: TenderVerificationState | None = None,
        freshness: TenderFreshnessState | None = None,
    ) -> None:
        self.score = score
        self.decision = decision
        self.verification = verification
        self.freshness = freshness
        self.calls: list[tuple[object, ...]] = []

    def get_latest_score(self, key: str) -> CorterisParticipationScore | None:
        self.calls.append(("get_latest_score", key))
        return self.score

    def get_latest_participation_decision_payload(self, key: str) -> dict[str, object] | None:
        self.calls.append(("get_latest_participation_decision_payload", key))
        return self.decision

    def get_verification_state(self, key: str) -> TenderVerificationState | None:
        self.calls.append(("get_verification_state", key))
        return self.verification

    def get_freshness_state(
        self, key: str, *, now: str | None = None
    ) -> TenderFreshnessState | None:
        self.calls.append(("get_freshness_state", key, now))
        return self.freshness


def _score(*, hard_excluded: bool = False) -> CorterisParticipationScore:
    return CorterisParticipationScore(
        total_score=81,
        recommendation=ParticipationRecommendation.RECOMMENDED,
        recommendation_text="Recommended",
        components=(),
        positive_factors=("fit",),
        negative_factors=(),
        matched_keywords=(),
        matched_okpd2=(),
        stop_factors=("license_missing",) if hard_excluded else (),
        missing_documents=(),
        directions=("video",),
        hard_excluded=hard_excluded,
        scored_at="2026-07-19T08:30:00+00:00",
        profile_version="profile-v1",
        input_fingerprint="score-input-fingerprint",
    )


def _verification(*, unresolved: int = 0) -> TenderVerificationState:
    return TenderVerificationState(
        registry_key="registry-key",
        verification_run_id="verify-1",
        status=(
            TenderVerificationStatus.CONFLICT
            if unresolved
            else TenderVerificationStatus.VERIFIED_EIS
        ),
        last_verified_at="2026-07-19T08:15:00+00:00",
        critical_field_count=3,
        verified_field_count=3,
        official_field_count=3,
        missing_fields=(),
        conflict_count=unresolved,
        unresolved_conflict_count=unresolved,
        minimum_confidence=0.95,
    )


def _freshness(*, stale: bool = False) -> TenderFreshnessState:
    return TenderFreshnessState(
        canonical_key="registry-key",
        status=TenderFreshnessStatus.STALE if stale else TenderFreshnessStatus.FRESH,
        last_verified_at="2026-07-19T08:15:00+00:00",
        verification_due_at="2026-07-20T08:15:00+00:00",
        is_stale=stale,
        stale_reason="verification_due" if stale else "",
        deadline_original="2026-07-25T12:00:00+03:00",
        source_timezone="Europe/Moscow",
        timezone_status=DeadlineTimezoneStatus.EXPLICIT,
        deadline_utc="2026-07-25T09:00:00+00:00",
        user_timezone="Europe/Moscow",
        deadline_user_local="2026-07-25T12:00:00+03:00",
        seconds_remaining=500_000,
        recheck_interval_minutes=1440,
        deadline_expired=False,
        updated_at="2026-07-19T08:15:00+00:00",
    )


def test_assembler_reads_only_existing_local_owners_and_exact_registry_key() -> None:
    registry = RegistryFake(_record())
    state = StateFake(score=_score(), verification=_verification(), freshness=_freshness())
    assembler = TenderDetailAssembler(registry, state, clock=lambda: NOW)

    snapshot = assembler.assemble(TenderIdentity(TenderIdentityKind.REGISTRY, "registry-key"))

    assert snapshot.state is TenderDetailState.READY
    assert registry.calls == [
        ("get_record", "registry-key"),
        ("list_tender_occurrences", "registry-key", 100),
    ]
    assert [call[0] for call in state.calls] == [
        "get_verification_state",
        "get_freshness_state",
        "get_latest_score",
        "get_latest_participation_decision_payload",
    ]
    assert not hasattr(assembler, "score")
    assert not hasattr(assembler, "evaluate")
    assert snapshot.fact("price").accessible_value == "1234567.80 RUB"


def test_unknown_and_legacy_identity_fail_closed_without_guessing() -> None:
    registry = RegistryFake(None)
    state = StateFake()
    assembler = TenderDetailAssembler(registry, state, clock=lambda: NOW)

    missing = assembler.assemble(TenderIdentity(TenderIdentityKind.REGISTRY, "missing"))
    legacy = assembler.assemble(TenderIdentity(TenderIdentityKind.LEGACY_ORM, "missing"))

    assert missing.state is TenderDetailState.NOT_FOUND
    assert missing.reason_code == "tender_not_found"
    assert legacy.state is TenderDetailState.ERROR
    assert legacy.reason_code == "identity_kind_unsupported"
    assert registry.calls == [("get_record", "missing")]
    assert state.calls == []


def test_repository_read_error_returns_typed_safe_snapshot() -> None:
    class FailingRegistry(RegistryFake):
        def get_record(self, registry_key: str) -> TenderRegistryRecord | None:
            raise OSError(f"do not expose local path for {registry_key}")

    snapshot = TenderDetailAssembler(
        FailingRegistry(None),
        StateFake(),
        clock=lambda: NOW,
    ).assemble(TenderIdentity(TenderIdentityKind.REGISTRY, "registry-key"))

    assert snapshot.state is TenderDetailState.ERROR
    assert snapshot.reason_code == "detail_read_failed"
    assert "local path" not in snapshot.accessible_summary


def test_persisted_critical_stop_factor_dominates_recommendation_and_actions() -> None:
    decision = {
        "decision_id": "decision-1",
        "registry_key": "registry-key",
        "recommendation": "participate",
        "score": 81,
        "confidence": 0.9,
        "summary": "Participate",
        "evidence": [{"code": "fit", "title": "Fit", "detail": "Good"}],
        "stop_factors": ["license_missing"],
        "missing": [],
        "actions": ["open_commercial_estimate"],
        "decided_at": "2026-07-19T08:35:00+00:00",
        "policy_version": "rm107-v1",
    }
    snapshot = TenderDetailAssembler(
        RegistryFake(_record()),
        StateFake(
            score=_score(hard_excluded=True),
            decision=decision,
            verification=_verification(),
            freshness=_freshness(),
        ),
        clock=lambda: NOW,
    ).assemble(TenderIdentity(TenderIdentityKind.REGISTRY, "registry-key"))

    assert snapshot.critical_warnings
    assert snapshot.critical_warnings[0].severity is TenderSeverity.CRITICAL
    assert snapshot.critical_warnings[0].blocking
    assert snapshot.primary_action.action_id == "view_participation_decision"
    assert snapshot.decision is not None
    assert snapshot.decision.recommendation == "participate"


def test_missing_decision_is_unknown_not_negative_recommendation() -> None:
    snapshot = TenderDetailAssembler(
        RegistryFake(_record()),
        StateFake(verification=_verification(), freshness=_freshness()),
        clock=lambda: NOW,
    ).assemble(TenderIdentity(TenderIdentityKind.REGISTRY, "registry-key"))

    assert snapshot.decision is None
    assert snapshot.status("decision").value == "not_loaded"
    assert "not_recommended" not in snapshot.accessible_summary


def test_snapshot_and_card_are_deterministic_and_card_never_reads_repositories() -> None:
    registry = RegistryFake(_record())
    state = StateFake(score=_score(), verification=_verification(), freshness=_freshness())
    assembler = TenderDetailAssembler(registry, state, clock=lambda: NOW)
    identity = TenderIdentity(TenderIdentityKind.REGISTRY, "registry-key")

    first = assembler.assemble(identity)
    second = assembler.assemble(identity)
    calls_before_projection = (len(registry.calls), len(state.calls))
    card = project_tender_card(replace(second, actions=tuple(reversed(second.actions))))

    assert first.fingerprint == second.fingerprint
    assert card.snapshot_fingerprint == second.fingerprint
    assert card.identity == second.identity
    assert card.primary_action.action_id == second.primary_action.action_id
    assert (len(registry.calls), len(state.calls)) == calls_before_projection
    assert "<script>" in card.title
    assert "Supply" in card.accessible_summary


def test_action_catalog_is_complete_and_conflict_dominates_primary_focus() -> None:
    snapshot = TenderDetailAssembler(
        RegistryFake(_record()),
        StateFake(
            score=_score(hard_excluded=True),
            verification=_verification(unresolved=1),
            freshness=_freshness(),
        ),
        clock=lambda: NOW,
    ).assemble(TenderIdentity(TenderIdentityKind.REGISTRY, "registry-key"))

    assert {item.action_id for item in snapshot.actions} == {
        "open_detail",
        "open_official_source",
        "download_documents",
        "view_documents",
        "run_requirements_analysis",
        "view_requirements_analysis",
        "run_full_analysis",
        "view_full_analysis",
        "view_participation_decision",
        "recalculate_participation_decision",
        "view_verification",
        "resolve_verification",
        "open_commercial_estimate",
        "archive_tender",
        "return_to_origin",
    }
    assert snapshot.primary_action.action_id == "view_verification"
    assert snapshot.primary_action.state.value == "available"


def test_domain_text_is_bounded_and_control_or_bidi_characters_are_neutralized() -> None:
    snapshot = TenderDetailAssembler(
        RegistryFake(
            _record(
                title="Unsafe\x00title\u202e.exe" + "x" * 5000,
                customer_name="Customer\nName",
            )
        ),
        StateFake(verification=_verification(), freshness=_freshness()),
        clock=lambda: NOW,
    ).assemble(TenderIdentity(TenderIdentityKind.REGISTRY, "registry-key"))

    assert "\x00" not in snapshot.title
    assert "\u202e" not in snapshot.title
    assert len(snapshot.title) == 4096
    assert "\n" not in snapshot.fact("customer").value
