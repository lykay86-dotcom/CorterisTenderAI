"""RM-131 non-secret settings contract retained by current schema v3."""

from __future__ import annotations

from datetime import datetime
import json

import pytest

from app.tenders.collector.provider_settings import (
    ProviderConfiguration,
    ProviderEnablementRepository,
    ProviderSettingsLoadStatus,
    ProviderSettingsMutationError,
)


def test_missing_catalog_is_typed_and_does_not_write(tmp_path) -> None:
    path = tmp_path / "collector_provider_settings.json"
    repository = ProviderEnablementRepository(path)

    result = repository.load_result()

    assert result.status is ProviderSettingsLoadStatus.MISSING
    assert result.records == ()
    assert not path.exists()


def test_current_schema_roundtrips_only_allowed_non_secret_fields(tmp_path) -> None:
    path = tmp_path / "collector_provider_settings.json"
    repository = ProviderEnablementRepository(path)

    repository.set_enabled("b2b_center", True)
    repository.set_configuration(
        "b2b_center",
        ProviderConfiguration(
            access_confirmed=True,
            api_base_url="https://api.example.test/v1/",
        ),
    )

    result = repository.load_result()
    record = result.get("b2b_center")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert result.status is ProviderSettingsLoadStatus.CURRENT
    assert record.enabled is True
    assert record.configuration == ProviderConfiguration(
        access_confirmed=True,
        api_base_url="https://api.example.test/v1",
    )
    assert payload["schema_version"] == ProviderEnablementRepository.SCHEMA_VERSION == 7
    assert payload["providers"] == {"b2b_center": True}
    assert payload["configuration"] == {
        "b2b_center": {
            "access_confirmed": True,
            "api_base_url": "https://api.example.test/v1",
        }
    }
    assert payload["manual_registrations"] == {}
    assert datetime.fromisoformat(payload["updated_at"]).utcoffset() is not None


@pytest.mark.parametrize(
    "value",
    (
        "ftp://api.example.test",
        "https://user:secret@api.example.test",
        "https://api.example.test/path?token=secret",
        "https://api.example.test/path#secret",
        "not a url",
    ),
)
def test_configuration_rejects_unsafe_endpoint(value: str) -> None:
    with pytest.raises(ValueError, match="HTTP"):
        ProviderConfiguration(api_base_url=value)


@pytest.mark.parametrize(
    ("payload", "status"),
    (
        ({"schema_version": 99, "providers": {}}, ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE),
        (
            {"schema_version": 2, "providers": [], "configuration": {}},
            ProviderSettingsLoadStatus.CORRUPT,
        ),
        (
            {"schema_version": 2, "providers": {}, "updated_at": "naive"},
            ProviderSettingsLoadStatus.CORRUPT,
        ),
    ),
)
def test_future_and_corrupt_payloads_are_typed_and_byte_preserved(
    tmp_path,
    payload: dict[str, object],
    status: ProviderSettingsLoadStatus,
) -> None:
    path = tmp_path / "collector_provider_settings.json"
    original = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    path.write_bytes(original)
    repository = ProviderEnablementRepository(path)

    result = repository.load_result()

    assert result.status is status
    assert path.read_bytes() == original
    with pytest.raises(ProviderSettingsMutationError):
        repository.set_enabled("eis", False)
    assert path.read_bytes() == original
