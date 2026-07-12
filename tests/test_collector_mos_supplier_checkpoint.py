from __future__ import annotations

from datetime import date, datetime, timezone

from app.tenders.collector.mos_supplier_checkpoint import (
    MosSupplierCheckpointCoordinator,
    MosSupplierCheckpointPolicy,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.models import (
    TenderCustomer,
    TenderSource,
    UnifiedTender,
)
from app.tenders.provider_base import TenderSearchQuery, TenderSearchResult


def _tender() -> UnifiedTender:
    return UnifiedTender(
        source=TenderSource.MOS_SUPPLIER,
        external_id="9294080",
        procurement_number="КС-9294080",
        title="Монтаж видеонаблюдения",
        customer=TenderCustomer(name="Заказчик"),
        source_url="https://zakupki.mos.ru/auction/9294080",
        published_at=datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc),
    )


def test_checkpoint_applies_publication_overlap(tmp_path) -> None:
    repository = CollectorStateRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    coordinator = MosSupplierCheckpointCoordinator(
        repository,
        policy=MosSupplierCheckpointPolicy(overlap_days=7),
    )
    query = TenderSearchQuery(
        keywords=("видеонаблюдение",),
        extra={"incremental": True},
    )
    prepared = coordinator.prepare(query)
    result = TenderSearchResult(
        provider_id="mos_supplier",
        items=(_tender(),),
    )
    coordinator.mark_success(prepared, result)

    next_prepared = coordinator.prepare(query)

    assert next_prepared.incremental_applied
    assert next_prepared.query.date_from == date(2026, 7, 3)
    assert next_prepared.checkpoint is not None
    assert next_prepared.checkpoint.watermark.startswith("2026-07-10")


def test_explicit_date_disables_checkpoint_override(tmp_path) -> None:
    repository = CollectorStateRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    coordinator = MosSupplierCheckpointCoordinator(repository)
    initial = TenderSearchQuery(keywords=("СКУД",))
    coordinator.mark_success(
        coordinator.prepare(initial),
        TenderSearchResult(provider_id="mos_supplier", items=(_tender(),)),
    )
    explicit = TenderSearchQuery(
        keywords=("СКУД",),
        date_from=date(2026, 1, 1),
    )

    prepared = coordinator.prepare(explicit)

    assert not prepared.incremental_applied
    assert prepared.query.date_from == date(2026, 1, 1)
