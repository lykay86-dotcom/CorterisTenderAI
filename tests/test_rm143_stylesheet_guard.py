"""Expected deterministic RM-143 stylesheet/migration guard."""

from __future__ import annotations

from pathlib import Path

from scripts.check_design_system import audit_design_system


ROOT = Path(__file__).parents[1]


def test_design_system_guard_covers_every_registered_site_and_raw_colour() -> None:
    report = audit_design_system(ROOT)

    assert report.ok, report.violations
    assert report.matrix_version == "rm143-style-matrix-v1"
    assert report.matrix_entry_count == 45
    assert report.unregistered_stylesheet_sites == ()
    assert report.raw_color_literals == ()
    assert report.broad_exceptions == ()


def test_matrix_has_exact_metadata_not_directory_globs() -> None:
    source = (ROOT / "docs" / "RM-143_COMPONENT_MIGRATION_MATRIX.md").read_text(encoding="utf-8")

    assert source.count("| DS-143-") >= 49
    assert "| `app/ui/**` |" not in source
    assert "45 of 45" in source
