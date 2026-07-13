"""Tests for editing existing business workflow records."""

from __future__ import annotations

from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)


def test_update_record_changes_only_mutable_fields(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    original = repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-77",
        title="Старое КП",
        status=BusinessStatus.READY,
        total=500000,
        profit=100000,
        margin_percent=20,
        file_path="old.docx",
        due_date="2026-07-15",
    )

    updated = repository.update_record(
        original.id,
        title="Новое КП",
        total=650000,
        profit=145000,
        margin_percent=22.31,
        file_path="new.docx",
        due_date="2026-07-20",
    )

    assert updated.id == original.id
    assert updated.kind == original.kind
    assert updated.tender_id == original.tender_id
    assert updated.status == original.status
    assert updated.created_at == original.created_at
    assert updated.title == "Новое КП"
    assert updated.total == 650000
    assert updated.profit == 145000
    assert updated.file_path == "new.docx"


def test_update_record_can_clear_file_and_due_date(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    record = repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-1",
        title="КП",
        status=BusinessStatus.DRAFT,
        file_path="proposal.docx",
        due_date="2026-07-20",
    )

    updated = repository.update_record(
        record.id,
        file_path="",
        due_date="",
    )

    assert updated.file_path == ""
    assert updated.due_date == ""


def test_update_record_rejects_missing_record(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")

    try:
        repository.update_record(
            "missing",
            title="Не существует",
        )
    except KeyError as exc:
        assert exc.args == ("missing",)
    else:
        raise AssertionError("Expected KeyError")
