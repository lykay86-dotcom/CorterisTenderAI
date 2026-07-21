"""Committed RM-154 baseline integrity without rendering noncanonical pixels."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.rm154_visual_qa.catalog import VISUAL_CASES
from scripts.rm154_visual_qa.core import privacy_findings
from scripts.rm154_visual_qa.workflow import (
    APPROVAL_PHRASE,
    REPOSITORY_PNG_BUDGET,
    validate_baseline,
)


ROOT = Path(__file__).parents[1]
BASELINE_ROOT = ROOT / "tests" / "visual" / "baselines" / "rm154-v1"


def test_committed_baseline_is_complete_hashed_reviewed_and_private() -> None:
    manifest = validate_baseline(BASELINE_ROOT)

    assert manifest["source_commit"] == "c95f066357e4614a4fa00e9c83f66ff22286750e"
    assert manifest["renderer_sha256"] == (
        "f1cd92373456028fd9360b3a032ef9b8d5784dc90d00abad4080d404db0dba56"
    )
    assert manifest["review"] == {
        "approval": APPROVAL_PHRASE,
        "reason": "Initial canonical baseline reviewed after fixed-clock visual audit",
        "reviewer": "codex-rm154",
    }
    assert manifest["total_png_bytes"] == 950_716
    assert manifest["total_png_bytes"] < REPOSITORY_PNG_BUDGET
    assert tuple(record["case_id"] for record in manifest["cases"]) == tuple(
        case.case_id for case in VISUAL_CASES
    )
    assert all(len(set(record["repeat_sha256"])) == 1 for record in manifest["cases"])
    serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    assert not privacy_findings((serialized,))


def test_committed_renderer_profile_is_explicit_and_path_free() -> None:
    manifest = validate_baseline(BASELINE_ROOT)
    renderer = manifest["renderer"]

    assert renderer["profile_id"] == "windows-latest-python312"
    assert renderer["python"] == "3.12.10"
    assert renderer["pyside"] == renderer["qt"] == "6.11.1"
    assert renderer["pillow"] == "12.3.0"
    assert renderer["qpa_platform"] == "offscreen"
    assert renderer["qt_style"] == "fusion"
    assert renderer["qt_locale"] == "ru_RU"
    assert renderer["timezone"] == "Europe/Moscow"
    assert tuple(font["file_name"] for font in renderer["fonts"]) == (
        "segoeui.ttf",
        "seguisb.ttf",
        "segoeuib.ttf",
        "consola.ttf",
    )
    assert all(
        "/" not in font["file_name"] and "\\" not in font["file_name"] for font in renderer["fonts"]
    )
