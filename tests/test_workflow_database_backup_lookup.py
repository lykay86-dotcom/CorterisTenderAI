"""Tests for bounded, non-recursive backup discovery."""

from __future__ import annotations

from datetime import datetime

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


def test_health_check_does_not_use_recursive_catalog_scan(
    tmp_path,
    monkeypatch,
) -> None:
    repository = BusinessMetricsRepository(tmp_path / "business_workflow.json")
    repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-86-1",
        title="КП",
        status=BusinessStatus.READY,
    )

    backup_service = WorkflowBackupService()
    catalog = WorkflowBackupCatalogService(backup_service)
    backup_dir = tmp_path / "backups"
    backup_service.create_backup(
        repository,
        backup_dir / "latest.ctbackup",
        created_at=datetime(2026, 7, 11, 22, 30),
    )

    def forbidden_recursive_scan(*args, **kwargs):
        raise AssertionError("Health diagnostics must not call list_backups/rglob")

    monkeypatch.setattr(
        catalog,
        "list_backups",
        forbidden_recursive_scan,
    )

    health = WorkflowDatabaseHealthService(
        backup_service=backup_service,
        catalog_service=catalog,
    )
    report = health.inspect(
        repository,
        backup_directories=[backup_dir],
    )

    assert report.latest_valid_backup is not None
    assert report.latest_valid_backup.path.name == "latest.ctbackup"


def test_health_check_does_not_descend_into_unlisted_subfolders(
    tmp_path,
) -> None:
    repository = BusinessMetricsRepository(tmp_path / "business_workflow.json")
    repository.save_record(
        kind=BusinessRecordKind.ESTIMATE,
        tender_id="T-86-2",
        title="Смета",
        status=BusinessStatus.DRAFT,
    )

    backup_service = WorkflowBackupService()
    root = tmp_path / "backups"
    nested = root / "deep" / "nested"
    backup_service.create_backup(
        repository,
        nested / "hidden.ctbackup",
        created_at=datetime(2026, 7, 11, 22, 31),
    )

    health = WorkflowDatabaseHealthService(
        backup_service=backup_service,
        catalog_service=WorkflowBackupCatalogService(backup_service),
    )

    root_only = health.inspect(
        repository,
        backup_directories=[root],
    )
    explicit_nested = health.inspect(
        repository,
        backup_directories=[root, nested],
    )

    assert root_only.latest_valid_backup is None
    assert explicit_nested.latest_valid_backup is not None
