"""RM-133 immutable registration-only model and validation contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone

import pytest

from app.tenders.collector.manual_provider_registration import (
    ManualProviderDraft,
    ManualProviderLifecycle,
    ManualProviderRegistration,
)


MANUAL_ID = f"manual_{'a' * 32}"
NOW = datetime(2026, 7, 17, 9, 0, tzinfo=timezone.utc)


def _registration(**changes: object) -> ManualProviderRegistration:
    values: dict[str, object] = {
        "provider_id": MANUAL_ID,
        "display_name": "  Тестовая   площадка  ",
        "homepage_url": "HTTPS://Example.TEST/",
        "endpoint_url": "https://API.Example.TEST:443/v1/",
        "lifecycle_state": ManualProviderLifecycle.PROTOCOL_REQUIRED,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return ManualProviderRegistration(**values)


def test_valid_registration_is_normalized_immutable_and_registration_only() -> None:
    registration = _registration()

    assert registration.provider_id == MANUAL_ID
    assert registration.display_name == "Тестовая площадка"
    assert registration.homepage_url == "https://example.test"
    assert registration.endpoint_url == "https://api.example.test/v1"
    assert registration.lifecycle_state is ManualProviderLifecycle.PROTOCOL_REQUIRED
    assert registration.enabled is False
    assert registration.registration_only is True
    assert registration.created_at.utcoffset() is not None
    assert registration.updated_at.utcoffset() is not None
    with pytest.raises(FrozenInstanceError):
        registration.display_name = "Другое"  # type: ignore[misc]


def test_rename_keeps_stable_identity_and_creation_time() -> None:
    current = _registration()
    changed = replace(
        current,
        display_name="Новое название",
        updated_at=datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc),
    )

    assert changed.provider_id == current.provider_id
    assert changed.created_at == current.created_at
    assert changed.display_name == "Новое название"


@pytest.mark.parametrize(
    "value",
    (
        "",
        "   ",
        "line\nbreak",
        "nul\x00value",
        "spoof\u202evalue",
        "x" * 161,
    ),
)
def test_display_name_rejects_empty_control_bidi_and_oversized_values(value: str) -> None:
    with pytest.raises(ValueError, match="display name"):
        ManualProviderDraft(
            display_name=value,
            homepage_url="https://example.test",
        )


@pytest.mark.parametrize(
    "field,value",
    (
        ("homepage_url", "ftp://example.test"),
        ("homepage_url", "https://user:secret@example.test"),
        ("homepage_url", "https://example.test/path?token=secret"),
        ("endpoint_url", "https://example.test/path#fragment"),
        ("endpoint_url", "https://example.test/%ZZ"),
        ("endpoint_url", "https://example.test/line\r\nbreak"),
        ("endpoint_url", "javascript:alert(1)"),
        ("endpoint_url", "file:///etc/passwd"),
    ),
)
def test_url_metadata_rejects_unsafe_values(field: str, value: str) -> None:
    values = {
        "display_name": "Площадка",
        "homepage_url": "https://example.test",
        "endpoint_url": "",
    }
    values[field] = value

    with pytest.raises(ValueError, match="URL") as captured:
        ManualProviderDraft(**values)

    assert value not in str(captured.value)


def test_safe_repr_and_public_payload_do_not_disclose_private_endpoint() -> None:
    registration = _registration(endpoint_url="http://127.0.0.1/private")

    assert "127.0.0.1" not in repr(registration)
    assert "endpoint" not in registration.public_payload()
    assert not hasattr(registration, "protocol")
    assert not hasattr(registration, "credential")
    assert not hasattr(registration, "adapter")


def test_manual_id_and_timestamps_are_strict() -> None:
    with pytest.raises(ValueError, match="manual provider id"):
        _registration(provider_id="eis")
    with pytest.raises(ValueError, match="timezone"):
        _registration(created_at=datetime(2026, 7, 17, 9, 0))
    with pytest.raises(ValueError, match="timestamp"):
        _registration(
            updated_at=datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
        )
