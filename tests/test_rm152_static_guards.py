"""RM-152 machine-readable evidence and accessibility ownership guards."""

from __future__ import annotations

import json
from pathlib import Path

from app.ui.accessibility.native_matrix import validate_native_matrix
from app.ui.theme.colors import DARK_PALETTE, LIGHT_PALETTE
from app.ui.theme.contrast_inventory import build_contrast_inventory
from scripts.check_rm152_accessibility import EVIDENCE_ROOT, validate


def test_contrast_inventory_covers_both_themes_and_has_no_threshold_failures() -> None:
    payload = json.loads((EVIDENCE_ROOT / "RM-152_CONTRAST_PAIRS.json").read_text(encoding="utf-8"))
    expected = [
        *build_contrast_inventory(DARK_PALETTE),
        *build_contrast_inventory(LIGHT_PALETTE),
    ]

    assert payload == {"schema": "rm152-contrast-inventory-v1", "pairs": expected}
    assert {row["theme"] for row in expected} == {"dark", "light"}
    assert not [row for row in expected if row["result"] == "FAIL"]
    assert any(row["result"] == "ADVISORY" for row in expected)


def test_native_matrix_lists_every_required_dev_frozen_and_environment_cell() -> None:
    payload = json.loads((EVIDENCE_ROOT / "RM-152_NATIVE_MATRIX.json").read_text(encoding="utf-8"))
    ids = {cell["id"] for cell in payload["cells"]}
    screen_reader = {
        f"SR-{number:02d}-{target}" for number in range(1, 12) for target in ("DEV", "FROZEN")
    }
    environment = {
        "NATIVE-1366-100-DL",
        "NATIVE-1366-125-DL",
        "NATIVE-1920-100-DL",
        "NATIVE-1920-125-DL",
        "NATIVE-1920-150-DL",
        "NATIVE-2560-150-DL",
        "NATIVE-2560-175-DL",
        "NATIVE-3840-200-DL",
        "NATIVE-HC",
        "NATIVE-MIXED-DPI",
        "NATIVE-FROZEN",
    }

    assert ids == screen_reader | environment
    assert validate_native_matrix(payload) == ()
    cells = {cell["id"]: cell for cell in payload["cells"]}
    partial = cells["NATIVE-1920-100-DL"]
    assert partial["status"] == "FAIL"
    assert partial["observed"] is True
    assert partial["environment"]
    assert partial["evidence"]
    assert all(
        cell["status"] == "NOT_EXECUTED" and cell["observed"] is False
        for cell_id, cell in cells.items()
        if cell_id != "NATIVE-1920-100-DL"
    )


def test_rm152_static_guard_passes_without_promoting_native_matrix() -> None:
    assert validate() == ()
    errors = validate(require_native_complete=True)
    assert len(errors) == 33
    assert all(error.endswith(": incomplete") for error in errors)


def test_evidence_artifacts_do_not_contain_machine_username_or_user_paths() -> None:
    for path in Path(EVIDENCE_ROOT).glob("RM-152_*.json"):
        content = path.read_text(encoding="utf-8").casefold()
        assert "lyka0" not in content
        assert "c:\\users\\" not in content
