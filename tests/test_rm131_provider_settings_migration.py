"""RM-131 deterministic split-v1 migration and rollback contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.tenders.collector.provider_settings import (
    ProviderConfiguration,
    ProviderEnablementRepository,
    ProviderSettingsLoadStatus,
)


def _write_json(path: Path, payload: object) -> bytes:
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    path.write_bytes(data)
    return data


def test_split_v1_uses_general_enablement_before_legacy_commercial(tmp_path) -> None:
    canonical = tmp_path / "collector_provider_settings.json"
    legacy = tmp_path / "commercial_provider_settings.json"
    _write_json(
        canonical,
        {
            "schema_version": 1,
            "providers": {"b2b_center": False, "sber_a": True},
        },
    )
    _write_json(
        legacy,
        {
            "schema_version": 1,
            "providers": {
                "b2b_center": {
                    "enabled": True,
                    "access_confirmed": True,
                    "api_base_url": "https://api.b2b.test/v1/",
                },
                "sber_commercial": {
                    "enabled": False,
                    "access_confirmed": False,
                    "api_base_url": "",
                },
            },
        },
    )
    repository = ProviderEnablementRepository(canonical, legacy_settings_path=legacy)

    result = repository.load_result()

    assert result.status is ProviderSettingsLoadStatus.MIGRATED_SPLIT_V1
    assert result.get("b2b_center").enabled is False
    assert result.get("b2b_center").configuration == ProviderConfiguration(
        access_confirmed=True,
        api_base_url="https://api.b2b.test/v1",
    )
    assert result.get("sber_commercial").enabled is True
    assert any("sber_a" in warning for warning in result.warnings)
    assert any("b2b_center" in warning and "overrides" in warning for warning in result.warnings)


def test_first_split_v1_mutation_backs_up_both_sources_and_is_idempotent(tmp_path) -> None:
    canonical = tmp_path / "collector_provider_settings.json"
    legacy = tmp_path / "commercial_provider_settings.json"
    canonical_bytes = _write_json(
        canonical,
        {"schema_version": 1, "providers": {"eis": True}},
    )
    legacy_bytes = _write_json(
        legacy,
        {
            "schema_version": 1,
            "providers": {
                "b2b_center": {
                    "enabled": True,
                    "access_confirmed": False,
                    "api_base_url": "",
                }
            },
        },
    )
    repository = ProviderEnablementRepository(canonical, legacy_settings_path=legacy)

    repository.set_enabled("mos_supplier", True)

    assert json.loads(canonical.read_text(encoding="utf-8"))["schema_version"] == 2
    assert legacy.read_bytes() == legacy_bytes
    backups = tuple(tmp_path.glob("*.v1-*.bak"))
    assert len(backups) == 2
    assert {item.read_bytes() for item in backups} == {canonical_bytes, legacy_bytes}
    before = {item.name for item in backups}

    repository.set_enabled("eis", False)

    assert {item.name for item in tmp_path.glob("*.v1-*.bak")} == before
    assert repository.load_result().status is ProviderSettingsLoadStatus.CURRENT


def test_atomic_replace_failure_preserves_v1_sources_and_removes_temp(
    tmp_path,
    monkeypatch,
) -> None:
    canonical = tmp_path / "collector_provider_settings.json"
    legacy = tmp_path / "commercial_provider_settings.json"
    canonical_bytes = _write_json(
        canonical,
        {"schema_version": 1, "providers": {"eis": True}},
    )
    legacy_bytes = _write_json(legacy, {"schema_version": 1, "providers": {}})
    repository = ProviderEnablementRepository(canonical, legacy_settings_path=legacy)
    original_replace = Path.replace

    def fail_target_replace(self: Path, target: Path):
        if Path(target) == canonical:
            raise OSError("replace failed")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_target_replace)

    with pytest.raises(OSError, match="replace failed"):
        repository.set_enabled("eis", False)

    assert canonical.read_bytes() == canonical_bytes
    assert legacy.read_bytes() == legacy_bytes
    assert not canonical.with_suffix(canonical.suffix + ".tmp").exists()
