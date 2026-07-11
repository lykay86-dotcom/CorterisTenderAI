"""Test helpers for TenderSearchEngine."""

from __future__ import annotations

from dataclasses import dataclass
from time import sleep

from app.tenders.models import (
    TenderCustomer,
    TenderDocument,
    TenderMoney,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)
from app.tenders.provider_base import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderHealth,
    ProviderHealthStatus,
    TenderProvider,
    TenderSearchQuery,
    TenderSearchResult,
)


@dataclass
class FakeProvider(TenderProvider):
    descriptor: ProviderDescriptor
    items: tuple[UnifiedTender, ...] = ()
    error: Exception | None = None
    delay_seconds: float = 0.0
    warnings: tuple[str, ...] = ()

    def search(
        self,
        query: TenderSearchQuery,
    ) -> TenderSearchResult:
        if self.delay_seconds:
            sleep(self.delay_seconds)
        if self.error is not None:
            raise self.error
        return TenderSearchResult(
            provider_id=self.descriptor.id,
            items=self.items,
            total=len(self.items),
            page=query.page,
            page_size=query.page_size,
            warnings=self.warnings,
        )

    def get_tender(self, external_id: str) -> UnifiedTender:
        for item in self.items:
            if item.external_id == external_id:
                return item
        raise KeyError(external_id)

    def list_documents(
        self,
        external_id: str,
    ) -> tuple[TenderDocument, ...]:
        return self.get_tender(external_id).documents

    def check_health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.descriptor.id,
            status=ProviderHealthStatus.AVAILABLE,
            checked_at="2026-07-12T20:00:00+00:00",
        )


def descriptor(
    provider_id: str,
    source: TenderSource,
    *,
    priority: int,
    enabled: bool = True,
) -> ProviderDescriptor:
    return ProviderDescriptor(
        id=provider_id,
        display_name=provider_id.upper(),
        source=source,
        homepage_url=f"https://{provider_id}.example.org/",
        capabilities=ProviderCapabilities(
            search=True,
            tender_details=True,
            documents=True,
        ),
        enabled_by_default=enabled,
        priority=priority,
        implementation_status="test",
    )


def tender(
    *,
    source: TenderSource,
    external_id: str,
    procurement_number: str,
    title: str,
    description: str = "",
    region: str = "",
    amount: str | None = None,
    tags: tuple[str, ...] = (),
    documents: tuple[TenderDocument, ...] = (),
) -> UnifiedTender:
    return UnifiedTender(
        source=source,
        external_id=external_id,
        procurement_number=procurement_number,
        title=title,
        customer=TenderCustomer(
            name="Заказчик",
            inn="7700000000",
        ),
        source_url=(
            f"https://{source.value}.example.org/"
            f"{external_id}"
        ),
        price=(
            TenderMoney.from_value(amount)
            if amount is not None
            else None
        ),
        status=TenderStatus.ACCEPTING_APPLICATIONS,
        description=description,
        region=region,
        tags=tags,
        documents=documents,
    )
