"""Static release-pipeline contract tests."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_pyinstaller_spec_collects_certificates_and_version_info() -> None:
    source = (ROOT / "installer" / "corteris_tender_ai.spec").read_text(encoding="utf-8")

    assert 'collect_data_files("certifi")' in source
    assert "version=str(version_info)" in source
    assert '"templates"' in source
    assert "hiddenimports=sorted(hiddenimports)" in source


def test_inno_setup_only_references_one_file_build() -> None:
    source = (ROOT / "installer" / "setup.iss").read_text(encoding="utf-8")

    assert "dist\\CorterisTenderAI\\*" not in source
    assert 'Source: "..\\dist\\{#AppExeName}"' in source
    assert "CorterisTenderAI_Setup_x64" in source


def test_build_script_runs_preflight_tests_and_frozen_self_test() -> None:
    source = (ROOT / "scripts" / "build_exe.ps1").read_text(encoding="utf-8-sig")

    assert "validate_build_environment.py" in source
    assert '"-m", "pytest"' in source
    assert "run_frozen_smoke_test.ps1" in source
    assert "write_build_manifest.py" in source


def test_bootstrap_handles_self_test_before_qt_imports() -> None:
    source = (ROOT / "app" / "bootstrap.py").read_text(encoding="utf-8")

    self_test_index = source.index('if "--self-test" in sys.argv')
    qt_index = source.index("from PySide6.QtWidgets import QApplication")
    assert self_test_index < qt_index


def test_runtime_requirements_include_certifi() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    build_requirements = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")

    assert "certifi>=2024.8" in requirements
    assert "pyinstaller>=6.11,<7" in build_requirements
    assert "pytest>=8,<10" in build_requirements
