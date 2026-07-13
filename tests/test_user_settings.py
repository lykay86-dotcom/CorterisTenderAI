from pathlib import Path
from app.config.user_settings import UserSettingsStore, UserPreferences, PlatformConnection


def test_user_settings_roundtrip(tmp_path: Path):
    store = UserSettingsStore(tmp_path / "settings.json")
    prefs = UserPreferences(
        profit_percent=35,
        licenses=["Лицензия МЧС"],
        platforms=[PlatformConnection("ЕИС", "RSS", "https://example.test/rss")],
    )
    store.save(prefs)
    loaded = store.load()
    assert loaded.profit_percent == 35
    assert loaded.licenses == ["Лицензия МЧС"]
    assert loaded.platforms[0].protocol == "RSS"


def test_template_import(tmp_path: Path):
    store = UserSettingsStore(tmp_path / "settings.json")
    template_dir = tmp_path / "templates"
    store.save(UserPreferences(template_dir=str(template_dir)))
    source = tmp_path / "source.docx"
    source.write_bytes(b"test")
    target = store.import_template(source, "01.docx")
    assert target.read_bytes() == b"test"
