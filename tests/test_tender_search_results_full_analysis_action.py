from pathlib import Path


def test_search_results_contains_full_analysis_action() -> None:
    source = Path("app/ui/tender_search_results_dialog.py").read_text(encoding="utf-8")
    assert "full_analysis_requested = Signal(object)" in source
    assert "Скачать документы и провести полный анализ" in source
