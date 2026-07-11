"""Tests for business workflow database diagnostics and recovery."""

from __future__ import annotations

from datetime import datetime
import json

from app.core.workflow_backup import WorkflowBackupService
from app.core.workflow_backup_catalog import (
    WorkflowBackupCatalogService,
)
from app.core.workflow_database_health import (
    WorkflowDatabaseHealthService,
    WorkflowDatabaseHealthStatus,
)
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)


NOW = datetime(2026, 7, 11, 22, 0, 0)


def _service() -> WorkflowDatabaseHealthService:
    backup = WorkflowBackupService()
    return WorkflowDatabaseHealthService(
        backup_service=backup,
        catalog_service=WorkflowBackupCatalogService(backup),
    )


def _seed(repository: BusinessMetricsRepository, tender: str):
    return repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id=tender,
        title=f"КП {tender}",
        status=BusinessStatus.READY,
        total=500_000,
        profit=100_000,
        margin_percent=20,
    )


def test_healthy_database_passes_full_diagnostics(tmp_path) -> None:
    repository = BusinessMetricsRepository(
        tmp_path / "business_workflow.json"
    )
    _seed(repository, "T-86")

    report = _service().inspect(repository)

    assert report.status == WorkflowDatabaseHealthStatus.HEALTHY
    assert report.safe_for_backup
    assert report.record_count == 1
    assert report.event_count == 1
    assert report.issues == ()


def test_corrupted_json_detected_and_latest_backup_selected(
    tmp_path,
) -> None:
    repository = BusinessMetricsRepository(
        tmp_path / "business_workflow.json"
    )
    _seed(repository, "T-OLD")

    backup_service = WorkflowBackupService()
    backup_dir = tmp_path / "backups"
    older = backup_service.create_backup(
        repository,
        backup_dir / "older.ctbackup",
        created_at=datetime(2026, 7, 11, 20, 0),
    )
    _seed(repository, "T-NEW")
    newer = backup_service.create_backup(
        repository,
        backup_dir / "newer.ctbackup",
        created_at=NOW,
    )
    repository.path.write_text("{broken", encoding="utf-8")

    service = WorkflowDatabaseHealthService(
        backup_service=backup_service,
        catalog_service=WorkflowBackupCatalogService(
            backup_service
        ),
    )
    report = service.inspect(
        repository,
        backup_directories=[backup_dir],
    )

    assert report.status == WorkflowDatabaseHealthStatus.CORRUPTED
    assert report.requires_recovery
    assert report.latest_valid_backup is not None
    assert report.latest_valid_backup.path == newer.path
    assert report.latest_valid_backup.path != older.path


def test_recover_latest_quarantines_corrupted_json(tmp_path) -> None:
    repository = BusinessMetricsRepository(
        tmp_path / "business_workflow.json"
    )
    original = _seed(repository, "T-RESTORE")
    backup_service = WorkflowBackupService()
    backup_dir = tmp_path / "backups"
    backup_service.create_backup(
        repository,
        backup_dir / "valid.ctbackup",
        created_at=NOW,
    )
    damaged_text = '{"schema_version": 2, "records": ['
    repository.path.write_text(damaged_text, encoding="utf-8")

    service = WorkflowDatabaseHealthService(
        backup_service=backup_service,
        catalog_service=WorkflowBackupCatalogService(
            backup_service
        ),
    )
    result = service.recover_latest(
        repository,
        backup_directories=[backup_dir],
        recovered_at=NOW,
    )

    assert result.report.status == WorkflowDatabaseHealthStatus.HEALTHY
    assert result.quarantine_path is not None
    assert result.quarantine_path.read_text(
        encoding="utf-8"
    ) == damaged_text
    assert repository.get_record(original.id) is not None


def test_initialize_empty_preserves_corrupted_file(tmp_path) -> None:
    repository = BusinessMetricsRepository(
        tmp_path / "business_workflow.json"
    )
    repository.path.write_text("not-json", encoding="utf-8")

    result = _service().initialize_empty(
        repository,
        initialized_at=NOW,
    )

    assert result.initialized_empty
    assert result.quarantine_path is not None
    assert result.quarantine_path.read_text(
        encoding="utf-8"
    ) == "not-json"
    payload = json.loads(
        repository.path.read_text(encoding="utf-8")
    )
    assert payload["schema_version"] == repository.SCHEMA_VERSION
    assert payload["records"] == []
    assert payload["events"] == []
    assert result.report.status == WorkflowDatabaseHealthStatus.EMPTY


def test_newer_schema_is_marked_incompatible(tmp_path) -> None:
    repository = BusinessMetricsRepository(
        tmp_path / "business_workflow.json"
    )
    repository.path.write_text(
        json.dumps(
            {
                "schema_version": repository.SCHEMA_VERSION + 1,
                "records": [],
                "events": [],
            }
        ),
        encoding="utf-8",
    )

    report = _service().inspect(repository)

    assert report.status == WorkflowDatabaseHealthStatus.INCOMPATIBLE
    assert report.requires_recovery
