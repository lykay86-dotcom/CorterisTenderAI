"""Tests for workflow backup creation, validation and restore."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from zipfile import ZIP_DEFLATED, ZipFile

from app.core.workflow_backup import WorkflowBackupService
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)


NOW = datetime(2026, 7, 11, 19, 30, 0)


def _seed(repository: BusinessMetricsRepository, tender: str):
    record = repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id=tender,
        title=f"КП {tender}",
        status=BusinessStatus.READY,
        total=500_000,
        profit=100_000,
        margin_percent=20,
    )
    repository.update_status(record.id, BusinessStatus.SENT)
    return record


def test_create_backup_contains_manifest_and_payload(tmp_path) -> None:
    repository = BusinessMetricsRepository(
        tmp_path / "business_workflow.json"
    )
    _seed(repository, "T-83")

    result = WorkflowBackupService().create_backup(
        repository,
        tmp_path / "backup",
        created_at=NOW,
    )

    assert result.path.suffix == ".ctbackup"
    assert result.inspection.valid
    assert result.inspection.record_count == 1
    assert result.inspection.event_count == 2

    with ZipFile(result.path) as archive:
        assert set(archive.namelist()) == {
            "manifest.json",
            "business_workflow.json",
        }
        manifest = json.loads(
            archive.read("manifest.json").decode("utf-8")
        )
        payload = archive.read("business_workflow.json")

    assert manifest["created_at"] == "2026-07-11T19:30:00"
    assert manifest["checksum_sha256"] == hashlib.sha256(
        payload
    ).hexdigest()


def test_inspection_rejects_tampered_payload(tmp_path) -> None:
    repository = BusinessMetricsRepository(
        tmp_path / "business_workflow.json"
    )
    _seed(repository, "T-1")
    service = WorkflowBackupService()
    backup = service.create_backup(
        repository,
        tmp_path / "valid.ctbackup",
        created_at=NOW,
    )

    tampered = tmp_path / "tampered.ctbackup"
    with ZipFile(backup.path) as source, ZipFile(
        tampered,
        "w",
        compression=ZIP_DEFLATED,
    ) as target:
        target.writestr(
            "manifest.json",
            source.read("manifest.json"),
        )
        payload = json.loads(
            source.read("business_workflow.json")
        )
        payload["records"][0]["title"] = "Изменено"
        target.writestr(
            "business_workflow.json",
            json.dumps(payload, ensure_ascii=False),
        )

    inspection = service.inspect_backup(tampered)

    assert not inspection.valid
    assert any(
        "Контрольная сумма" in error
        for error in inspection.errors
    )


def test_restore_replaces_store_and_creates_safety_backup(
    tmp_path,
) -> None:
    service = WorkflowBackupService()
    source_repository = BusinessMetricsRepository(
        tmp_path / "source.json"
    )
    source_record = _seed(source_repository, "SOURCE")
    backup = service.create_backup(
        source_repository,
        tmp_path / "source.ctbackup",
        created_at=NOW,
    )

    target_repository = BusinessMetricsRepository(
        tmp_path / "target.json"
    )
    target_record = _seed(target_repository, "TARGET")

    result = service.restore_backup(
        backup.path,
        target_repository,
        safety_directory=tmp_path / "safety",
        restored_at=NOW,
    )

    restored_ids = [
        item.id
        for item in target_repository.list_records(
            include_archived=True
        )
    ]
    assert restored_ids == [source_record.id]
    assert result.safety_backup.exists()
    assert service.inspect_backup(result.safety_backup).valid

    safety_repository = BusinessMetricsRepository(
        tmp_path / "safety_restored.json"
    )
    service.restore_backup(
        result.safety_backup,
        safety_repository,
        safety_directory=tmp_path / "second_safety",
        restored_at=NOW,
    )
    safety_ids = [
        item.id
        for item in safety_repository.list_records(
            include_archived=True
        )
    ]
    assert safety_ids == [target_record.id]


def test_inspection_rejects_orphan_event(tmp_path) -> None:
    service = WorkflowBackupService()
    payload = {
        "schema_version": 2,
        "records": [],
        "events": [
            {
                "id": "event-1",
                "record_id": "missing",
                "action": "created",
                "occurred_at": "2026-07-11T10:00:00",
            }
        ],
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    manifest = {
        "format": service.FORMAT_NAME,
        "format_version": service.FORMAT_VERSION,
        "created_at": NOW.isoformat(timespec="seconds"),
        "schema_version": 2,
        "record_count": 0,
        "event_count": 1,
        "archived_count": 0,
        "checksum_sha256": hashlib.sha256(raw).hexdigest(),
        "payload_name": service.PAYLOAD_NAME,
    }
    path = tmp_path / "orphan.ctbackup"
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            service.MANIFEST_NAME,
            json.dumps(manifest, ensure_ascii=False),
        )
        archive.writestr(service.PAYLOAD_NAME, raw)

    inspection = service.inspect_backup(path)

    assert not inspection.valid
    assert any(
        "неизвестная запись" in error
        for error in inspection.errors
    )
