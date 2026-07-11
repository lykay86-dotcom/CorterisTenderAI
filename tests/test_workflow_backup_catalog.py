"""Tests for workflow backup catalog discovery and deletion."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.core.workflow_backup import WorkflowBackupService
from app.core.workflow_backup_catalog import (
    WorkflowBackupCatalogService,
    WorkflowBackupKind,
)
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)


NOW = datetime(2026, 7, 11, 21, 0, 0)


def _repository(path: Path) -> BusinessMetricsRepository:
    repository = BusinessMetricsRepository(path)
    repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-85",
        title="КП",
        status=BusinessStatus.READY,
    )
    return repository


def test_catalog_scans_classifies_and_sorts_backups(
    tmp_path,
) -> None:
    repository = _repository(tmp_path / "workflow.json")
    backup_service = WorkflowBackupService()
    catalog = WorkflowBackupCatalogService(backup_service)
    directory = tmp_path / "backups"

    manual = backup_service.create_backup(
        repository,
        directory / "CORTERIS_manual.ctbackup",
        created_at=datetime(2026, 7, 11, 19, 0),
    )
    automatic = backup_service.create_backup(
        repository,
        directory / "CORTERIS_auto_20260711_200000.ctbackup",
        created_at=datetime(2026, 7, 11, 20, 0),
    )
    safety = backup_service.create_backup(
        repository,
        directory
        / "CORTERIS_auto_before_restore_20260711_210000.ctbackup",
        created_at=NOW,
    )

    entries = catalog.list_backups([directory])

    assert [entry.path for entry in entries] == [
        safety.path,
        automatic.path,
        manual.path,
    ]
    assert [entry.kind for entry in entries] == [
        WorkflowBackupKind.SAFETY,
        WorkflowBackupKind.AUTOMATIC,
        WorkflowBackupKind.MANUAL,
    ]
    assert all(entry.valid for entry in entries)


def test_catalog_lists_invalid_backup_instead_of_crashing(
    tmp_path,
) -> None:
    directory = tmp_path / "backups"
    directory.mkdir()
    damaged = directory / "damaged.ctbackup"
    damaged.write_text("not a zip", encoding="utf-8")

    catalog = WorkflowBackupCatalogService()
    entries = catalog.list_backups([directory])

    assert len(entries) == 1
    assert entries[0].path == damaged
    assert not entries[0].valid
    assert entries[0].inspection.errors


def test_delete_requires_managed_directory_or_permission(
    tmp_path,
) -> None:
    managed = tmp_path / "managed"
    external = tmp_path / "external"
    managed.mkdir()
    external.mkdir()
    managed_file = managed / "managed.ctbackup"
    external_file = external / "external.ctbackup"
    managed_file.write_bytes(b"x")
    external_file.write_bytes(b"x")

    catalog = WorkflowBackupCatalogService()

    deleted = catalog.delete_backup(
        managed_file,
        managed_directories=[managed],
    )
    assert deleted == managed_file
    assert not managed_file.exists()

    try:
        catalog.delete_backup(
            external_file,
            managed_directories=[managed],
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("Expected PermissionError")

    catalog.delete_backup(
        external_file,
        managed_directories=[managed],
        allow_external=True,
    )
    assert not external_file.exists()
