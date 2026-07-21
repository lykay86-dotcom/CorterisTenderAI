"""RM-133 legacy manual-platform separation and byte-preservation guards."""

from __future__ import annotations

import json

from app.config.user_settings import PlatformConnection, UserPreferences, UserSettingsStore
from app.tenders.collector.manual_provider_registration import ManualProviderDraft
from app.tenders.collector.provider_control import CollectorProviderManager
from app.ui.pages.tender_workspace_page import (
    LEGACY_PLATFORM_COMPATIBILITY_NOTICE,
    LEGACY_PLATFORM_CREDENTIAL_NOTICE,
    LEGACY_PLATFORM_PROVIDER_ACTION_TEXT,
)


class _CredentialTripwire:
    def __getattr__(self, name: str):
        raise AssertionError(f"legacy/keyring access is forbidden: {name}")


def test_legacy_platform_is_not_automatically_imported_or_rewritten(tmp_path) -> None:
    user_settings_path = tmp_path / "user_settings.json"
    store = UserSettingsStore(user_settings_path)
    store.save(
        UserPreferences(
            platforms=[
                PlatformConnection(
                    name="Legacy source",
                    protocol="FTP",
                    endpoint="ftp://legacy.example.test/feed",
                    username="legacy-user",
                    enabled=True,
                )
            ]
        )
    )
    original = user_settings_path.read_bytes()

    manager = CollectorProviderManager(
        tmp_path,
        credential_service=_CredentialTripwire(),
        manual_provider_id_factory=lambda: f"manual_{'2' * 32}",
    )

    assert manager.settings_snapshot().manual_registrations == ()
    assert user_settings_path.read_bytes() == original

    manager.register_manual_provider(
        ManualProviderDraft("Canonical source", "https://example.test")
    )

    assert user_settings_path.read_bytes() == original
    assert (
        json.loads(user_settings_path.read_text(encoding="utf-8"))["platforms"][0]["protocol"]
        == "FTP"
    )


def test_legacy_handoff_copy_remains_explicit_and_credential_safe() -> None:
    assert "совместим" in LEGACY_PLATFORM_COMPATIBILITY_NOTICE.casefold()
    assert "не используются" in LEGACY_PLATFORM_COMPATIBILITY_NOTICE.casefold()
    assert "не управляет credentials" in LEGACY_PLATFORM_CREDENTIAL_NOTICE.casefold()
    assert "каноническ" in LEGACY_PLATFORM_PROVIDER_ACTION_TEXT.casefold()
