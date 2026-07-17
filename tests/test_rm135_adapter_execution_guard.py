"""RM-135 configured does not imply verified, enabled or runnable."""

from __future__ import annotations

from app.tenders.collector.manual_adapter import ManualAdapterReadiness
from app.tenders.collector.manual_provider_registration import ManualProviderLifecycle


def test_configured_lifecycle_is_still_connection_test_required() -> None:
    assert ManualProviderLifecycle.CONNECTION_TEST_REQUIRED.value == "connection_test_required"
    assert ManualAdapterReadiness.CONNECTION_TEST_REQUIRED.value == "connection_test_required"
    assert "ready" not in {item.value for item in ManualProviderLifecycle}
    assert "verified" not in {item.value for item in ManualProviderLifecycle}
    assert "runnable" not in {item.value for item in ManualProviderLifecycle}
