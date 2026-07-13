from pathlib import Path
from app.config.user_settings import UserSettingsStore
from app.estimates.workspace import EstimateRow, totals
from app.services.readiness import check_application


def test_defaults_v13(tmp_path):
    s = UserSettingsStore(tmp_path / "settings.json")
    p = s.load()
    assert p.vat_percent == 22.0 and p.profit_percent == 30.0


def test_estimate_workspace():
    t = totals([EstimateRow("Камера", 2, "шт.", 10000, 30, 22)])
    assert t["cost"] == 20000 and t["gross"] == 31720 and t["profit"] == 6000


def test_readiness(tmp_path):
    files = []
    for n in ["Коммерческое предложение.docx", "Смета.xlsx", "Таблица соответствия.xlsx"]:
        p = tmp_path / n
        p.write_bytes(b"x")
        files.append(p)
    assert check_application(files)["ready"] is True


def test_brand_registry_exists():
    p = Path(__file__).resolve().parents[1] / "data" / "brands_ru.json"
    assert p.exists() and "TRASSIR" in p.read_text(encoding="utf-8")
