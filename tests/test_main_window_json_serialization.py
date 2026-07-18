"""Static integration test for Decimal-safe analysis rendering."""

from __future__ import annotations

from pathlib import Path


def test_tender_workspace_uses_safe_json_renderer() -> None:
    source = (
        Path(__file__).parents[1] / "app" / "ui" / "pages" / "tender_workspace_page.py"
    ).read_text(encoding="utf-8")

    assert "from app.core.json_serialization import json_dumps" in source
    assert "json_dumps(self.last_report)" in source
    assert "json.dumps(self.last_report" not in source
