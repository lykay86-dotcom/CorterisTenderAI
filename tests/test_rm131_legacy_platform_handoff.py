"""RM-131 legacy manual-platform compatibility handoff guards."""

from __future__ import annotations

from pathlib import Path

from app.config.user_settings import PlatformConnection, UserPreferences, UserSettingsStore
from app.ui.main_window import (
    LEGACY_PLATFORM_COMPATIBILITY_NOTICE,
    LEGACY_PLATFORM_PROVIDER_ACTION_TEXT,
)


def test_legacy_platform_copy_identifies_manual_compatibility_boundary() -> None:
    assert "совместим" in LEGACY_PLATFORM_COMPATIBILITY_NOTICE.casefold()
    assert "ручн" in LEGACY_PLATFORM_COMPATIBILITY_NOTICE.casefold()
    assert "источник" in LEGACY_PLATFORM_PROVIDER_ACTION_TEXT.casefold()


def test_legacy_platform_store_remains_separate_and_byte_semantics_are_preserved(tmp_path) -> None:
    path = tmp_path / "user_settings.json"
    store = UserSettingsStore(path)
    original = PlatformConnection(
        name="Private RSS",
        protocol="RSS",
        endpoint="https://legacy.example.test/feed",
        username="operator",
    )
    store.save(UserPreferences(platforms=[original]))

    loaded = store.load().platforms

    assert loaded == [original]
    assert not (tmp_path / "collector_provider_settings.json").exists()
    assert not (tmp_path / "commercial_provider_settings.json").exists()


def test_legacy_ui_does_not_construct_collector_settings_owners() -> None:
    source = Path("app/ui/main_window.py").read_text(encoding="utf-8")

    assert "CollectorProviderManager(" not in source
    assert "ProviderEnablementRepository(" not in source
    assert "CommercialProviderSettingsRepository(" not in source
