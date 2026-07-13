from pathlib import Path
from app.database.session import init_database
from app.repositories.tenders import TenderRepository
from app.tender_analysis.engine import AnalysisEngine
from app.estimates.calculator import EstimateCalculator, EstimateItem, ProfitMode


def test_profit_modes():
    items = [EstimateItem("Работы", 1, "компл.", 100000)]
    markup = EstimateCalculator().calculate(
        items, vat_percent=0, risk_percent=0, profit_percent=30, profit_mode=ProfitMode.MARKUP
    )
    margin = EstimateCalculator().calculate(
        items,
        vat_percent=0,
        risk_percent=0,
        profit_percent=30,
        profit_mode=ProfitMode.REVENUE_MARGIN,
    )
    assert markup["price_without_vat"] == 130000
    assert round(markup["margin_percent"], 2) == 23.08
    assert round(margin["price_without_vat"], 2) == 142857.14
    assert round(margin["margin_percent"], 2) == 30.00


def test_missing_license_is_stop_factor(tmp_path: Path):
    init_database(f"sqlite:///{tmp_path / 'license.db'}")
    repo = TenderRepository()
    t = repo.create(title="Монтаж пожарной сигнализации", nmck=1000000)
    repo.add_document(
        t.id,
        name="ТЗ.txt",
        path="x",
        kind="Техническое задание",
        text="Обязательно наличие действующей лицензии МЧС на монтаж пожарной сигнализации.",
        page_count=1,
    )
    r = AnalysisEngine().analyze(t.id, 800000, 600000)
    assert r["stop_factors"]
    assert r["recommendation"] == "Не соответствует возможностям компании"
