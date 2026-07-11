"""Tests for lock-safe business workflow snapshots."""

from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)


def test_snapshot_is_isolated_and_replace_is_atomic(tmp_path) -> None:
    repository = BusinessMetricsRepository(
        tmp_path / "workflow.json"
    )
    record = repository.save_record(
        kind=BusinessRecordKind.ESTIMATE,
        tender_id="T-83",
        title="Смета",
        status=BusinessStatus.DRAFT,
    )

    snapshot = repository.snapshot_payload()
    snapshot["records"][0]["title"] = "Из копии"

    assert repository.get_record(record.id).title == "Смета"

    repository.replace_payload(snapshot)

    assert repository.get_record(record.id).title == "Из копии"
    temporary = repository.path.with_suffix(
        repository.path.suffix + ".restore.tmp"
    )
    assert not temporary.exists()
