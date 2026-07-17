"""RM-133 one resolved built-in/manual provider catalog contract."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.tenders.collector.manual_provider_registration import (
    ManualProviderLifecycle,
    ManualProviderRegistration,
)
from app.tenders.collector.provider_definitions import (
    ProviderCatalogOrigin,
    canonical_provider_definitions,
    resolved_provider_catalog,
)
from app.tenders.models import TenderSource


def _registration(
    identifier: str = f"manual_{'e' * 32}",
    *,
    name: str = "Ручная площадка",
    endpoint: str = "https://api.example.test/v1",
) -> ManualProviderRegistration:
    now = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)
    return ManualProviderRegistration(
        provider_id=identifier,
        display_name=name,
        homepage_url="https://example.test",
        endpoint_url=endpoint,
        lifecycle_state=ManualProviderLifecycle.PROTOCOL_REQUIRED,
        created_at=now,
        updated_at=now,
    )


def test_static_built_in_catalog_is_unchanged() -> None:
    assert tuple(item.id for item in canonical_provider_definitions()) == (
        "eis",
        "mos_supplier",
        "b2b_center",
        "gazprombank",
        "fabrikant",
        "tek_torg",
        "otc",
        "sber_commercial",
        "rts_commercial",
        "roseltorg_commercial",
    )


def test_manual_registration_appears_once_with_no_runtime_capabilities() -> None:
    registration = _registration()
    entries = resolved_provider_catalog((registration,))
    manual = next(item for item in entries if item.descriptor.id == registration.provider_id)

    assert len(entries) == len(canonical_provider_definitions()) + 1
    assert manual.origin is ProviderCatalogOrigin.MANUAL
    assert manual.lifecycle is ManualProviderLifecycle.PROTOCOL_REQUIRED
    assert manual.registration_only is True
    assert manual.runnable is False
    assert manual.factory_available is False
    assert manual.protocol_configured is False
    assert manual.credential_available is False
    assert manual.health_check_available is False
    assert manual.descriptor.source is TenderSource.CUSTOM
    assert manual.descriptor.enabled_by_default is False
    assert not any(vars(manual.descriptor.capabilities).values())


def test_loading_order_is_deterministic() -> None:
    first = _registration(f"manual_{'f' * 32}", name="Бета", endpoint="https://b.test/api")
    second = _registration(f"manual_{'1' * 32}", name="Альфа", endpoint="https://a.test/api")

    forward = resolved_provider_catalog((first, second))
    reverse = resolved_provider_catalog((second, first))

    assert tuple(item.descriptor.id for item in forward) == tuple(
        item.descriptor.id for item in reverse
    )


@pytest.mark.parametrize(
    "registrations",
    (
        (
            _registration(f"manual_{'2' * 32}", name="Площадка"),
            _registration(
                f"manual_{'3' * 32}",
                name="  ПЛОЩАДКА  ",
                endpoint="https://other.test/api",
            ),
        ),
        (
            _registration(f"manual_{'4' * 32}", endpoint="HTTPS://API.EXAMPLE.TEST:443/v1/"),
            _registration(
                f"manual_{'5' * 32}",
                name="Другая",
                endpoint="https://api.example.test/v1",
            ),
        ),
    ),
)
def test_ambiguous_name_or_endpoint_catalog_fails_closed(registrations) -> None:
    with pytest.raises(ValueError, match="manual provider conflict"):
        resolved_provider_catalog(registrations)
