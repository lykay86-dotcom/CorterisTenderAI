"""Expected-red security and correlation contracts for RM-151 safe feedback."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
import json

import pytest


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
MALICIOUS = """RM151_FAKE_OPENAI_CREDENTIAL_DO_NOT_USE
Authorization: Bearer FAKE_TOKEN
C:\\Users\\Yuri\\secret\\config.json
/home/alice/.config/corteris/secret.env
https://example.invalid/api?t=FAKE_SECRET&user=alice#fragment
postgresql://alice:password@localhost/private
<script>alert(1)</script><img src=x onerror=alert(2)>
TRACEBACK_MARKER SQL_MARKER ENV_MARKER \u202e
"""
FORBIDDEN = (
    "RM151_FAKE_OPENAI_CREDENTIAL_DO_NOT_USE",
    "FAKE_TOKEN",
    "C:\\Users\\Yuri",
    "/home/alice",
    "FAKE_SECRET",
    "password@",
    "<script",
    "onerror",
    "TRACEBACK_MARKER",
    "SQL_MARKER",
    "ENV_MARKER",
    "\u202e",
)


def _modules():
    return (
        import_module("app.operations.contracts"),
        import_module("app.operations.diagnostics"),
        import_module("app.operations.safe_feedback"),
    )


def test_malicious_exception_is_absent_from_every_user_projection_but_correlated() -> None:
    contracts, diagnostics, safe_feedback = _modules()
    registry = diagnostics.DiagnosticRegistry(
        max_records=4,
        id_factory=lambda: "diagnostic-151-a",
    )
    projector = safe_feedback.SafeFeedbackProjector(
        registry=registry,
        feedback_id_factory=lambda: "feedback-151-a",
    )

    feedback = projector.project_exception(
        RuntimeError(MALICIOUS),
        episode_id=contracts.OperationEpisodeId("episode-151-a"),
        kind=contracts.OperationKind.TENDER_SEARCH,
        occurred_at=NOW,
    )
    projections = (
        feedback.title.value,
        feedback.summary.value,
        feedback.accessible_text.value,
        feedback.to_plain_text(),
        json.dumps(feedback.to_notification_payload(), ensure_ascii=False),
        json.dumps(feedback.to_export_dict(), ensure_ascii=False),
    )

    for projection in projections:
        for marker in FORBIDDEN:
            assert marker not in projection
    assert feedback.title.value == "Операция не завершена"
    assert feedback.summary.value == ("Технические детали безопасно скрыты. Откройте диагностику.")
    assert feedback.accessible_text.value.startswith(
        "Операция не завершена. Технические детали безопасно скрыты. "
        "Откройте диагностику. Код диагностики: diagnostic-151-a."
    )
    assert feedback.reason is contracts.OperationReasonCode.INTERNAL_ERROR
    assert feedback.diagnostic_id is not None
    record = registry.get(feedback.diagnostic_id)
    assert record is not None
    assert record.episode_id == feedback.episode_id
    assert MALICIOUS not in repr(record)


def test_safe_text_normalizes_controls_bidi_and_markup_with_bounds() -> None:
    contracts, _, safe_feedback = _modules()

    text = safe_feedback.sanitize_safe_text(
        "  A\x00B\nC\u202e<script>unsafe</script>  ",
        max_length=32,
    )

    assert isinstance(text, contracts.SafeText)
    assert "\x00" not in text.value
    assert "\u202e" not in text.value
    assert "<" not in text.value
    assert ">" not in text.value
    assert len(text.value) <= 32
    assert safe_feedback.sanitize_safe_text(text.value, max_length=32) == text


def test_diagnostic_registry_is_exact_bounded_and_rejects_conflicting_reuse() -> None:
    contracts, diagnostics, _ = _modules()
    registry = diagnostics.DiagnosticRegistry(max_records=2)

    def record(identifier: str, reason):
        return diagnostics.DiagnosticRecord(
            correlation_id=contracts.DiagnosticCorrelationId(identifier),
            episode_id=contracts.OperationEpisodeId(f"episode-{identifier}"),
            kind=contracts.OperationKind.SYSTEM_HEALTH,
            reason=reason,
            occurred_at=NOW,
            application_version="1.5.1",
            safe_context=(("component", "workflow"),),
            owner_kind=diagnostics.DiagnosticOwnerKind.TRANSIENT,
            evidence_reference=f"opaque-{identifier}",
            parent_correlation_id=None,
        )

    first = record("diagnostic-151-a", contracts.OperationReasonCode.DATA_DAMAGED)
    registry.register(first)
    assert registry.register(first) is first
    with pytest.raises(diagnostics.DiagnosticConflictError):
        registry.register(record("diagnostic-151-a", contracts.OperationReasonCode.INTERNAL_ERROR))

    registry.register(record("diagnostic-151-b", contracts.OperationReasonCode.OFFLINE))
    registry.register(record("diagnostic-151-c", contracts.OperationReasonCode.TIMEOUT))
    assert registry.get(first.correlation_id) is None
    assert registry.get(contracts.DiagnosticCorrelationId("diagnostic-151-c")) is not None
    assert len(registry) == 2


@pytest.mark.parametrize(
    ("reason_name", "expected_severity"),
    (
        ("OFFLINE", "warning"),
        ("AUTH_REQUIRED", "warning"),
        ("DATA_DAMAGED", "error"),
        ("UNSUPPORTED_SCHEMA", "error"),
    ),
)
def test_j10_j13_j15_typed_recovery_feedback_never_reads_raw_detail(
    reason_name,
    expected_severity,
) -> None:
    contracts, diagnostics, safe_feedback = _modules()
    registry = diagnostics.DiagnosticRegistry(max_records=4)
    projector = safe_feedback.SafeFeedbackProjector(registry=registry)

    feedback = projector.project_reason(
        getattr(contracts.OperationReasonCode, reason_name),
        episode_id=contracts.OperationEpisodeId(f"episode-{reason_name.lower()}"),
        kind=contracts.OperationKind.WORKFLOW_RECOVERY,
        occurred_at=NOW,
        unsafe_detail=MALICIOUS,
    )

    assert feedback.severity.value == expected_severity
    assert MALICIOUS not in feedback.to_plain_text()
    assert all(marker not in feedback.to_plain_text() for marker in FORBIDDEN)
