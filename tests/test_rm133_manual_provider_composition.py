"""RM-133 manager commands and pre-runtime execution guards."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.tenders.collector.async_provider_factory import create_default_async_providers
from app.tenders.collector.manual_provider_registration import (
    ManualProviderCommandStatus,
    ManualProviderDraft,
    ManualProviderExecutionError,
    ManualProviderLifecycle,
)
from app.tenders.collector.provider_control import CollectorProviderManager
from app.tenders.collector.network_runtime import create_collector_network_runtime
from app.tenders.collector.run_session import CollectorRunSession
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.unified_search import (
    UnifiedTenderSearchRequest,
    UnifiedTenderSearchValidationError,
    resolve_unified_tender_search,
)


def _draft(name: str = "Ручная площадка") -> ManualProviderDraft:
    return ManualProviderDraft(
        display_name=name,
        homepage_url="https://example.test",
        endpoint_url="https://api.example.test/v1",
    )


def test_manager_registers_and_updates_through_one_settings_owner(tmp_path) -> None:
    identifiers = iter((f"manual_{'6' * 32}",))
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: next(identifiers),
    )

    created = manager.register_manual_provider(_draft())
    updated = manager.update_manual_provider(created.provider_id, _draft("Новое название"))
    state = next(item for item in manager.states() if item.provider_id == created.provider_id)

    assert created.status is ManualProviderCommandStatus.CREATED
    assert updated.status is ManualProviderCommandStatus.UPDATED
    assert created.provider_id == updated.provider_id
    assert created.lifecycle is ManualProviderLifecycle.PROTOCOL_REQUIRED
    assert manager.settings_repository.path == tmp_path / "collector_provider_settings.json"
    assert state.display_name == "Новое название"
    assert state.enabled is False
    assert state.registration_only is True
    assert state.runnable is False
    assert state.status_text == "Требуется выбор протокола"


def test_concurrent_duplicate_create_commits_once(tmp_path) -> None:
    identifiers = iter((f"manual_{'7' * 32}", f"manual_{'8' * 32}"))
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: next(identifiers),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(lambda _index: manager.register_manual_provider(_draft()), range(2))
        )

    assert {item.status for item in results} == {
        ManualProviderCommandStatus.CREATED,
        ManualProviderCommandStatus.DUPLICATE,
    }
    assert len(manager.settings_snapshot().manual_registrations) == 1


def test_builtin_display_identity_conflict_is_rejected_before_write(tmp_path) -> None:
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: f"manual_{'d' * 32}",
    )

    result = manager.register_manual_provider(
        ManualProviderDraft("  еис закупки  ", "https://custom.example.test")
    )

    assert result.status is ManualProviderCommandStatus.DUPLICATE
    assert not (tmp_path / "collector_provider_settings.json").exists()


def test_manual_registration_cannot_be_enabled(tmp_path) -> None:
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: f"manual_{'9' * 32}",
    )
    created = manager.register_manual_provider(_draft())

    with pytest.raises(ManualProviderExecutionError, match="выбор протокола"):
        manager.set_enabled(created.provider_id, True)

    assert manager.settings_snapshot().get(created.provider_id).enabled is False


def test_unified_resolver_rejects_registration_only_state(tmp_path) -> None:
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: f"manual_{'0' * 32}",
    )
    created = manager.register_manual_provider(_draft())
    from app.tenders.search_profiles import create_builtin_search_profiles

    profile = create_builtin_search_profiles()[0]

    with pytest.raises(UnifiedTenderSearchValidationError, match="выбора протокола"):
        resolve_unified_tender_search(
            UnifiedTenderSearchRequest(
                profile_id=profile.id,
                provider_ids=(created.provider_id,),
            ),
            profiles=(profile,),
            provider_states=manager.states(),
        )


def test_run_session_rejects_manual_id_before_runtime_creation(tmp_path) -> None:
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: f"manual_{'a' * 32}",
    )
    created = manager.register_manual_provider(_draft())
    calls: list[str] = []

    def runtime_factory():
        calls.append("runtime")
        raise AssertionError("runtime must not be created")

    session = CollectorRunSession(
        tmp_path,
        runtime_factory=runtime_factory,
        provider_settings_snapshot_factory=manager.settings_snapshot,
    )

    with pytest.raises(ManualProviderExecutionError) as captured:
        asyncio.run(
            session.run(
                TenderSearchQuery(keywords=("кабель",)),
                provider_ids=(created.provider_id,),
            )
        )

    assert captured.value.lifecycle is ManualProviderLifecycle.PROTOCOL_REQUIRED
    assert calls == []
    assert "api.example" not in str(captured.value)


def test_async_factory_manual_adapter_path_is_static_and_code_owned() -> None:
    source = Path("app/tenders/collector/async_provider_factory.py").read_text(encoding="utf-8")

    assert "importlib" not in source
    assert "eval(" not in source
    assert "exec(" not in source
    assert "build_manual_async_provider" in source
    assert "compile_manual_adapter" in source


def test_async_factory_never_constructs_adapter_for_manual_registration(tmp_path) -> None:
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: f"manual_{'3' * 32}",
    )
    created = manager.register_manual_provider(_draft())
    runtime = create_collector_network_runtime()
    try:
        providers = create_default_async_providers(
            runtime,
            include_commercial_catalog=True,
            provider_settings_snapshot=manager.settings_snapshot(),
            environment={},
            include_disabled=True,
        )
    finally:
        asyncio.run(runtime.aclose())

    ids = {item.descriptor.id for item in providers}
    assert created.provider_id not in ids
    assert len(ids) == 13


def test_conflicting_update_is_atomic_and_keeps_stable_rows(tmp_path) -> None:
    identifiers = iter((f"manual_{'4' * 32}", f"manual_{'5' * 32}"))
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: next(identifiers),
    )
    first = manager.register_manual_provider(_draft("Первая"))
    second = manager.register_manual_provider(
        ManualProviderDraft(
            "Вторая",
            "https://second.example.test",
            "https://api.second.example.test/v1",
        )
    )
    path = tmp_path / "collector_provider_settings.json"
    original = path.read_bytes()

    result = manager.update_manual_provider(
        second.provider_id,
        ManualProviderDraft(
            "Вторая",
            "https://second.example.test",
            "https://api.example.test/v1",
        ),
    )

    assert result.status is ManualProviderCommandStatus.DUPLICATE
    assert path.read_bytes() == original
    assert {item.provider_id for item in manager.settings_snapshot().manual_registrations} == {
        first.provider_id,
        second.provider_id,
    }
