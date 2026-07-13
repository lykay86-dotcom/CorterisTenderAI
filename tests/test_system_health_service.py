"""Tests for the aggregated system health service."""

from __future__ import annotations

from datetime import datetime

from app.core.system_health import (
    SystemHealthJournal,
    SystemHealthService,
    SystemHealthSeverity,
)
from app.core.workflow_auto_backup import WorkflowAutoBackupService
from app.core.workflow_backup import WorkflowBackupService
from app.core.workflow_backup_catalog import (
    WorkflowBackupCatalogService,
)
from app.core.workflow_database_health import (
    WorkflowDatabaseHealthService,
)
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)


def _services(tmp_path):
    backup = WorkflowBackupService()
    catalog = WorkflowBackupCatalogService(backup)
    health = WorkflowDatabaseHealthService(
        backup_service=backup,
        catalog_service=catalog,
    )
    auto = WorkflowAutoBackupService(
        tmp_path / "auto_settings.json",
        backup_service=backup,
    )
    return backup, catalog, health, auto


def test_snapshot_is_healthy_with_database_and_valid_backup(
    tmp_path,
) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-87",
        title="КП",
        status=BusinessStatus.READY,
    )
    backup, catalog, database_health, auto = _services(tmp_path)
    backup_dir = tmp_path / "backups"
    backup.create_backup(
        repository,
        backup_dir / "valid.ctbackup",
        created_at=datetime(2026, 7, 11, 23, 0),
    )
    journal = SystemHealthJournal(tmp_path / "journal.json")

    snapshot = SystemHealthService().collect(
        repository=repository,
        database_health_service=database_health,
        auto_backup_service=auto,
        backup_catalog_service=catalog,
        journal=journal,
        backup_directories=[backup_dir],
    )

    assert snapshot.severity == SystemHealthSeverity.SUCCESS
    assert snapshot.database.record_count == 1
    assert snapshot.backup_valid == 1
    assert snapshot.backup_invalid == 0


def test_snapshot_reports_corrupted_database_and_backup(
    tmp_path,
) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    repository.path.write_text("{broken", encoding="utf-8")
    backup, catalog, database_health, auto = _services(tmp_path)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "damaged.ctbackup").write_text(
        "broken",
        encoding="utf-8",
    )

    snapshot = SystemHealthService().collect(
        repository=repository,
        database_health_service=database_health,
        auto_backup_service=auto,
        backup_catalog_service=catalog,
        journal=SystemHealthJournal(tmp_path / "journal.json"),
        backup_directories=[backup_dir],
    )

    assert snapshot.severity == SystemHealthSeverity.ERROR
    assert snapshot.database.requires_recovery
    assert snapshot.backup_invalid == 1
    assert snapshot.issues
