"""RM-133 manual-registration persistence on the current canonical schema."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from app.tenders.collector.manual_provider_registration import (
    ManualProviderLifecycle,
    ManualProviderRegistration,
)
from app.tenders.collector.provider_settings import (
    ProviderEnablementRepository,
    ProviderSettingsLoadStatus,
    ProviderSettingsMutationError,
)


def _registration(identifier: str = f"manual_{'b' * 32}") -> ManualProviderRegistration:
    now = datetime(2026, 7, 17, 9, 30, tzinfo=timezone.utc)
    return ManualProviderRegistration(
        provider_id=identifier,
        display_name="Новая площадка",
        homepage_url="https://example.test",
        endpoint_url="https://api.example.test/v1",
        lifecycle_state=ManualProviderLifecycle.PROTOCOL_REQUIRED,
        created_at=now,
        updated_at=now,
    )


def _v2_payload() -> dict[str, object]:
    return {
        "schema_version": 2,
        "updated_at": "2026-07-17T06:00:00+00:00",
        "providers": {"eis": False, "b2b_center": True},
        "configuration": {
            "b2b_center": {
                "access_confirmed": True,
                "api_base_url": "https://api.b2b.test/v1",
            }
        },
    }


def test_v2_loads_in_memory_and_first_manual_mutation_writes_current_with_backup(tmp_path) -> None:
    path = tmp_path / "collector_provider_settings.json"
    original = json.dumps(_v2_payload(), ensure_ascii=False, indent=2).encode("utf-8")
    path.write_bytes(original)
    repository = ProviderEnablementRepository(path)

    loaded = repository.load_result()

    assert loaded.status is ProviderSettingsLoadStatus.MIGRATED_V2
    assert loaded.manual_registrations == ()
    assert path.read_bytes() == original

    repository.register_manual_provider(_registration())
    payload = json.loads(path.read_text(encoding="utf-8"))
    backups = tuple(tmp_path.glob("collector_provider_settings.json.v2-*.bak"))

    assert payload["schema_version"] == 4
    assert payload["providers"] == {"b2b_center": True, "eis": False}
    assert payload["configuration"] == _v2_payload()["configuration"]
    assert tuple(payload["manual_registrations"]) == (_registration().provider_id,)
    assert len(backups) == 1
    assert backups[0].read_bytes() == original


def test_current_roundtrip_is_deterministic_and_does_not_repeat_backup(tmp_path) -> None:
    path = tmp_path / "collector_provider_settings.json"
    repository = ProviderEnablementRepository(path)
    first = _registration(f"manual_{'c' * 32}")
    now = datetime(2026, 7, 17, 9, 30, tzinfo=timezone.utc)
    second = ManualProviderRegistration(
        provider_id=f"manual_{'a' * 32}",
        display_name="Другая площадка",
        homepage_url="https://other.example.test",
        endpoint_url="https://api.other.example.test/v1",
        lifecycle_state=ManualProviderLifecycle.PROTOCOL_REQUIRED,
        created_at=now,
        updated_at=now,
    )

    repository.register_manual_provider(first)
    repository.register_manual_provider(second)
    first_bytes = path.read_bytes()
    loaded = repository.load_result()

    assert loaded.status is ProviderSettingsLoadStatus.CURRENT
    assert tuple(item.provider_id for item in loaded.manual_registrations) == (
        second.provider_id,
        first.provider_id,
    )
    assert json.loads(first_bytes)["schema_version"] == 4
    assert not tuple(tmp_path.glob("collector_provider_settings.json.v3-*.bak"))


@pytest.mark.parametrize(
    ("payload", "status"),
    (
        ({"schema_version": 99, "providers": {}}, ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE),
        (
            {
                "schema_version": 3,
                "updated_at": "2026-07-17T06:00:00+00:00",
                "providers": {},
                "configuration": {},
                "manual_registrations": {"eis": {}},
            },
            ProviderSettingsLoadStatus.CORRUPT,
        ),
    ),
)
def test_corrupt_and_future_payloads_block_mutation_and_preserve_bytes(
    tmp_path,
    payload: dict[str, object],
    status: ProviderSettingsLoadStatus,
) -> None:
    path = tmp_path / "collector_provider_settings.json"
    original = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    path.write_bytes(original)
    repository = ProviderEnablementRepository(path)

    assert repository.load_result().status is status
    with pytest.raises(ProviderSettingsMutationError):
        repository.register_manual_provider(_registration())
    assert path.read_bytes() == original


def test_replace_failure_preserves_v2_and_removes_temporary_file(tmp_path, monkeypatch) -> None:
    path = tmp_path / "collector_provider_settings.json"
    original = json.dumps(_v2_payload(), ensure_ascii=False).encode("utf-8")
    path.write_bytes(original)
    repository = ProviderEnablementRepository(path)
    original_replace = Path.replace

    def fail_target_replace(source: Path, target: Path):
        if source.name.endswith(".tmp") and target == path:
            raise OSError("RM133_PRIVATE_PATH_SENTINEL")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_target_replace)

    with pytest.raises(OSError):
        repository.register_manual_provider(_registration())

    assert path.read_bytes() == original
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_duplicate_or_validation_failure_leaves_current_bytes_unchanged(tmp_path) -> None:
    path = tmp_path / "collector_provider_settings.json"
    repository = ProviderEnablementRepository(path)
    repository.register_manual_provider(_registration())
    original = path.read_bytes()

    with pytest.raises(ValueError):
        repository.register_manual_provider(_registration(f"manual_{'d' * 32}"))

    assert path.read_bytes() == original
