from pathlib import Path


def test_import_service_no_longer_uses_extractall() -> None:
    source = Path("app/services/import_service.py").read_text(encoding="utf-8")
    assert "extractall(" not in source
    assert "SafeArchiveExtractor" in source
