from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_commercial_diagnostic_runs_from_another_directory(tmp_path) -> None:
    project_root = Path(__file__).parents[1]
    script = project_root / "scripts" / "check_commercial_providers.py"
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith("CORTERIS_B2B_"):
            environment.pop(key, None)

    completed = subprocess.run(
        [sys.executable, str(script), "--json"],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert completed.returncode == 0
    assert '"provider_id": "b2b_center"' in completed.stdout
    assert '"working": false' in completed.stdout
    assert "No module named 'app'" not in completed.stderr
