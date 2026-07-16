"""RM-131 one-snapshot manager/session/factory/scheduler contract."""

from __future__ import annotations

import asyncio

from app.tenders.collector.async_provider_factory import create_default_async_providers
from app.tenders.collector.network_runtime import create_collector_network_runtime
from app.tenders.collector.provider_control import CollectorProviderManager
from app.tenders.collector.provider_settings import ProviderConfiguration
from app.tenders.collector.run_session import CollectorRunSession
from app.tenders.provider_base import TenderSearchQuery


class _FakeRuntime:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class _FakeService:
    async def collect(self, _query, **_kwargs):
        return "done"


def test_session_passes_one_captured_manager_snapshot_to_service_factory(tmp_path) -> None:
    manager = CollectorProviderManager(tmp_path, environment={})
    manager.set_enabled("b2b_center", True)
    manager.set_configuration(
        "b2b_center",
        ProviderConfiguration(
            access_confirmed=True,
            api_base_url="https://api.b2b.test/v1",
        ),
    )
    expected = manager.settings_snapshot()
    runtime = _FakeRuntime()
    captured = []

    def service_factory(_data_directory, _runtime, **kwargs):
        captured.append(kwargs["provider_settings_snapshot"])
        return _FakeService()

    session = CollectorRunSession(
        tmp_path,
        runtime_factory=lambda: runtime,
        service_factory=service_factory,
        provider_settings_snapshot_factory=manager.settings_snapshot,
    )

    result = asyncio.run(session.run(TenderSearchQuery(), provider_ids=("b2b_center",)))

    assert result == "done"
    assert runtime.closed
    assert captured == [expected]


def test_factory_uses_snapshot_configuration_instead_of_legacy_file(tmp_path) -> None:
    manager = CollectorProviderManager(tmp_path, environment={})
    manager.set_enabled("b2b_center", True)
    manager.set_configuration(
        "b2b_center",
        ProviderConfiguration(
            access_confirmed=True,
            api_base_url="https://canonical.example.test/v1",
        ),
    )
    (tmp_path / "commercial_provider_settings.json").write_text(
        '{"schema_version": 1, "providers": {"b2b_center": '
        '{"enabled": false, "access_confirmed": false, '
        '"api_base_url": "https://legacy.example.test"}}}',
        encoding="utf-8",
    )
    snapshot = manager.settings_snapshot()
    runtime = create_collector_network_runtime()

    try:
        providers = create_default_async_providers(
            runtime,
            include_commercial_catalog=True,
            include_disabled=True,
            provider_settings_snapshot=snapshot,
            environment={},
        )
    finally:
        asyncio.run(runtime.aclose())

    b2b = next(item for item in providers if item.descriptor.id == "b2b_center")
    assert b2b.settings.enabled is True
    assert b2b.settings.access_confirmed is True
    assert b2b.settings.api_base_url == "https://canonical.example.test/v1"


def test_manager_resolves_profile_and_scheduler_aliases_without_file_rewrite(tmp_path) -> None:
    manager = CollectorProviderManager(tmp_path, environment={})
    manager.set_enabled("sber_commercial", True)

    assert manager.resolve_provider_ids(("sber_a", "eis")) == (
        "sber_commercial",
        "eis",
    )
