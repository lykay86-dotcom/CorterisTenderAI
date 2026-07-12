"""Regression tests for direct execution of Moscow API diagnostics."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_mos_diagnostic_adds_project_root_before_app_imports() -> None:
    source = (
        Path(__file__).parents[1]
        / "scripts"
        / "check_mos_supplier_api.py"
    ).read_text(encoding="utf-8")

    bootstrap = (
        "PROJECT_ROOT = Path(__file__).resolve().parents[1]"
    )
    app_import = (
        "from app.tenders.collector.network_runtime import"
    )

    assert bootstrap in source
    assert source.index(bootstrap) < source.index(app_import)


def test_mos_diagnostic_runs_from_scripts_path_without_app_error(
    tmp_path,
) -> None:
    project_root = Path(__file__).parents[1]
    script = project_root / "scripts" / "check_mos_supplier_api.py"

    environment = os.environ.copy()
    environment.pop("CORTERIS_MOS_API_KEY", None)
    environment.pop("CORTERIS_MOS_BEARER_TOKEN", None)

    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
    )

    combined = completed.stdout + completed.stderr
    assert completed.returncode == 2
    assert "Портал поставщиков не настроен" in combined
    assert "No module named 'app'" not in combined
