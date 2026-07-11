"""Static check for search timeout covering EIS retries."""

from __future__ import annotations

from pathlib import Path


def test_runtime_default_timeout_covers_eis_retry_budget() -> None:
    source = (
        Path(__file__).parents[1]
        / "app"
        / "tenders"
        / "search_runtime.py"
    ).read_text(encoding="utf-8")

    assert "timeout_seconds: float = 60.0" in source
