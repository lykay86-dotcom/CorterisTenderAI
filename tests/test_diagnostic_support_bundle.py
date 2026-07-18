"""Tests for privacy-aware diagnostic support bundles."""

from __future__ import annotations

from datetime import datetime
import json
from zipfile import ZIP_DEFLATED, ZipFile

from app.core.diagnostic_support_bundle import (
    DiagnosticSupportBundleService,
)
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


NOW = datetime(2026, 7, 12, 10, 0, 0)


def _context(tmp_path):
    repository = BusinessMetricsRepository(tmp_path / "private-user" / "business_workflow.json")
    repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="SECRET-TENDER-89",
        title="Секретное коммерческое предложение",
        status=BusinessStatus.READY,
    )

    backup = WorkflowBackupService()
    catalog = WorkflowBackupCatalogService(backup)
    database_health = WorkflowDatabaseHealthService(
        backup_service=backup,
        catalog_service=catalog,
    )
    auto = WorkflowAutoBackupService(
        tmp_path / "private-user" / "auto_settings.json",
        backup_service=backup,
    )
    journal = SystemHealthJournal(tmp_path / "private-user" / "journal.json")
    journal.record(
        severity=SystemHealthSeverity.ERROR,
        component="api",
        title="Ошибка подключения",
        details=(
            f"Path={repository.path}; "
            "email=user@example.com; "
            "Authorization: Bearer secret-token-123"
        ),
        occurred_at=NOW,
    )
    snapshot = SystemHealthService().collect(
        repository=repository,
        database_health_service=database_health,
        auto_backup_service=auto,
        backup_catalog_service=catalog,
        journal=journal,
        backup_directories=[tmp_path / "backups"],
    )
    return repository, backup, catalog, auto, journal, snapshot


def test_bundle_contains_required_diagnostics_but_not_database(
    tmp_path,
) -> None:
    repository, _, catalog, auto, journal, snapshot = _context(tmp_path)
    service = DiagnosticSupportBundleService()

    result = service.create_bundle(
        tmp_path / "support",
        repository=repository,
        snapshot=snapshot,
        journal=journal,
        auto_backup_service=auto,
        backup_catalog_service=catalog,
        backup_directories=[tmp_path / "backups"],
        created_at=NOW,
    )

    assert result.path.suffix == ".ctsupport"
    assert service.inspect_bundle(result.path).valid

    with ZipFile(result.path) as archive:
        names = set(archive.namelist())
        assert service.REQUIRED_FILES <= names
        assert "business_workflow.json" not in names

        summary = json.loads(archive.read("database_summary.json"))
        assert summary["record_count"] == 1
        assert summary["raw_database_included"] is False

        combined = b"\n".join(
            archive.read(name) for name in names if not name.endswith("/")
        ).decode("utf-8-sig", errors="replace")

    assert "SECRET-TENDER-89" not in combined
    assert "Секретное коммерческое предложение" not in combined


def test_bundle_redacts_paths_email_and_secrets_from_logs(
    tmp_path,
) -> None:
    repository, _, catalog, auto, journal, snapshot = _context(tmp_path)
    logs = repository.path.parent / "logs"
    logs.mkdir()
    log_file = logs / "application.log"
    log_file.write_text(
        (
            f"Database: {repository.path}\n"
            "Contact: user@example.com\n"
            "api_key=top-secret-key\n"
            "Authorization: Bearer abcdefghijklmnop\n"
            "Authorization: Bearer RM140_SECRET_SENTINEL\n"
        ),
        encoding="utf-8",
    )

    result = DiagnosticSupportBundleService().create_bundle(
        tmp_path / "support.ctsupport",
        repository=repository,
        snapshot=snapshot,
        journal=journal,
        auto_backup_service=auto,
        backup_catalog_service=catalog,
        backup_directories=[tmp_path / "backups"],
        created_at=NOW,
    )

    with ZipFile(result.path) as archive:
        text = "\n".join(
            archive.read(name).decode(
                "utf-8-sig",
                errors="replace",
            )
            for name in archive.namelist()
            if name.startswith("logs/") or name == "system_health_journal.txt"
        )

    assert str(repository.path.parent) not in text
    assert "user@example.com" not in text
    assert "top-secret-key" not in text
    assert "abcdefghijklmnop" not in text
    assert "RM140_SECRET_SENTINEL" not in text
    assert "<PRIVATE_PATH>" in text
    assert "<EMAIL>" in text
    assert "<REDACTED>" in text


def test_bundle_inspection_detects_tampered_file(tmp_path) -> None:
    repository, _, catalog, auto, journal, snapshot = _context(tmp_path)
    service = DiagnosticSupportBundleService()
    valid = service.create_bundle(
        tmp_path / "valid.ctsupport",
        repository=repository,
        snapshot=snapshot,
        journal=journal,
        auto_backup_service=auto,
        backup_catalog_service=catalog,
        backup_directories=[],
        created_at=NOW,
    )

    tampered = tmp_path / "tampered.ctsupport"
    with (
        ZipFile(valid.path) as source,
        ZipFile(
            tampered,
            "w",
            compression=ZIP_DEFLATED,
        ) as target,
    ):
        for name in source.namelist():
            content = source.read(name)
            if name == "environment.json":
                content = b'{"changed": true}'
            target.writestr(name, content)

    inspection = service.inspect_bundle(tampered)

    assert not inspection.valid
    assert any("environment.json" in error and "сумма" in error for error in inspection.errors)
