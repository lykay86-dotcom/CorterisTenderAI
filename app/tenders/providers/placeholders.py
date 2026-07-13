"""Built-in provider descriptors and non-network placeholders."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from app.tenders.models import (
    TenderDocument,
    TenderSource,
    UnifiedTender,
)
from app.tenders.provider_base import (
    ProviderCapabilities,
    ProviderCapabilityError,
    ProviderDescriptor,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderNotConfiguredError,
    TenderProvider,
    TenderSearchQuery,
    TenderSearchResult,
)


class PlaceholderTenderProvider(TenderProvider):
    """Descriptor-only adapter used until a real connector is enabled."""

    def __init__(
        self,
        descriptor: ProviderDescriptor,
    ) -> None:
        self.descriptor = descriptor

    def search(
        self,
        query: TenderSearchQuery,
    ) -> TenderSearchResult:
        if not self.descriptor.capabilities.search:
            raise ProviderCapabilityError(f"{self.descriptor.display_name} does not support search")
        raise ProviderNotConfiguredError(
            f"{self.descriptor.display_name}: connector is not configured"
        )

    def get_tender(
        self,
        external_id: str,
    ) -> UnifiedTender:
        if not self.descriptor.capabilities.tender_details:
            raise ProviderCapabilityError(
                f"{self.descriptor.display_name} does not support tender details"
            )
        raise ProviderNotConfiguredError(
            f"{self.descriptor.display_name}: connector is not configured"
        )

    def list_documents(
        self,
        external_id: str,
    ) -> Sequence[TenderDocument]:
        if not self.descriptor.capabilities.documents:
            raise ProviderCapabilityError(
                f"{self.descriptor.display_name} does not support documents"
            )
        raise ProviderNotConfiguredError(
            f"{self.descriptor.display_name}: connector is not configured"
        )

    def check_health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.descriptor.id,
            status=ProviderHealthStatus.NOT_CONFIGURED,
            checked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            message="Коннектор подготовлен, но ещё не настроен.",
        )

    def validate_configuration(self) -> tuple[str, ...]:
        return ("Реальная интеграция будет подключена в следующих коммитах.",)


def create_builtin_providers() -> tuple[TenderProvider, ...]:
    """Return the initial provider catalog in default priority order."""

    return tuple(
        PlaceholderTenderProvider(descriptor)
        for descriptor in (
            ProviderDescriptor(
                id="eis",
                display_name="ЕИС Закупки",
                source=TenderSource.EIS,
                homepage_url="https://zakupki.gov.ru/",
                capabilities=ProviderCapabilities(
                    search=True,
                    tender_details=True,
                    documents=True,
                    authentication=False,
                    public_api=True,
                    incremental_updates=True,
                    rate_limit_per_minute=60,
                ),
                priority=10,
            ),
            ProviderDescriptor(
                id="sber_a",
                display_name="Сбер А",
                source=TenderSource.SBER_A,
                homepage_url="https://www.sberbank-ast.ru/",
                capabilities=ProviderCapabilities(
                    search=True,
                    tender_details=True,
                    documents=True,
                    authentication=True,
                    public_api=False,
                ),
                priority=20,
            ),
            ProviderDescriptor(
                id="rts_tender",
                display_name="РТС-тендер",
                source=TenderSource.RTS_TENDER,
                homepage_url="https://www.rts-tender.ru/",
                capabilities=ProviderCapabilities(
                    search=True,
                    tender_details=True,
                    documents=True,
                    authentication=True,
                    public_api=False,
                ),
                priority=30,
            ),
            ProviderDescriptor(
                id="roseltorg",
                display_name="Росэлторг",
                source=TenderSource.ROSELTORG,
                homepage_url="https://www.roseltorg.ru/",
                capabilities=ProviderCapabilities(
                    search=True,
                    tender_details=True,
                    documents=True,
                    authentication=True,
                    public_api=False,
                ),
                priority=40,
            ),
            ProviderDescriptor(
                id="b2b_center",
                display_name="B2B-Center",
                source=TenderSource.B2B_CENTER,
                homepage_url="https://www.b2b-center.ru/",
                capabilities=ProviderCapabilities(
                    search=True,
                    tender_details=True,
                    documents=True,
                    authentication=True,
                    public_api=False,
                ),
                priority=50,
            ),
            ProviderDescriptor(
                id="tek_torg",
                display_name="ТЭК-Торг",
                source=TenderSource.TEK_TORG,
                homepage_url="https://www.tektorg.ru/",
                capabilities=ProviderCapabilities(
                    search=True,
                    tender_details=True,
                    documents=True,
                    authentication=True,
                    public_api=False,
                ),
                priority=60,
            ),
            ProviderDescriptor(
                id="gazprombank",
                display_name="ЭТП Газпромбанка",
                source=TenderSource.GAZPROMBANK,
                homepage_url="https://etpgpb.ru/",
                capabilities=ProviderCapabilities(
                    search=True,
                    tender_details=True,
                    documents=True,
                    authentication=True,
                    public_api=False,
                ),
                priority=70,
            ),
            ProviderDescriptor(
                id="commercial",
                display_name="Коммерческие закупки",
                source=TenderSource.COMMERCIAL,
                homepage_url="https://example.invalid/",
                capabilities=ProviderCapabilities(
                    search=False,
                    tender_details=False,
                    documents=False,
                    authentication=False,
                    public_api=False,
                ),
                enabled_by_default=False,
                priority=100,
            ),
        )
    )


__all__ = [
    "PlaceholderTenderProvider",
    "create_builtin_providers",
]
