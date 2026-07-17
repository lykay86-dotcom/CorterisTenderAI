"""RM-134 schema-v4 roundtrip, migration and optimistic concurrency."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from app.tenders.collector.manual_provider_protocol import (
    ManualProviderAuthenticationKind,
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
    ProviderSettingsStaleWriteError,
)


MANUAL_ID = f"manual_{'7' * 32}"
NOW = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)


def _registration(*, selected: bool) -> ManualProviderRegistration:
    selection = None
    lifecycle = ManualProviderLifecycle.PROTOCOL_REQUIRED
    if selected:
        selection = create_manual_provider_protocol_selection(
            ManualProviderProtocolDraft(
                family=ManualProviderProtocolFamily.API,
                endpoint_url="https://api.example.test/v1",
                payload_format=ManualProviderPayloadFormat.JSON,
                authentication_kind=ManualProviderAuthenticationKind.API_KEY,
            ),
            timestamp=NOW,
        )
        lifecycle = ManualProviderLifecycle.ADAPTER_REQUIRED
    return ManualProviderRegistration(
        provider_id=MANUAL_ID,
        display_name="Площадка",
        homepage_url="https://example.test",
        endpoint_url="https://discovery.example.test",
        lifecycle_state=lifecycle,
        protocol_selection=selection,
        created_at=NOW,
        updated_at=NOW,
    )


def test_schema_v4_roundtrip_preserves_selection_but_public_payload_hides_endpoint(
    tmp_path,
) -> None:
    path = tmp_path / "collector_provider_settings.json"
    repository = ProviderEnablementRepository(path)
    repository.register_manual_provider(_registration(selected=True))

    raw = json.loads(path.read_text(encoding="utf-8"))
    loaded = repository.load_result()
    selection = loaded.manual_registrations[0].protocol_selection

    assert raw["schema_version"] == 4
    assert selection is not None
    assert selection.family is ManualProviderProtocolFamily.API
    assert selection.endpoint_url == "https://api.example.test/v1"
    assert "endpoint_url" not in loaded.manual_registrations[0].public_payload()
    assert "api.example.test" not in repr(loaded.manual_registrations[0])


def test_v3_loads_without_mutation_then_first_write_creates_one_backup(tmp_path) -> None:
    path = tmp_path / "collector_provider_settings.json"
    v3_registration = _registration(selected=False).persisted_payload()
    v3_registration.pop("protocol_selection")
    payload = {
        "schema_version": 3,
        "updated_at": "2026-07-17T09:00:00+00:00",
        "providers": {},
        "configuration": {},
        "manual_registrations": {MANUAL_ID: v3_registration},
    }
    original = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    path.write_bytes(original)
    repository = ProviderEnablementRepository(path)

    assert repository.load_result().status is ProviderSettingsLoadStatus.MIGRATED_V3
    assert path.read_bytes() == original

    current = repository.load_result().manual_registrations[0]
    changed = replace(current, display_name="Новое имя", updated_at=NOW + timedelta(minutes=1))
    repository.update_manual_provider(changed)
    backups = tuple(tmp_path.glob("collector_provider_settings.json.v3-*.bak"))

    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 4
    assert len(backups) == 1
    assert backups[0].read_bytes() == original


def test_compare_and_replace_rejects_stale_writer_without_changing_bytes(tmp_path) -> None:
    path = tmp_path / "collector_provider_settings.json"
    repository = ProviderEnablementRepository(path)
    current = _registration(selected=False)
    repository.register_manual_provider(current)
    newer = replace(current, display_name="Новое имя", updated_at=NOW + timedelta(minutes=2))
    repository.replace_manual_provider_if_current(newer, expected_updated_at=NOW)
    stable = path.read_bytes()

    stale = replace(current, display_name="Устаревшее имя", updated_at=NOW + timedelta(minutes=3))
    with pytest.raises(ProviderSettingsStaleWriteError):
        repository.replace_manual_provider_if_current(stale, expected_updated_at=NOW)

    assert path.read_bytes() == stable
    assert repository.load_result().manual_registrations[0].display_name == "Новое имя"


def test_schema_v4_rejects_unknown_protocol_fields_fail_closed(tmp_path) -> None:
    path = tmp_path / "collector_provider_settings.json"
    registration = _registration(selected=True).persisted_payload()
    assert isinstance(registration["protocol_selection"], dict)
    registration["protocol_selection"]["script"] = "run()"
    path.write_text(
        json.dumps(
            {
                "schema_version": 4,
                "updated_at": "2026-07-17T09:00:00+00:00",
                "providers": {},
                "configuration": {},
                "manual_registrations": {MANUAL_ID: registration},
            }
        ),
        encoding="utf-8",
    )

    assert (
        ProviderEnablementRepository(path).load_result().status
        is ProviderSettingsLoadStatus.CORRUPT
    )
