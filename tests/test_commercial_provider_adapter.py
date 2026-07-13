from __future__ import annotations

import asyncio

import pytest

from app.tenders.provider_base import (
    ProviderHealthStatus,
    ProviderNotConfiguredError,
    TenderSearchQuery,
)
from app.tenders.providers.commercial_adapter import (
    AsyncCommercialAccessProvider,
)
from app.tenders.providers.commercial_catalog import (
    CommercialProviderState,
    create_commercial_provider_catalog,
)


def test_disabled_adapter_reports_not_configured_without_network() -> None:
    async def scenario() -> None:
        settings = create_commercial_provider_catalog(environment={}).get("b2b_center")
        provider = AsyncCommercialAccessProvider(settings)

        health = await provider.check_health()
        assert health.status == ProviderHealthStatus.NOT_CONFIGURED
        assert "отключён" in health.message

        with pytest.raises(ProviderNotConfiguredError):
            await provider.search(TenderSearchQuery())

    asyncio.run(scenario())


def test_ready_for_verification_is_still_not_a_working_connector() -> None:
    async def scenario() -> None:
        settings = create_commercial_provider_catalog(
            environment={
                "CORTERIS_B2B_ENABLED": "true",
                "CORTERIS_B2B_ACCESS_CONFIRMED": "true",
                "CORTERIS_B2B_API_KEY": "test-secret",
                "CORTERIS_B2B_API_BASE_URL": "https://api.example.test/",
            }
        ).get("b2b_center")
        provider = AsyncCommercialAccessProvider(settings)

        assert settings.state == CommercialProviderState.READY_FOR_VERIFICATION
        health = await provider.check_health()
        assert health.status == ProviderHealthStatus.UNKNOWN
        assert "рабочим" in health.message

        with pytest.raises(ProviderNotConfiguredError) as captured:
            await provider.search(TenderSearchQuery())
        assert "контракт" in str(captured.value).casefold()

    asyncio.run(scenario())
