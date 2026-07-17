"""RM-135 factory, application command, revision and admission coverage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.tenders.collector.async_provider_factory import build_manual_async_provider
from app.tenders.collector.manual_adapter import (
    AdapterCompileStatus,
    CanonicalTenderField,
    FieldMappingSpec,
    ManualAdapterCommandStatus,
    ManualAdapterDataFormat,
    ManualAdapterDependencies,
    RecordSelectorSpec,
    SourceRequestSpec,
    create_manual_adapter_spec,
)
from app.tenders.collector.manual_provider_protocol import (
    ManualProviderPayloadFormat,
    ManualProviderProtocolDraft,
    ManualProviderProtocolFamily,
    create_manual_provider_protocol_selection,
)
from app.tenders.collector.manual_provider_registration import (
    ManualProviderLifecycle,
    ManualProviderRegistration,
)
from app.tenders.collector.provider_control import CollectorProviderManager
from app.tenders.collector.provider_settings import ProviderEnablementRepository


PROVIDER_ID = f"manual_{'e' * 32}"
NOW = datetime(2026, 7, 17, 17, 0, tzinfo=timezone.utc)


class _ForbiddenDependency:
    def __getattribute__(self, name):
        raise AssertionError(f"dependency accessed during compile: {name}")


def _registration() -> ManualProviderRegistration:
    protocol = create_manual_provider_protocol_selection(
        ManualProviderProtocolDraft(
            family=ManualProviderProtocolFamily.API,
            endpoint_url="https://api.example.test/v1",
            payload_format=ManualProviderPayloadFormat.JSON,
        ),
        timestamp=NOW,
    )
    return ManualProviderRegistration(
        provider_id=PROVIDER_ID,
        display_name="Площадка",
        homepage_url="https://example.test",
        lifecycle_state=ManualProviderLifecycle.ADAPTER_REQUIRED,
        protocol_selection=protocol,
        created_at=NOW,
        updated_at=NOW,
    )


def _spec(revision: int, *, source_field: str = "title"):
    timestamp = NOW + timedelta(minutes=revision)
    return create_manual_adapter_spec(
        provider_id=PROVIDER_ID,
        protocol_family=ManualProviderProtocolFamily.API,
        source=SourceRequestSpec(ManualAdapterDataFormat.JSON),
        record_selector=RecordSelectorSpec(("items",)),
        field_mappings=(
            FieldMappingSpec(
                CanonicalTenderField.TITLE,
                (source_field,),
                required=True,
            ),
        ),
        revision=revision,
        timestamp=timestamp,
        created_at=NOW + timedelta(minutes=1),
    )


def test_existing_factory_boundary_builds_scoped_adapter_without_dependency_access() -> None:
    registration = _registration()
    dependencies = ManualAdapterDependencies(
        transport=_ForbiddenDependency(),
        credential_resolver=_ForbiddenDependency(),
    )

    first = build_manual_async_provider(registration, _spec(1), dependencies=dependencies)
    second = build_manual_async_provider(registration, _spec(1), dependencies=dependencies)

    assert first.status is AdapterCompileStatus.VALID
    assert second.status is AdapterCompileStatus.VALID
    assert first.adapter is not second.adapter
    assert first.adapter is not None
    assert first.adapter.descriptor.id == PROVIDER_ID
    assert first.adapter.spec_revision == 1
    assert first.adapter.validate_configuration() == ("connection_test_required",)


def test_manager_save_noop_revision_rollback_and_admission_are_separate(tmp_path) -> None:
    repository = ProviderEnablementRepository(tmp_path / "collector_provider_settings.json")
    repository.register_manual_provider(_registration())
    manager = CollectorProviderManager(
        tmp_path,
        enablement_repository=repository,
        manual_provider_clock=lambda: NOW + timedelta(hours=1),
    )

    saved = manager.save_manual_adapter_spec(
        PROVIDER_ID,
        _spec(1),
        expected_updated_at=NOW,
    )
    current = manager.settings_snapshot().get_manual(PROVIDER_ID)
    stable_bytes = repository.path.read_bytes()
    noop = manager.save_manual_adapter_spec(
        PROVIDER_ID,
        _spec(2),
        expected_updated_at=current.updated_at,
    )

    assert saved.status is ManualAdapterCommandStatus.SAVED
    assert current.lifecycle_state is ManualProviderLifecycle.CONNECTION_TEST_REQUIRED
    assert noop.status is ManualAdapterCommandStatus.UNCHANGED
    assert repository.path.read_bytes() == stable_bytes

    changed = manager.save_manual_adapter_spec(
        PROVIDER_ID,
        _spec(2, source_field="name"),
        expected_updated_at=current.updated_at,
    )
    changed_registration = manager.settings_snapshot().get_manual(PROVIDER_ID)
    rolled_back = manager.rollback_manual_adapter_spec(
        PROVIDER_ID,
        expected_updated_at=changed_registration.updated_at,
        history_revision=1,
    )
    final = manager.settings_snapshot().get_manual(PROVIDER_ID)
    state = next(item for item in manager.states() if item.provider_id == PROVIDER_ID)

    assert changed.status is ManualAdapterCommandStatus.SAVED
    assert rolled_back.status is ManualAdapterCommandStatus.ROLLED_BACK
    assert final.adapter_spec is not None
    assert final.adapter_spec.revision == 3
    assert final.adapter_spec.fingerprint == _spec(1).fingerprint
    assert state.adapter_compiled is True
    assert state.factory_available is True
    assert state.runnable is False
    assert state.enabled is False
    assert state.health_check_available is True

    cleared = manager.clear_manual_adapter_spec(
        PROVIDER_ID,
        expected_updated_at=final.updated_at,
    )
    cleared_registration = manager.settings_snapshot().get_manual(PROVIDER_ID)
    resaved = manager.save_manual_adapter_spec(
        PROVIDER_ID,
        _spec(4, source_field="restored_title"),
        expected_updated_at=cleared_registration.updated_at,
    )

    assert cleared.status is ManualAdapterCommandStatus.CLEARED
    assert cleared_registration.next_adapter_revision == 4
    assert resaved.status is ManualAdapterCommandStatus.SAVED
    assert manager.settings_snapshot().get_manual(PROVIDER_ID).adapter_spec.revision == 4


def test_stale_adapter_save_is_rejected_before_noop(tmp_path) -> None:
    repository = ProviderEnablementRepository(tmp_path / "collector_provider_settings.json")
    repository.register_manual_provider(_registration())
    manager = CollectorProviderManager(
        tmp_path,
        enablement_repository=repository,
        manual_provider_clock=lambda: NOW + timedelta(hours=1),
    )
    manager.save_manual_adapter_spec(PROVIDER_ID, _spec(1), expected_updated_at=NOW)
    stable = repository.path.read_bytes()

    result = manager.save_manual_adapter_spec(
        PROVIDER_ID,
        _spec(2),
        expected_updated_at=NOW,
    )

    assert result.status is ManualAdapterCommandStatus.STALE
    assert repository.path.read_bytes() == stable
