"""Static integration tests for Safe Mode bootstrap wiring."""

from __future__ import annotations

from pathlib import Path


def test_bootstrap_contains_launch_guard_and_safe_mode() -> None:
    source = (Path(__file__).parents[1] / "app" / "bootstrap.py").read_text(encoding="utf-8")

    assert "LaunchGuardService" in source
    assert '"--safe-mode" in sys.argv' in source
    assert "SafeModeDialog" in source
    assert "launch_guard.mark_crash" in source
    assert "launch_guard.mark_clean_exit" in source
