"""RM-133 manager commands and pre-runtime execution guards."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.tenders.collector.manual_provider_registration import (
    ManualProviderCommandStatus,
    ManualProviderDraft,
    ManualProviderExecutionError,
    ManualProviderLifecycle,
)
from app.tenders.collector.provider_control import CollectorProviderManager
from app.tenders.collector.run_session import CollectorRunSession
from app.tenders.provider_base import TenderSearchQuery


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


def test_manual_registration_cannot_be_enabled(tmp_path) -> None:
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: f"manual_{'9' * 32}",
    )
    created = manager.register_manual_provider(_draft())

    with pytest.raises(ManualProviderExecutionError, match="выбор протокола"):
        manager.set_enabled(created.provider_id, True)

    assert manager.settings_snapshot().get(created.provider_id).enabled is False


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


def test_async_factory_source_has_no_dynamic_manual_adapter_path() -> None:
    source = Path("app/tenders/collector/async_provider_factory.py").read_text(encoding="utf-8")

    assert "importlib" not in source
    assert "eval(" not in source
    assert "exec(" not in source
    assert "ManualProviderRegistration" not in source
