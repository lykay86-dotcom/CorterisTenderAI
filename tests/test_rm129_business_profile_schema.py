"""RM-129 schema, migration, confirmation, and rollback contract."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path

import pytest

from app.tenders.collector.company_capability import (
    CompanyCapabilityLoadStatus,
    CompanyCapabilityProfile,
    CompanyCapabilityProfileRepository,
    migrate_company_capability_v1,
)


CONFIRMED_AT = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
V2_ONLY_FIELDS = {
    "base_currency",
    "confirmation_version",
    "confirmation_fingerprint",
    "confirmation_source",
}


def _draft(**changes: object) -> CompanyCapabilityProfile:
    values: dict[str, object] = {
        "company_name": "ООО КОРТЕРИС",
        "business_directions": ("видеонаблюдение", "СКУД"),
        "self_install_regions": ("Москва",),
        "licenses": ("МЧС",),
        "installation_crew_count": 2,
        "confirmed_experience": ("Контракт №1",),
        "max_project_amount": Decimal("30000000.0100"),
        "working_capital": Decimal("5000000.50"),
        "max_bid_security": Decimal("400000.00"),
        "max_contract_security": Decimal("800000.00"),
        "bank_guarantee_limit": Decimal("1000000.00"),
        "equipment": ("IP-камера",),
        "brands": ("Trassir",),
        "suppliers": ("Поставщик 1",),
        "minimum_margin_percent": Decimal("20.00"),
        "base_currency": "RUB",
    }
    values.update(changes)
    return CompanyCapabilityProfile(**values)


def _confirmed(**changes: object) -> CompanyCapabilityProfile:
    return _draft(**changes).confirm(
        confirmed_by="Директор",
        confirmed_at=CONFIRMED_AT,
        evidence_note="Проверено по документам компании",
    )


def _v1_payload(**changes: object) -> dict[str, object]:
    profile = _draft(**changes).to_dict()
    for key in V2_ONLY_FIELDS:
        profile.pop(key, None)
    profile.update(
        {
            "confirmed_at": CONFIRMED_AT.isoformat(timespec="seconds"),
            "confirmed_by": "Директор",
            "evidence_note": "Проверено по документам компании",
            "updated_at": "2026-07-12T12:05:00+00:00",
        }
    )
    return {"schema_version": 1, "profile": profile}


def _write(path: Path, payload: object) -> bytes:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    path.write_bytes(rendered)
    return rendered


def test_missing_file_returns_typed_empty_unconfirmed_profile(tmp_path: Path) -> None:
    repository = CompanyCapabilityProfileRepository(tmp_path / "company_capability_profile.json")

    result = repository.load_result()

    assert result.status is CompanyCapabilityLoadStatus.MISSING
    assert result.source_schema_version is None
    assert not result.profile.is_confirmed
    assert result.profile.company_name == ""
    assert result.warnings == ()


def test_v1_load_is_fact_preserving_auditable_and_does_not_rewrite(tmp_path: Path) -> None:
    path = tmp_path / "company_capability_profile.json"
    original = _write(path, _v1_payload())
    before_mtime = path.stat().st_mtime_ns
    repository = CompanyCapabilityProfileRepository(path)

    result = repository.load_result()

    assert result.status is CompanyCapabilityLoadStatus.MIGRATED_V1
    assert result.source_schema_version == 1
    assert result.profile.is_confirmed
    assert result.profile.confirmation_source == "migrated_v1"
    assert result.profile.confirmation_version == 1
    assert len(result.profile.confirmation_fingerprint) == 64
    assert result.profile.base_currency == "RUB"
    assert result.profile.max_project_amount == Decimal("30000000.0100")
    assert result.profile.updated_at == "2026-07-12T12:05:00+00:00"
    assert path.read_bytes() == original
    assert path.stat().st_mtime_ns == before_mtime


def test_pure_v1_migrator_does_not_mutate_input() -> None:
    payload = _v1_payload()
    before = json.loads(json.dumps(payload, ensure_ascii=False))

    migrated = migrate_company_capability_v1(payload)

    assert payload == before
    assert migrated.is_confirmed
    assert migrated.confirmation_source == "migrated_v1"
    assert migrated.max_project_amount == Decimal("30000000.0100")


def test_explicit_save_upgrades_v1_to_current_old_reader_shape(tmp_path: Path) -> None:
    path = tmp_path / "company_capability_profile.json"
    _write(path, _v1_payload())
    repository = CompanyCapabilityProfileRepository(path)
    migrated = repository.load_result().profile

    repository.save(migrated)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["profile"]["company_name"] == "ООО КОРТЕРИС"
    assert payload["profile"]["business_directions"] == ["видеонаблюдение", "СКУД"]
    assert payload["profile"]["max_project_amount"] == "30000000.0100"
    assert payload["profile"]["base_currency"] == "RUB"
    assert payload["profile"]["confirmation_source"] == "migrated_v1"
    assert repository.load_result().status is CompanyCapabilityLoadStatus.CURRENT


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"schema_version": 999, "profile": {}}, CompanyCapabilityLoadStatus.UNSUPPORTED_FUTURE),
        ({"schema_version": 2, "profile": []}, CompanyCapabilityLoadStatus.CORRUPT),
        (["not", "an", "object"], CompanyCapabilityLoadStatus.CORRUPT),
    ],
)
def test_future_and_structurally_corrupt_payloads_fail_closed_without_overwrite(
    tmp_path: Path,
    payload: object,
    status: CompanyCapabilityLoadStatus,
) -> None:
    path = tmp_path / "company_capability_profile.json"
    original = _write(path, payload)
    repository = CompanyCapabilityProfileRepository(path)

    result = repository.load_result()

    assert result.status is status
    assert not result.profile.is_confirmed
    assert result.profile.company_name == ""
    assert result.warnings
    assert path.read_bytes() == original
    with pytest.raises(ValueError):
        repository.save(_confirmed())
    assert path.read_bytes() == original


def test_malformed_json_is_corrupt_and_original_is_preserved(tmp_path: Path) -> None:
    path = tmp_path / "company_capability_profile.json"
    original = b'{"schema_version": 2, "profile": '
    path.write_bytes(original)
    repository = CompanyCapabilityProfileRepository(path)

    result = repository.load_result()

    assert result.status is CompanyCapabilityLoadStatus.CORRUPT
    assert not result.profile.is_confirmed
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_project_amount", 30000000.01),
        ("working_capital", float("inf")),
        ("installation_crew_count", True),
        ("confirmed_at", "2026-07-12T12:00:00"),
        ("base_currency", "UNKNOWN"),
    ],
)
def test_invalid_known_v2_field_returns_corrupt_not_partial_confirmation(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    path = tmp_path / "company_capability_profile.json"
    repository = CompanyCapabilityProfileRepository(path)
    repository.save(_confirmed())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["profile"][field] = value
    _write(path, payload)

    result = repository.load_result()

    assert result.status is CompanyCapabilityLoadStatus.CORRUPT
    assert not result.profile.is_confirmed
    assert result.profile.company_name == ""


def test_v2_round_trip_preserves_decimal_scale_and_normalizes_aware_dates(tmp_path: Path) -> None:
    path = tmp_path / "company_capability_profile.json"
    repository = CompanyCapabilityProfileRepository(path)
    confirmed_at = datetime(2026, 7, 12, 15, 0, tzinfo=timezone(timedelta(hours=3)))
    profile = _draft().confirm(confirmed_by="Директор", confirmed_at=confirmed_at)

    repository.save(profile)
    restored = repository.load_result().profile

    assert restored.max_project_amount == Decimal("30000000.0100")
    assert str(restored.max_project_amount) == "30000000.0100"
    assert restored.confirmed_at == "2026-07-12T12:00:00+00:00"
    assert restored.updated_at.endswith("+00:00")
    assert restored.is_confirmed


def test_confirmation_is_bound_to_facts_but_not_updated_at_or_tuple_order() -> None:
    profile = _confirmed()

    assert profile.is_confirmed
    assert replace(profile, updated_at="2026-07-13T12:00:00+00:00").is_confirmed
    assert replace(
        profile,
        business_directions=tuple(reversed(profile.business_directions)),
    ).is_confirmed
    assert not replace(profile, max_project_amount=Decimal("30000000.02")).is_confirmed
    assert not replace(profile, licenses=("МЧС", "ФСБ")).is_confirmed
    assert not replace(profile, base_currency="USD").is_confirmed


def test_confirmation_rejects_empty_confirmer_and_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="confirmed_by"):
        _draft().confirm(confirmed_by=" ", confirmed_at=CONFIRMED_AT)
    with pytest.raises(ValueError, match="timezone"):
        _draft().confirm(
            confirmed_by="Директор",
            confirmed_at=datetime(2026, 7, 12, 12, 0),
        )


def test_repository_rejects_unconfirmed_or_stale_confirmation(tmp_path: Path) -> None:
    repository = CompanyCapabilityProfileRepository(tmp_path / "company_capability_profile.json")

    with pytest.raises(ValueError):
        repository.save(_draft())
    with pytest.raises(ValueError):
        repository.save(replace(_confirmed(), equipment=("Другое оборудование",)))


def test_atomic_replace_failure_preserves_original_and_cleans_temporary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "company_capability_profile.json"
    repository = CompanyCapabilityProfileRepository(path)
    repository.save(_confirmed())
    original = path.read_bytes()
    replacement = _confirmed(max_project_amount=Decimal("31000000.00"))

    def fail_replace(_self: Path, _target: Path) -> Path:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        repository.save(replacement)

    assert path.read_bytes() == original
    assert not path.with_suffix(path.suffix + ".tmp").exists()
