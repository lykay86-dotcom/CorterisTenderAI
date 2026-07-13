"""Static runtime integration checks for requirement analysis."""

from __future__ import annotations

from pathlib import Path


def test_runtime_builds_requirement_analysis_service() -> None:
    source = (Path(__file__).parents[1] / "app" / "tenders" / "search_runtime.py").read_text(
        encoding="utf-8"
    )

    assert "TenderAnalysisRepository" in source
    assert "TenderRequirementAnalysisService" in source
    assert 'data_path / "tender_analysis.sqlite3"' in source
    assert "requirement_analysis_service" in source


def test_tender_package_exports_analysis_api() -> None:
    source = (Path(__file__).parents[1] / "app" / "tenders" / "__init__.py").read_text(
        encoding="utf-8"
    )

    assert "TenderRequirementsAnalyzer" in source
    assert "TenderRequirementAnalysisService" in source
    assert "RequirementCategory" in source
    assert "AnalysisRiskLevel" in source
