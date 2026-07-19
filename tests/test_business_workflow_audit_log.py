"""Tests for persistent workflow audit history."""

from __future__ import annotations

import json

import pytest

from app.financial import FinancialMigrationError

from app.repositories.business_metrics import (
    BusinessAuditAction,
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)


def test_create_record_writes_created_event(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    record = repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-79",
        title="КП",
        status=BusinessStatus.DRAFT,
    )

    history = repository.list_history(record.id)

    assert len(history) == 1
    assert history[0].action == BusinessAuditAction.CREATED.value
    assert history[0].new_value == "КП"


def test_edit_writes_one_event_per_changed_field(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    record = repository.save_record(
        kind=BusinessRecordKind.ESTIMATE,
        tender_id="T-1",
        title="Смета",
        status=BusinessStatus.DRAFT,
        total=100000,
        profit=20000,
    )

    repository.update_record(
        record.id,
        title="Смета обновлена",
        total=120000,
        profit=25000,
    )

    history = repository.list_history(record.id)
    updated = [event for event in history if event.action == BusinessAuditAction.UPDATED.value]

    assert {event.field for event in updated} == {
        "title",
        "total",
        "profit",
        "margin_percent",
    }
    total_event = next(event for event in updated if event.field == "total")
    assert total_event.old_value == "100000.00"
    assert total_event.new_value == "120000.00"


def test_status_archive_and_restore_are_audited(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    record = repository.save_record(
        kind=BusinessRecordKind.PROJECT,
        tender_id="T-2",
        title="Монтаж",
        status=BusinessStatus.PLANNED,
    )

    repository.update_status(record.id, BusinessStatus.ACTIVE)
    repository.archive_record(record.id)
    repository.restore_record(record.id)

    actions = {event.action for event in repository.list_history(record.id)}

    assert BusinessAuditAction.STATUS_CHANGED.value in actions
    assert BusinessAuditAction.ARCHIVED.value in actions
    assert BusinessAuditAction.RESTORED.value in actions


def test_legacy_json_without_events_is_supported(tmp_path) -> None:
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": [
                    {
                        "id": "legacy",
                        "kind": "proposal",
                        "tender_id": "1",
                        "title": "Старое КП",
                        "status": "draft",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    repository = BusinessMetricsRepository(path)

    assert repository.list_history("legacy") == []
    with pytest.raises(FinancialMigrationError):
        repository.update_record("legacy", title="Новое КП")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert "events" not in payload
