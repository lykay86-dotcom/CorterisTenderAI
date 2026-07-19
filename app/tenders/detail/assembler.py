"""Read-only assembly of deterministic RM-149 tender detail snapshots."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from typing import Protocol

from app.financial import CurrencyCode, FinancialValueState, MoneyAmount, format_money
from app.tenders.collector.freshness import TenderFreshnessState
from app.tenders.collector.participation_score import CorterisParticipationScore
from app.tenders.collector.verification import TenderVerificationState
from app.tenders.detail.action_catalog import validate_https_url
from app.tenders.detail.contracts import (
    DETAIL_CONTRACT_VERSION,
    PRIMARY_ACTION_POLICY_VERSION,
    TenderActionRole,
    TenderActionSpec,
    TenderActionState,
    TenderCriticalWarning,
    TenderDecisionSummary,
    TenderDetailSnapshot,
    TenderDetailState,
    TenderFact,
    TenderHistoryItem,
    TenderIdentity,
    TenderIdentityKind,
    TenderSeverity,
    TenderStatusItem,
    TenderValueState,
)
from app.tenders.tender_registry import TenderRegistryOccurrence, TenderRegistryRecord


class TenderRegistryReader(Protocol):
    def get_record(self, registry_key: str) -> TenderRegistryRecord | None: ...

    def list_tender_occurrences(
        self, registry_key: str, *, limit: int = 100
    ) -> tuple[TenderRegistryOccurrence, ...]: ...


class TenderStateReader(Protocol):
    def get_verification_state(self, registry_key: str) -> TenderVerificationState | None: ...

    def get_freshness_state(
        self, registry_key: str, *, now: str | None = None
    ) -> TenderFreshnessState | None: ...

    def get_latest_score(self, registry_key: str) -> CorterisParticipationScore | None: ...

    def get_latest_participation_decision_payload(
        self, registry_key: str
    ) -> Mapping[str, object] | None: ...


_STATUS_ORDER = {
    name: index
    for index, name in enumerate(
        (
            "lifecycle",
            "deadline",
            "archive",
            "verification",
            "freshness",
            "conflicts",
            "documents",
            "requirements",
            "full_analysis",
            "decision",
        )
    )
}
_ACTION_LABELS = {
    "open_detail": "Open tender details",
    "open_official_source": "Open official source",
    "download_documents": "Download documents",
    "view_documents": "View documents",
    "run_requirements_analysis": "Analyze requirements",
    "view_requirements_analysis": "View requirements analysis",
    "run_full_analysis": "Run full analysis",
    "view_full_analysis": "View full analysis",
    "view_participation_decision": "View participation decision",
    "recalculate_participation_decision": "Recalculate participation decision",
    "view_verification": "View verification",
    "resolve_verification": "Resolve verification conflict",
    "open_commercial_estimate": "Open commercial estimate",
    "archive_tender": "Archive tender",
    "restore_tender": "Restore tender",
    "return_to_origin": "Return to origin",
}


class TenderDetailAssembler:
    """Combine existing local owners without scoring, AI, network or mutation."""

    def __init__(
        self,
        registry: TenderRegistryReader,
        state: TenderStateReader,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._registry = registry
        self._state = state
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def assemble(self, identity: TenderIdentity) -> TenderDetailSnapshot:
        generated_at = self._clock()
        if generated_at.tzinfo is None or generated_at.utcoffset() is None:
            raise ValueError("detail clock must return a timezone-aware datetime")
        if identity.kind is not TenderIdentityKind.REGISTRY:
            return _terminal(
                identity, generated_at, TenderDetailState.ERROR, "unsupported_identity_kind"
            )

        record = self._registry.get_record(identity.value)
        if record is None:
            return _terminal(
                identity, generated_at, TenderDetailState.NOT_FOUND, "record_not_found"
            )

        verification = self._state.get_verification_state(identity.value)
        freshness = self._state.get_freshness_state(
            identity.value,
            now=generated_at.astimezone(timezone.utc).isoformat(),
        )
        score = self._state.get_latest_score(identity.value)
        payload = self._state.get_latest_participation_decision_payload(identity.value)
        occurrences = self._registry.list_tender_occurrences(identity.value, limit=100)

        decision = _decision(identity.value, payload, score)
        warnings = _warnings(score, payload, verification)
        facts = _facts(record)
        statuses = _statuses(record, verification, freshness, score, payload)
        history = _history(occurrences)
        revision = _revision(record)
        actions = _actions(identity, record, revision, score, payload, verification)
        state = _state(freshness, verification)
        fingerprint = _fingerprint(
            identity, revision, state, facts, statuses, warnings, decision, actions, history
        )
        actions = tuple(replace(item, snapshot_fingerprint=fingerprint) for item in actions)
        return TenderDetailSnapshot(
            identity=identity,
            generated_at=generated_at,
            source_revision=revision,
            state=state,
            title=_display(record.title, "Untitled tender"),
            source=_display(record.source, "unknown", limit=128),
            source_url=validate_https_url(record.source_url) or "",
            facts=facts,
            statuses=statuses,
            critical_warnings=warnings,
            decision=decision,
            actions=actions,
            history=history,
            fingerprint=fingerprint,
            accessible_summary=_summary(record, facts, statuses, warnings, decision),
        )


def _terminal(
    identity: TenderIdentity,
    generated_at: datetime,
    state: TenderDetailState,
    reason: str,
) -> TenderDetailSnapshot:
    semantic = {
        "contract": DETAIL_CONTRACT_VERSION,
        "identity": identity.public_id,
        "state": state,
        "reason": reason,
    }
    fingerprint = _hash(semantic)
    action = TenderActionSpec(
        "open_detail",
        _ACTION_LABELS["open_detail"],
        TenderActionState.UNSUPPORTED,
        reason,
        identity,
        "registry.detail",
        TenderActionRole.PRIMARY,
        False,
        fingerprint,
        "",
        f"detail:{identity.public_id}",
        "Tender detail is unavailable",
    )
    return TenderDetailSnapshot(
        identity,
        generated_at,
        "",
        state,
        "Tender not available",
        "unknown",
        "",
        (),
        (),
        (),
        None,
        (action,),
        (),
        fingerprint,
        f"Tender not available. {reason}",
        reason,
        ("identity", "decision", "facts"),
    )


def _facts(record: TenderRegistryRecord) -> tuple[TenderFact, ...]:
    currency = (
        CurrencyCode.RUB if record.currency.strip().upper() == "RUB" else CurrencyCode.UNKNOWN
    )
    money_state = (
        FinancialValueState.AVAILABLE
        if currency is CurrencyCode.RUB
        else FinancialValueState.UNSUPPORTED_CURRENCY
    )
    money = MoneyAmount(record.price_amount, currency, money_state)
    price_state = (
        TenderValueState.MISSING
        if record.price_amount is None
        else (
            TenderValueState.AVAILABLE
            if currency is CurrencyCode.RUB
            else TenderValueState.UNSUPPORTED
        )
    )
    values = (
        TenderFact(
            "customer",
            "Customer",
            _display(record.customer_name),
            _display(record.customer_name),
        ),
        TenderFact(
            "customer_inn",
            "Customer INN",
            _display(record.customer_inn),
            _display(record.customer_inn),
        ),
        TenderFact(
            "external_id",
            "External ID",
            _display(record.external_id),
            _display(record.external_id),
        ),
        TenderFact(
            "price", "Price", format_money(money), format_money(money, accessible=True), price_state
        ),
        TenderFact(
            "procurement_number",
            "Procurement number",
            _display(record.procurement_number),
            _display(record.procurement_number),
        ),
        TenderFact("region", "Region", _display(record.region), _display(record.region)),
        TenderFact("registry_key", "Registry key", record.registry_key, record.registry_key),
        TenderFact(
            "source",
            "Source",
            _display(record.source, "unknown", limit=128),
            _display(record.source, "unknown", limit=128),
        ),
    )
    return tuple(sorted(values, key=lambda item: item.stable_id))


def _status(
    stable_id: str,
    value: str,
    severity: TenderSeverity,
    explanation: str,
    timestamp: str = "",
) -> TenderStatusItem:
    return TenderStatusItem(
        stable_id, stable_id.replace("_", " ").title(), value, severity, explanation, timestamp
    )


def _statuses(
    record: TenderRegistryRecord,
    verification: TenderVerificationState | None,
    freshness: TenderFreshnessState | None,
    score: CorterisParticipationScore | None,
    payload: Mapping[str, object] | None,
) -> tuple[TenderStatusItem, ...]:
    conflicts = verification.unresolved_conflict_count if verification else 0
    items = (
        _status(
            "lifecycle",
            _display(record.status, "not_loaded", limit=128),
            TenderSeverity.INFO,
            "Persisted registry lifecycle",
            record.last_seen_at,
        ),
        _status(
            "deadline",
            _display(
                freshness.deadline_user_local if freshness else record.application_deadline,
                "not_loaded",
                limit=256,
            ),
            TenderSeverity.INFO,
            "Persisted source deadline",
            freshness.updated_at if freshness else record.last_seen_at,
        ),
        _status(
            "archive",
            "archived" if record.archived else "active",
            TenderSeverity.WARNING if record.archived else TenderSeverity.INFO,
            "Registry archive state",
            record.last_seen_at,
        ),
        _status(
            "verification",
            verification.status.value if verification else "not_loaded",
            TenderSeverity.WARNING if conflicts or not verification else TenderSeverity.SUCCESS,
            "Latest persisted verification state",
            verification.last_verified_at if verification else "",
        ),
        _status(
            "freshness",
            freshness.status.value if freshness else "not_loaded",
            TenderSeverity.WARNING if freshness and freshness.is_stale else TenderSeverity.INFO,
            freshness.stale_reason if freshness else "Freshness was not loaded",
            freshness.updated_at if freshness else "",
        ),
        _status(
            "conflicts",
            str(conflicts),
            TenderSeverity.CRITICAL if conflicts else TenderSeverity.INFO,
            "Unresolved persisted verification conflicts",
            verification.last_verified_at if verification else "",
        ),
        _status(
            "documents",
            "not_loaded",
            TenderSeverity.INFO,
            "Inspect in the existing documents surface",
        ),
        _status(
            "requirements",
            "not_loaded",
            TenderSeverity.INFO,
            "Inspect in the existing requirements surface",
        ),
        _status(
            "full_analysis",
            "not_loaded",
            TenderSeverity.INFO,
            "Inspect in the existing analysis surface",
        ),
        _status(
            "decision",
            "available" if payload is not None or score is not None else "not_loaded",
            TenderSeverity.INFO,
            "Latest persisted decision or score only",
            _text(payload.get("decided_at")) if payload else (score.scored_at if score else ""),
        ),
    )
    return tuple(sorted(items, key=lambda item: _STATUS_ORDER[item.stable_id]))


def _decision(
    registry_key: str,
    payload: Mapping[str, object] | None,
    score: CorterisParticipationScore | None,
) -> TenderDecisionSummary | None:
    if payload is not None and _text(payload.get("registry_key")) == registry_key:
        return TenderDecisionSummary(
            _text(payload.get("recommendation")) or "data_insufficient",
            _text(payload.get("summary")) or "Persisted decision",
            _int(payload.get("score"), 0, 100),
            _float(payload.get("confidence"), 0.0, 1.0),
            _text(payload.get("summary")) or "Persisted decision",
            _text(payload.get("decision_id")),
            _text(payload.get("decided_at")),
            _text(payload.get("policy_version")),
            tuple(sorted(_evidence(payload.get("evidence")))),
            tuple(sorted(_strings(payload.get("missing")))),
            tuple(sorted(_strings(payload.get("actions")))),
            score.input_fingerprint if score else "",
        )
    if score is None:
        return None
    return TenderDecisionSummary(
        score.recommendation.value,
        score.recommendation_text,
        score.total_score,
        None,
        score.recommendation_text,
        "",
        score.scored_at,
        score.profile_version,
        tuple(sorted((*score.positive_factors, *score.negative_factors))),
        tuple(sorted(score.missing_documents)),
        (),
        score.input_fingerprint,
    )


def _warnings(
    score: CorterisParticipationScore | None,
    payload: Mapping[str, object] | None,
    verification: TenderVerificationState | None,
) -> tuple[TenderCriticalWarning, ...]:
    stop_factors = set(score.stop_factors if score else ())
    if payload:
        stop_factors.update(_strings(payload.get("stop_factors")))
    result: list[TenderCriticalWarning] = []
    if stop_factors or (score and score.hard_excluded):
        result.append(
            TenderCriticalWarning(
                "critical_stop_factor",
                "Blocking participation factor",
                ", ".join(sorted(stop_factors)) or "Persisted hard exclusion",
            )
        )
    if verification and verification.unresolved_conflict_count:
        result.append(
            TenderCriticalWarning(
                "verification_conflict",
                "Unresolved verification conflict",
                f"{verification.unresolved_conflict_count} unresolved conflict(s)",
            )
        )
    return tuple(sorted(result, key=lambda item: item.stable_id))


def _actions(
    identity: TenderIdentity,
    record: TenderRegistryRecord,
    revision: str,
    score: CorterisParticipationScore | None,
    payload: Mapping[str, object] | None,
    verification: TenderVerificationState | None,
) -> tuple[TenderActionSpec, ...]:
    stop_factors = set(score.stop_factors if score else ())
    if payload:
        stop_factors.update(_strings(payload.get("stop_factors")))
    if (stop_factors or (score and score.hard_excluded)) and (
        verification and verification.unresolved_conflict_count
    ):
        primary = "view_verification"
    elif stop_factors or (score and score.hard_excluded):
        primary = (
            "view_participation_decision" if payload is not None or score else "view_verification"
        )
    elif verification and verification.unresolved_conflict_count:
        primary = "view_verification"
    elif score and score.missing_documents:
        primary = "download_documents"
    elif payload is not None:
        mapped = [
            item
            for item in _strings(payload.get("actions"))
            if item in _ACTION_LABELS and item not in {"archive_tender", "restore_tender"}
        ]
        primary = mapped[0] if mapped else "view_participation_decision"
    else:
        primary = "open_detail"

    ids = (
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
        "restore_tender" if record.archived else "archive_tender",
        "return_to_origin",
    )
    result = []
    for action_id in ids:
        available = not (
            (action_id == "open_official_source" and validate_https_url(record.source_url) is None)
            or (action_id == "view_participation_decision" and payload is None and score is None)
            or action_id
            in {
                "view_documents",
                "view_requirements_analysis",
                "view_full_analysis",
                "return_to_origin",
            }
            or (
                action_id == "resolve_verification"
                and not (verification and verification.unresolved_conflict_count)
            )
        )
        result.append(
            TenderActionSpec(
                action_id,
                _ACTION_LABELS[action_id],
                TenderActionState.AVAILABLE if available else TenderActionState.CONTEXT_REQUIRED,
                "" if available else "required_context_not_loaded",
                identity,
                action_id.replace("_", "."),
                TenderActionRole.PRIMARY if action_id == primary else TenderActionRole.SECONDARY,
                action_id in {"archive_tender", "restore_tender", "resolve_verification"},
                "",
                revision,
                f"detail:{identity.public_id}",
                f"{_ACTION_LABELS[action_id]} for "
                f"{_display(record.procurement_number or record.title)}",
            )
        )
    return tuple(
        sorted(result, key=lambda item: (item.role is TenderActionRole.SECONDARY, item.action_id))
    )


def _history(items: Sequence[TenderRegistryOccurrence]) -> tuple[TenderHistoryItem, ...]:
    result = (
        TenderHistoryItem(
            f"{item.run_id}:{item.profile_id}",
            item.executed_at,
            _display(item.profile_name),
            f"score={item.relevance_score}; grade={item.relevance_grade}",
            item.accepted,
        )
        for item in items[:100]
    )
    return tuple(sorted(result, key=lambda item: (item.occurred_at, item.stable_id), reverse=True))


def _state(
    freshness: TenderFreshnessState | None,
    verification: TenderVerificationState | None,
) -> TenderDetailState:
    if verification and verification.unresolved_conflict_count:
        return TenderDetailState.CONFLICTED
    if freshness and freshness.is_stale:
        return TenderDetailState.STALE
    if verification is None or freshness is None:
        return TenderDetailState.PARTIAL
    return TenderDetailState.READY


def _revision(record: TenderRegistryRecord) -> str:
    return _hash((record.registry_key, record.last_seen_at, record.seen_count, record.archived))


def _fingerprint(
    identity: TenderIdentity,
    revision: str,
    state: TenderDetailState,
    facts: Sequence[TenderFact],
    statuses: Sequence[TenderStatusItem],
    warnings: Sequence[TenderCriticalWarning],
    decision: TenderDecisionSummary | None,
    actions: Sequence[TenderActionSpec],
    history: Sequence[TenderHistoryItem],
) -> str:
    return _hash(
        {
            "contract": DETAIL_CONTRACT_VERSION,
            "policy": PRIMARY_ACTION_POLICY_VERSION,
            "identity": identity.public_id,
            "revision": revision,
            "state": state,
            "facts": [asdict(item) for item in facts],
            "statuses": [asdict(item) for item in statuses],
            "warnings": [asdict(item) for item in warnings],
            "decision": asdict(decision) if decision else None,
            "actions": [
                (item.action_id, item.state, item.reason, item.role, item.destructive)
                for item in actions
            ],
            "history": [asdict(item) for item in history],
        }
    )


def _summary(
    record: TenderRegistryRecord,
    facts: Sequence[TenderFact],
    statuses: Sequence[TenderStatusItem],
    warnings: Sequence[TenderCriticalWarning],
    decision: TenderDecisionSummary | None,
) -> str:
    price = next(item.accessible_value for item in facts if item.stable_id == "price")
    deadline = next(item.value for item in statuses if item.stable_id == "deadline")
    parts = [
        _display(record.title, "Untitled tender"),
        _display(record.procurement_number, ""),
        price,
        deadline,
    ]
    if warnings:
        parts.append("Critical: " + "; ".join(item.title for item in warnings))
    parts.append("Decision: " + (decision.recommendation if decision else "not loaded"))
    return ". ".join(item for item in parts if item)


def _text(value: object) -> str:
    return _display(value, "")


def _display(value: object, fallback: str = "Not specified", *, limit: int = 4096) -> str:
    if not isinstance(value, str):
        return fallback
    bidi = {
        "\u061c",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
    safe = "".join(
        " " if ord(character) < 32 or ord(character) == 127 or character in bidi else character
        for character in value
    ).strip()
    return (safe or fallback)[:limit]


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(safe for item in value if isinstance(item, str) and (safe := _display(item, "")))


def _evidence(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    result = []
    for item in value:
        if isinstance(item, Mapping):
            code, detail = _text(item.get("code")), _text(item.get("detail"))
            if code or detail:
                result.append(f"{code}: {detail}".strip(": "))
    return tuple(result)


def _int(value: object, lower: int, upper: int) -> int | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (str, int, float)):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if lower <= result <= upper else None


def _float(value: object, lower: float, upper: float) -> float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (str, int, float)):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if lower <= result <= upper else None


def _hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["TenderDetailAssembler", "TenderRegistryReader", "TenderStateReader"]
