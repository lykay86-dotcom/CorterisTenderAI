"""Offscreen renderer, catalog, font, and fixture checks for RM-154."""

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

from scripts.rm154_visual_qa.catalog import VISUAL_CASES, case_by_id
from scripts.rm154_visual_qa.core import normalized_png_sha256, privacy_findings
from scripts.rm154_visual_qa.environment import register_and_fingerprint_fonts
from scripts.rm154_visual_qa.fixtures import build_visual
from scripts.rm154_visual_qa.renderer import capture_case


ROOT = Path(__file__).parents[1]


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_catalog_is_closed_sorted_paired_and_representative() -> None:
    ids = tuple(case.case_id for case in VISUAL_CASES)

    assert ids == tuple(sorted(ids))
    assert len(ids) == len(set(ids)) == 14
    for family in {case_id.rsplit(".", 2)[0] for case_id in ids}:
        assert f"{family}.dark.canonical" in ids
        assert f"{family}.light.canonical" in ids
    assert any("dashboard" in case_id for case_id in ids)
    assert any("tenders" in case_id for case_id in ids)
    assert any("workflow" in case_id for case_id in ids)
    assert any("analytics" in case_id for case_id in ids)
    critical = case_by_id("dialog.participation.critical-stop.dark.canonical")
    assert critical.native_evidence_required


def test_windows_fonts_are_explicitly_registered_and_path_free() -> None:
    _app()
    fonts = register_and_fingerprint_fonts()

    assert tuple(font.file_name for font in fonts) == (
        "segoeui.ttf",
        "seguisb.ttf",
        "segoeuib.ttf",
        "consola.ttf",
    )
    assert all(len(font.sha256) == 64 for font in fonts)
    assert all("\\" not in font.file_name and "/" not in font.file_name for font in fonts)


def test_gallery_capture_is_metadata_free_and_repeatable(tmp_path: Path) -> None:
    _app()
    case = case_by_id("component.gallery.core.dark.canonical")
    first = capture_case(case, root=ROOT, runtime_root=tmp_path / "first")
    second = capture_case(case, root=ROOT, runtime_root=tmp_path / "second")

    assert first.png == second.png
    assert normalized_png_sha256(first.png) == normalized_png_sha256(second.png)
    with Image.open(BytesIO(first.png)) as image:
        image.load()
        assert image.mode == "RGB"
        assert image.size == (1200, 900)
        assert image.info == {}
    assert b"tEXt" not in first.png
    assert b"eXIf" not in first.png
    assert b"iCCP" not in first.png


def test_critical_dialog_capture_uses_only_synthetic_values(tmp_path: Path) -> None:
    _app()
    case = case_by_id("dialog.participation.critical-stop.light.canonical")
    capture = capture_case(case, root=ROOT, runtime_root=tmp_path)

    assert capture.png.startswith(b"\x89PNG\r\n\x1a\n")
    assert not privacy_findings((case.case_id, case.fixture_id, capture.renderer.profile_id))


def test_shell_fixture_freezes_workflow_minute_and_analytics_dates(tmp_path: Path) -> None:
    app = _app()
    workflow = build_visual(
        case_by_id("shell.workflow.empty.dark.canonical"),
        tmp_path / "workflow",
    )
    try:
        window = workflow.widget
        assert window.workflow_page.updated_label.text().endswith("09:00")  # type: ignore[attr-defined]
    finally:
        workflow.dispose(app)

    analytics = build_visual(
        case_by_id("shell.analytics.empty.dark.canonical"),
        tmp_path / "analytics",
    )
    try:
        page = analytics.widget.analytics_page  # type: ignore[attr-defined]
        assert page.start_date.date() == QDate(2026, 6, 21)
        assert page.end_date.date() == QDate(2026, 7, 21)
    finally:
        analytics.dispose(app)
