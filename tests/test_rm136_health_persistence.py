"""RM-136 schema-v2 evidence persistence and invalidation."""

from datetime import datetime, timedelta, timezone
import json

from app.tenders.collector.manual_provider_health import (
    HealthCheckBinding,
    ManualHealthEvidence,
    ManualHealthOutcome,
    ManualHealthState,
)
from app.tenders.collector.provider_control import (
    ProviderCheckLoadStatus,
    ProviderCheckRepository,
)


NOW = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
MANUAL_ID = f"manual_{'3' * 32}"


def _evidence() -> ManualHealthEvidence:
    return ManualHealthEvidence(
        check_id="check-current",
        binding=HealthCheckBinding(MANUAL_ID, "a" * 64, 1, 1, "b" * 64, "none"),
        outcome=ManualHealthOutcome.PASSED,
        health=ManualHealthState.HEALTHY,
        checked_at=NOW,
        valid_until=NOW + timedelta(minutes=15),
    )


def test_repository_persists_latest_v2_evidence_and_invalidates_it(tmp_path) -> None:
    path = tmp_path / "collector_provider_health.json"
    repository = ProviderCheckRepository(path)
    evidence = _evidence()
    repository.save_manual_evidence(evidence)

    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 2
    assert repository.manual_evidence(MANUAL_ID) == evidence
    repository.invalidate_manual_evidence(MANUAL_ID)
    assert repository.manual_evidence(MANUAL_ID) is None


def test_cancelled_or_stale_completion_does_not_replace_current_evidence(tmp_path) -> None:
    repository = ProviderCheckRepository(tmp_path / "collector_provider_health.json")
    evidence = _evidence()
    repository.save_manual_evidence(evidence)
    assert repository.save_manual_evidence(evidence, expected_check_id="older-check") is False
    assert repository.manual_evidence(MANUAL_ID) == evidence


def test_missing_corrupt_and_future_health_schema_fail_closed(tmp_path) -> None:
    path = tmp_path / "collector_provider_health.json"
    repository = ProviderCheckRepository(path)
    assert repository.load_result().status is ProviderCheckLoadStatus.MISSING

    path.write_text("{broken", encoding="utf-8")
    assert repository.load_result().status is ProviderCheckLoadStatus.CORRUPT

    path.write_text('{"schema_version": 99, "providers": {}}', encoding="utf-8")
    loaded = repository.load_result()
    assert loaded.status is ProviderCheckLoadStatus.UNSUPPORTED_FUTURE
    assert loaded.manual_evidence == {}
