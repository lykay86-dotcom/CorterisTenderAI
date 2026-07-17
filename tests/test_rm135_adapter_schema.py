"""RM-135 schema-v5 migration, revision and lifecycle contract."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json

from app.tenders.collector.manual_adapter import (
    CanonicalTenderField,
    FieldMappingSpec,
    ManualAdapterDataFormat,
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
from app.tenders.collector.provider_settings import (
    ProviderEnablementRepository,
    ProviderSettingsLoadStatus,
)


MANUAL_ID = f"manual_{'d' * 32}"
NOW = datetime(2026, 7, 17, 16, 0, tzinfo=timezone.utc)


def _registration() -> ManualProviderRegistration:
    selection = create_manual_provider_protocol_selection(
        ManualProviderProtocolDraft(
            family=ManualProviderProtocolFamily.API,
            endpoint_url="https://api.example.test/v1",
            payload_format=ManualProviderPayloadFormat.JSON,
        ),
        timestamp=NOW,
    )
    return ManualProviderRegistration(
        provider_id=MANUAL_ID,
        display_name="Площадка",
        homepage_url="https://example.test",
        lifecycle_state=ManualProviderLifecycle.ADAPTER_REQUIRED,
        protocol_selection=selection,
        created_at=NOW,
        updated_at=NOW,
    )


def _spec():
    return create_manual_adapter_spec(
        provider_id=MANUAL_ID,
        protocol_family=ManualProviderProtocolFamily.API,
        source=SourceRequestSpec(data_format=ManualAdapterDataFormat.JSON),
        record_selector=RecordSelectorSpec(path=("items",)),
        field_mappings=(FieldMappingSpec(CanonicalTenderField.TITLE, ("title",), required=True),),
        revision=1,
        timestamp=NOW,
    )


def test_v4_loads_without_guessing_then_first_adapter_save_creates_v4_backup(tmp_path) -> None:
    path = tmp_path / "collector_provider_settings.json"
    registration = _registration().persisted_payload()
    registration.pop("adapter_spec")
    registration.pop("adapter_spec_history")
    payload = {
        "schema_version": 4,
        "updated_at": NOW.isoformat(),
        "providers": {},
        "configuration": {},
        "manual_registrations": {MANUAL_ID: registration},
    }
    original = json.dumps(payload, ensure_ascii=False, indent=2).encode()
    path.write_bytes(original)
    repository = ProviderEnablementRepository(path)

    loaded = repository.load_result()
    assert loaded.status is ProviderSettingsLoadStatus.MIGRATED_V4
    assert loaded.manual_registrations[0].adapter_spec is None
    assert path.read_bytes() == original

    configured = replace(
        loaded.manual_registrations[0],
        lifecycle_state=ManualProviderLifecycle.CONNECTION_TEST_REQUIRED,
        adapter_spec=_spec(),
    )
    repository.replace_manual_provider_if_current(configured, expected_updated_at=NOW)

    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 6
    backups = tuple(tmp_path.glob("collector_provider_settings.json.v4-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == original
