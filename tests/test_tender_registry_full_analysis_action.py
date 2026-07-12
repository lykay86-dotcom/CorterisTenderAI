from pathlib import Path


def test_registry_contains_full_analysis_action() -> None:
    source = Path("app/ui/tender_registry_dialog.py").read_text(encoding="utf-8")
    assert "full_analysis_requested = Signal(str)" in source
    assert "Скачать документы и провести полный анализ" in source
