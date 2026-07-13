"""Tests for workflow repository public UI API."""

from __future__ import annotations

from decimal import Decimal

from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)


def test_save_record_and_get_record(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")

    record = repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-15",
        title="КП на умный шлагбаум",
        status=BusinessStatus.READY,
        total=Decimal("850000"),
        profit=Decimal("170000"),
        file_path="proposal.docx",
    )

    loaded = repository.get_record(record.id)

    assert loaded is not None
    assert loaded.title == "КП на умный шлагбаум"
    assert loaded.total == 850000
    assert loaded.profit == 170000


def test_generic_save_upserts_kind_and_tender(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")

    first = repository.save_record(
        kind=BusinessRecordKind.PROJECT,
        tender_id=7,
        title="Проект",
        status=BusinessStatus.PLANNED,
    )
    second = repository.save_record(
        kind=BusinessRecordKind.PROJECT,
        tender_id=7,
        title="Проект обновлён",
        status=BusinessStatus.ACTIVE,
    )

    assert first.id == second.id
    assert len(repository.list_records()) == 1
    assert repository.get_record(first.id).status == "active"
