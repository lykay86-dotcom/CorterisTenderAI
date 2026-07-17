"""RM-134 manager lifecycle, projection and fail-closed runtime guards."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.tenders.collector.manual_provider_protocol import (
    ManualProviderAuthenticationKind,
    ManualProviderPayloadFormat,
    ManualProviderProtocolCommandStatus,
    ManualProviderProtocolDraft,
    ManualProviderProtocolErrorCategory,
    ManualProviderProtocolFamily,
    ManualProviderProtocolReadiness,
)
from app.tenders.collector.manual_provider_registration import (
    ManualProviderCommandStatus,
    ManualProviderDraft,
    ManualProviderExecutionError,
    ManualProviderLifecycle,
)
from app.tenders.collector.provider_control import CollectorProviderManager
from app.tenders.collector.run_session import CollectorRunSession
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.search_profiles import create_builtin_search_profiles
from app.tenders.unified_search import (
    UnifiedTenderSearchRequest,
    UnifiedTenderSearchValidationError,
    resolve_unified_tender_search,
)


MANUAL_ID = f"manual_{'8' * 32}"
NOW = datetime(2026, 7, 17, 13, 0, tzinfo=timezone.utc)


def _manager(tmp_path) -> CollectorProviderManager:
    manager = CollectorProviderManager(
        tmp_path,
        environment={},
        manual_provider_id_factory=lambda: MANUAL_ID,
        manual_provider_clock=lambda: NOW,
    )
    result = manager.register_manual_provider(
        ManualProviderDraft(
            display_name="Ручная площадка",
            homepage_url="https://example.test",
            endpoint_url="https://discovery.example.test",
        )
    )
    assert result.status is ManualProviderCommandStatus.CREATED
    return manager


def _api_draft(endpoint: str = "https://api.example.test/v1") -> ManualProviderProtocolDraft:
    return ManualProviderProtocolDraft(
        family=ManualProviderProtocolFamily.API,
        endpoint_url=endpoint,
        payload_format=ManualProviderPayloadFormat.JSON,
        authentication_kind=ManualProviderAuthenticationKind.API_KEY,
    )


def test_save_change_clear_projects_honest_non_runnable_lifecycle(tmp_path) -> None:
    manager = _manager(tmp_path)
    original = manager.settings_snapshot().get_manual(MANUAL_ID)

    saved = manager.save_manual_provider_protocol(
        MANUAL_ID,
        _api_draft(),
        expected_updated_at=original.updated_at,
    )
    state = next(item for item in manager.states() if item.provider_id == MANUAL_ID)

    assert saved.status is ManualProviderProtocolCommandStatus.SAVED
    assert saved.error_category is ManualProviderProtocolErrorCategory.NONE
    assert saved.lifecycle is ManualProviderProtocolReadiness.ADAPTER_REQUIRED
    assert state.lifecycle is ManualProviderLifecycle.ADAPTER_REQUIRED
    assert state.status_text == "Протокол выбран — требуется создание адаптера"
    assert state.protocol_configured is True
    assert state.registration_only is True
    assert state.enabled is False
    assert state.runnable is False
    assert state.factory_available is False
    assert state.credential_available is False
    assert state.health_check_available is False
    assert "api.example.test" not in repr(state)

    metadata_update = manager.update_manual_provider(
        MANUAL_ID,
        ManualProviderDraft("Новое имя", "https://example.test"),
    )
    assert metadata_update.status is ManualProviderCommandStatus.UPDATED
    assert manager.manual_protocol_selection(MANUAL_ID) is not None

    selected = manager.settings_snapshot().get_manual(MANUAL_ID)
    changed = manager.save_manual_provider_protocol(
        MANUAL_ID,
        _api_draft("https://next.example.test/v2"),
        expected_updated_at=selected.updated_at,
    )
    assert changed.status is ManualProviderProtocolCommandStatus.CHANGED

    latest = manager.settings_snapshot().get_manual(MANUAL_ID)
    cleared = manager.clear_manual_provider_protocol(
        MANUAL_ID,
        expected_updated_at=latest.updated_at,
    )
    reset = manager.settings_snapshot().get_manual(MANUAL_ID)
    assert cleared.status is ManualProviderProtocolCommandStatus.CLEARED
    assert reset.protocol_selection is None
    assert reset.lifecycle_state is ManualProviderLifecycle.PROTOCOL_REQUIRED


def test_stale_change_is_rejected_without_lost_update_or_endpoint_disclosure(tmp_path) -> None:
    manager = _manager(tmp_path)
    original = manager.settings_snapshot().get_manual(MANUAL_ID)
    manager.save_manual_provider_protocol(
        MANUAL_ID,
        _api_draft(),
        expected_updated_at=original.updated_at,
    )

    stale = manager.save_manual_provider_protocol(
        MANUAL_ID,
        _api_draft("https://stale-secret.example.test/v2"),
        expected_updated_at=original.updated_at,
    )

    assert stale.status is ManualProviderProtocolCommandStatus.STALE
    assert stale.error_category is ManualProviderProtocolErrorCategory.STALE_EDIT
    assert "stale-secret" not in stale.message
    assert manager.manual_protocol_selection(MANUAL_ID).endpoint_url == (
        "https://api.example.test/v1"
    )


def test_invalid_and_builtin_targets_return_safe_typed_results(tmp_path) -> None:
    manager = _manager(tmp_path)
    current = manager.settings_snapshot().get_manual(MANUAL_ID)
    unsafe = ManualProviderProtocolDraft.unvalidated(
        family=ManualProviderProtocolFamily.API,
        endpoint_url="https://user:SECRET@example.test/v1",
        payload_format=ManualProviderPayloadFormat.JSON,
        authentication_kind=ManualProviderAuthenticationKind.NONE,
    )

    rejected = manager.save_manual_provider_protocol(
        MANUAL_ID,
        unsafe,
        expected_updated_at=current.updated_at,
    )
    builtin = manager.save_manual_provider_protocol(
        "eis",
        _api_draft(),
        expected_updated_at=current.updated_at,
    )

    assert rejected.status is ManualProviderProtocolCommandStatus.INVALID_INPUT
    assert "SECRET" not in rejected.message
    assert builtin.status is ManualProviderProtocolCommandStatus.UNSUPPORTED_TARGET
    assert builtin.error_category is ManualProviderProtocolErrorCategory.UNSUPPORTED_TARGET


def test_selected_protocol_never_bypasses_runtime_or_enablement_guards(tmp_path) -> None:
    manager = _manager(tmp_path)
    current = manager.settings_snapshot().get_manual(MANUAL_ID)
    manager.save_manual_provider_protocol(
        MANUAL_ID,
        _api_draft(),
        expected_updated_at=current.updated_at,
    )

    with pytest.raises(ManualProviderExecutionError) as selected:
        manager.assert_runnable_provider_ids((MANUAL_ID,))
    with pytest.raises(ManualProviderExecutionError):
        manager.set_enabled(MANUAL_ID, True)

    assert selected.value.lifecycle is ManualProviderLifecycle.ADAPTER_REQUIRED
    assert manager.enabled_provider_ids() == ("eis", "mos_supplier")
    assert manager.manual_protocol_readiness_gaps(MANUAL_ID) == ("adapter_required",)


def test_selected_protocol_is_rejected_before_runtime_health_and_unified_search(tmp_path) -> None:
    health_calls: list[tuple[str, ...]] = []

    async def health_checker(provider_ids: tuple[str, ...]):
        health_calls.append(provider_ids)
        return {}

    manager = CollectorProviderManager(
        tmp_path,
        environment={},
        health_checker=health_checker,
        manual_provider_id_factory=lambda: MANUAL_ID,
        manual_provider_clock=lambda: NOW,
    )
    manager.register_manual_provider(ManualProviderDraft("Площадка", "https://example.test"))
    current = manager.settings_snapshot().get_manual(MANUAL_ID)
    manager.save_manual_provider_protocol(
        MANUAL_ID,
        _api_draft(),
        expected_updated_at=current.updated_at,
    )
    runtime_calls: list[str] = []

    def runtime_factory():
        runtime_calls.append("runtime")
        raise AssertionError("runtime must not be created")

    session = CollectorRunSession(
        tmp_path,
        runtime_factory=runtime_factory,
        provider_settings_snapshot_factory=manager.settings_snapshot,
    )
    with pytest.raises(ManualProviderExecutionError) as run_error:
        asyncio.run(
            session.run(
                TenderSearchQuery(keywords=("кабель",)),
                provider_ids=(MANUAL_ID,),
            )
        )
    with pytest.raises(ManualProviderExecutionError) as health_error:
        asyncio.run(manager.check_providers((MANUAL_ID,)))

    profile = create_builtin_search_profiles()[0]
    with pytest.raises(UnifiedTenderSearchValidationError, match="адаптера"):
        resolve_unified_tender_search(
            UnifiedTenderSearchRequest(profile_id=profile.id, provider_ids=(MANUAL_ID,)),
            profiles=(profile,),
            provider_states=manager.states(),
        )

    assert run_error.value.lifecycle is ManualProviderLifecycle.ADAPTER_REQUIRED
    assert health_error.value.lifecycle is ManualProviderLifecycle.ADAPTER_REQUIRED
    assert runtime_calls == []
    assert health_calls == []
