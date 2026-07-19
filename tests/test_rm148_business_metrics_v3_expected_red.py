"""Expected-red v3 persistence and controlled migration contract for RM-148."""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json

import pytest

from app.financial import FinancialMigrationError
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
    BusinessWorkflowRecord,
)
from app.repositories.business_metrics_migration import BusinessMetricsV3Migration


def test_new_repository_persists_exact_v3_fixed_point_strings(tmp_path) -> None:
    path = tmp_path / "business_workflow.json"
    repository = BusinessMetricsRepository(path)

    record = repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-148",
        title="Exact",
        status=BusinessStatus.READY,
        total=Decimal("0.10"),
        profit=Decimal("0.01"),
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    stored = payload["records"][0]

    assert repository.SCHEMA_VERSION == 3
    assert record.total == Decimal("0.10")
    assert record.profit == Decimal("0.01")
    assert record.margin_percent == Decimal("10.00")
    assert stored["total"] == "0.10"
    assert stored["profit"] == "0.01"
    assert stored["currency"] == "RUB"
    assert stored["margin_percent"] == "10.00"
    assert stored["margin_version"] == "workflow-revenue-margin-v1"


def test_direct_record_float_is_rejected() -> None:
    with pytest.raises(TypeError):
        BusinessWorkflowRecord(
            id="float",
            kind="proposal",
            tender_id="T-1",
            title="Float",
            status="ready",
            total=0.1,  # type: ignore[arg-type]
        )


def test_legacy_read_is_exact_and_does_not_rewrite_bytes(tmp_path) -> None:
    path = tmp_path / "business_workflow.json"
    source = b'{"schema_version":2,"records":[{"id":"legacy","kind":"proposal","tender_id":"T-1","title":"Legacy","status":"ready","total":0.1,"profit":0.01,"margin_percent":10.0}],"events":[]}'
    path.write_bytes(source)
    repository = BusinessMetricsRepository(path)

    record = repository.get_record("legacy")

    assert record is not None
    assert record.total == Decimal("0.1")
    assert record.profit == Decimal("0.01")
    assert record.currency == "RUB"
    assert repository.requires_migration
    assert path.read_bytes() == source


def test_v2_migration_dry_run_backup_and_readback_are_exact(tmp_path) -> None:
    path = tmp_path / "business_workflow.json"
    source = b'{"schema_version":2,"records":[{"id":"legacy","kind":"proposal","tender_id":"T-1","title":"Legacy","status":"ready","total":0.1,"profit":0.01,"margin_percent":10.0}],"events":[]}'
    path.write_bytes(source)
    repository = BusinessMetricsRepository(path)
    migration = BusinessMetricsV3Migration(repository)

    plan = migration.dry_run()

    assert plan.source_sha256 == hashlib.sha256(source).hexdigest()
    assert plan.source_schema == 2
    assert plan.target_schema == 3
    assert plan.record_count == 1
    assert not plan.issues
    assert path.read_bytes() == source

    result = migration.execute(plan)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert result.backup_path.read_bytes() == source
    assert result.target_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert payload["schema_version"] == 3
    assert payload["records"][0]["total"] == "0.10"
    assert payload["records"][0]["profit"] == "0.01"
    assert payload["records"][0]["currency"] == "RUB"
    assert repository.get_record("legacy").total == Decimal("0.10")  # type: ignore[union-attr]


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1e3", "1.005", "-0.01"])
def test_migration_stops_on_unsafe_legacy_value(tmp_path, value: str) -> None:
    path = tmp_path / "business_workflow.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "records": [
                    {
                        "id": "unsafe",
                        "kind": "proposal",
                        "tender_id": "T-1",
                        "title": "Unsafe",
                        "status": "ready",
                        "total": value,
                        "profit": 0,
                        "margin_percent": 0,
                    }
                ],
                "events": [],
            }
        ),
        encoding="utf-8",
    )
    source = path.read_bytes()

    with pytest.raises(FinancialMigrationError):
        BusinessMetricsV3Migration(BusinessMetricsRepository(path)).execute()

    assert path.read_bytes() == source
