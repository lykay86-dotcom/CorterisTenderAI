"""Tests for scheduled workflow backups and retention."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path

from app.core.workflow_auto_backup import (
    WorkflowAutoBackupService,
    WorkflowAutoBackupSettings,
)
from app.core.workflow_backup import WorkflowBackupService
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)


NOW = datetime(2026, 7, 11, 20, 0, 0)


def _repository(tmp_path: Path) -> BusinessMetricsRepository:
    repository = BusinessMetricsRepository(
        tmp_path / "business_workflow.json"
    )
    repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-84",
        title="КП",
        status=BusinessStatus.READY,
    )
    return repository


def _service(tmp_path: Path) -> WorkflowAutoBackupService:
    return WorkflowAutoBackupService(
        tmp_path / "auto_backup_settings.json",
        backup_service=WorkflowBackupService(),
    )


def test_first_due_check_creates_backup_and_persists_success(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)
    service = _service(tmp_path)
    service.update_preferences(
        enabled=True,
        interval_hours=24,
        retention_count=10,
        directory=tmp_path / "automatic",
    )

    result = service.run_if_due(repository, now=NOW)

    assert result.executed
    assert result.backup is not None
    assert result.backup.path.exists()
    assert result.settings.last_success_at == "2026-07-11T20:00:00"
    assert result.next_run_at == NOW + timedelta(hours=24)

    payload = json.loads(
        service.settings_path.read_text(encoding="utf-8")
    )
    assert payload["last_success_at"] == "2026-07-11T20:00:00"


def test_schedule_skips_before_interval_and_runs_when_due(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)
    service = _service(tmp_path)
    service.save_settings(
        WorkflowAutoBackupSettings(
            enabled=True,
            interval_hours=6,
            retention_count=10,
            directory=str(tmp_path / "automatic"),
            last_success_at=NOW.isoformat(timespec="seconds"),
        )
    )

    early = service.run_if_due(
        repository,
        now=NOW + timedelta(hours=5),
    )
    due = service.run_if_due(
        repository,
        now=NOW + timedelta(hours=6),
    )

    assert not early.executed
    assert early.next_run_at == NOW + timedelta(hours=6)
    assert due.executed


def test_force_creates_backup_when_schedule_is_disabled(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)
    service = _service(tmp_path)
    service.update_preferences(
        enabled=False,
        interval_hours=24,
        retention_count=10,
        directory=tmp_path / "automatic",
    )

    skipped = service.run_if_due(repository, now=NOW)
    forced = service.run_if_due(
        repository,
        now=NOW,
        force=True,
    )

    assert not skipped.executed
    assert forced.executed
    assert forced.settings.enabled is False


def test_retention_removes_only_old_automatic_backups(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)
    service = _service(tmp_path)
    directory = tmp_path / "automatic"
    service.update_preferences(
        enabled=True,
        interval_hours=1,
        retention_count=2,
        directory=directory,
    )

    for offset in range(4):
        service.run_if_due(
            repository,
            now=NOW + timedelta(hours=offset),
            force=True,
        )

    manual = directory / "manual.ctbackup"
    manual.write_bytes(b"manual")
    service.prune_backups(directory, retention_count=2)

    automatic = list(
        directory.glob("CORTERIS_auto_*.ctbackup")
    )
    assert len(automatic) == 2
    assert manual.exists()


def test_invalid_preferences_are_clamped(tmp_path) -> None:
    service = _service(tmp_path)

    saved = service.save_settings(
        WorkflowAutoBackupSettings(
            interval_hours=0,
            retention_count=999,
        )
    )

    assert saved.interval_hours == 1
    assert saved.retention_count == 100
