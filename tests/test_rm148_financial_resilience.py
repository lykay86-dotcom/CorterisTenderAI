"""RM-148 transaction, rollback, backup and concurrency evidence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json

import pytest

from app.core.workflow_backup import WorkflowBackupService
from app.financial import FinancialMigrationError
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)
from app.repositories.business_metrics_migration import BusinessMetricsV3Migration


def test_migration_failure_restores_original_bytes(tmp_path, monkeypatch) -> None:
    path = tmp_path / "workflow.json"
    source = b'{"schema_version":2,"records":[],"events":[]}'
    path.write_bytes(source)
    migration = BusinessMetricsV3Migration(BusinessMetricsRepository(path))
    real_replace = __import__("os").replace
    calls = 0

    def fail_once(source_path, target_path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("injected replace failure")
        return real_replace(source_path, target_path)

    monkeypatch.setattr("app.repositories.business_metrics_migration.os.replace", fail_once)

    with pytest.raises(FinancialMigrationError):
        migration.execute()

    assert path.read_bytes() == source


def test_concurrent_writers_keep_all_exact_records(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")

    def save(index: int) -> None:
        repository.save_record(
            kind=BusinessRecordKind.PROPOSAL,
            tender_id=f"T-{index}",
            title=f"Record {index}",
            status=BusinessStatus.READY,
            total=Decimal("0.10"),
            profit=Decimal("0.01"),
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        tuple(pool.map(save, range(40)))

    records = repository.list_records()
    assert len(records) == 40
    assert all(record.total == Decimal("0.10") for record in records)
    assert len({record.id for record in records}) == 40


def test_backup_restore_preserves_v3_fixed_point_strings(tmp_path) -> None:
    source = BusinessMetricsRepository(tmp_path / "source.json")
    source.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-1",
        title="Exact",
        status=BusinessStatus.READY,
        total=Decimal("0.10"),
        profit=Decimal("0.01"),
    )
    backup = WorkflowBackupService().create_backup(source, tmp_path / "exact.ctbackup")
    target = BusinessMetricsRepository(tmp_path / "target.json")

    WorkflowBackupService().restore_backup(backup.path, target)
    payload = json.loads(target.path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 3
    assert payload["records"][0]["total"] == "0.10"
    assert payload["records"][0]["profit"] == "0.01"
    assert payload["records"][0]["currency"] == "RUB"
