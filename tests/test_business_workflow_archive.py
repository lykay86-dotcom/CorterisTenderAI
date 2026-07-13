"""Tests for workflow archive and restore behavior."""

from __future__ import annotations

from decimal import Decimal

from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)


def _record(repository: BusinessMetricsRepository):
    return repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-78",
        title="КП на видеонаблюдение",
        status=BusinessStatus.READY,
        total=1_000_000,
        profit=Decimal("200000"),
    )


def test_archive_hides_record_from_active_list(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    record = _record(repository)

    archived = repository.archive_record(record.id)

    assert archived.is_archived
    assert repository.list_records() == []
    assert repository.list_records(archived_only=True) == [archived]
    assert repository.list_records(include_archived=True) == [archived]


def test_archive_excludes_record_from_summary(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    record = _record(repository)

    before = repository.summary()
    repository.archive_record(record.id)
    after = repository.summary()

    assert before.proposals_in_work == 1
    assert before.potential_profit == Decimal("200000")
    assert after.proposals_in_work == 0
    assert after.potential_profit == Decimal("0")


def test_restore_returns_record_to_active_workflow(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    record = _record(repository)
    repository.archive_record(record.id)

    restored = repository.restore_record(record.id)

    assert not restored.is_archived
    assert repository.list_records() == [restored]
    assert repository.list_records(archived_only=True) == []


def test_archived_record_cannot_be_edited(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    record = _record(repository)
    repository.archive_record(record.id)

    try:
        repository.update_record(
            record.id,
            title="Изменение",
        )
    except ValueError as exc:
        assert "восстановить" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
