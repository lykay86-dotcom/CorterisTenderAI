import json

from app.core.config_manager import ConfigManager


def test_creates_default_config(tmp_path):
    path = tmp_path / "settings.json"
    manager = ConfigManager(path)
    assert path.exists()
    assert manager.get("finance.vat_rate") == 22.0
    assert manager.get("ai.provider") == "disabled"


def test_set_and_reload(tmp_path):
    path = tmp_path / "settings.json"
    manager = ConfigManager(path)
    manager.set("finance.profit_percent", 35.0)
    loaded = ConfigManager(path)
    assert loaded.get("finance.profit_percent") == 35.0


def test_deep_merge_keeps_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"finance": {"vat_rate": 20}}), encoding="utf-8")
    manager = ConfigManager(path)
    assert manager.get("finance.vat_rate") == 20
    assert manager.get("finance.profit_percent") == 30.0


def test_snapshot_is_copy(tmp_path):
    manager = ConfigManager(tmp_path / "settings.json")
    snapshot = manager.snapshot()
    snapshot["finance"]["vat_rate"] = 1
    assert manager.get("finance.vat_rate") == 22.0


def test_corrupt_json_is_replaced_with_safe_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"ai": [broken secret=do-not-leak', encoding="utf-8")

    manager = ConfigManager(path)

    assert manager.get("ai.provider") == "disabled"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["ai"]["provider"] == "disabled"
    assert "do-not-leak" not in path.read_text(encoding="utf-8")


def test_non_object_config_is_replaced_with_safe_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[]", encoding="utf-8")

    manager = ConfigManager(path)

    assert manager.get("ai.provider") == "disabled"
