"""Reusable fixtures for collector C3 core tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.tenders.models import (
    TenderCustomer,
    TenderDocument,
    TenderMoney,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)


def make_tender(
    *,
    source: TenderSource = TenderSource.EIS,
    external_id: str = "external-1",
    procurement_number: str = "0373100000126000001",
    title: str = "Монтаж системы видеонаблюдения",
    customer_name: str = "ГБУ Заказчик",
    customer_inn: str = "7701000001",
    amount: str = "1500000.00",
    deadline_day: int = 20,
    status: TenderStatus = TenderStatus.ACCEPTING_APPLICATIONS,
    description: str = "Поставка и монтаж IP-камер",
    documents: tuple[TenderDocument, ...] = (),
    raw_metadata: dict[str, object] | None = None,
) -> UnifiedTender:
    return UnifiedTender(
        source=source,
        external_id=external_id,
        procurement_number=procurement_number,
        title=title,
        customer=TenderCustomer(
            name=customer_name,
            inn=customer_inn,
            region="Москва",
        ),
        source_url=(
            f"https://example.org/{source.value}/{external_id}"
        ),
        published_at=datetime(
            2026,
            7,
            10,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        application_deadline=datetime(
            2026,
            7,
            deadline_day,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        price=TenderMoney(
            Decimal(amount),
            currency="RUB",
        ),
        status=status,
        law="44-ФЗ",
        region="Москва",
        description=description,
        classification_codes=("26.40.33.190",),
        tags=("видеонаблюдение",),
        documents=documents,
        raw_metadata=raw_metadata or {},
    )


def make_document(
    document_id: str,
    *,
    name: str = "Техническое задание.pdf",
    checksum: str = "",
) -> TenderDocument:
    return TenderDocument(
        id=document_id,
        name=name,
        url=f"https://files.example.org/{document_id}.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        checksum_sha256=checksum,
    )
