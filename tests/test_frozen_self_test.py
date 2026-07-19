"""Tests for the non-network source/frozen smoke test."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.frozen_self_test import run_frozen_self_test
from app.core.path_manager import AppPaths
from app.core.startup import StartupContext


def _context(tmp_path: Path) -> StartupContext:
    bundle = tmp_path / "bundle"
    templates = bundle / "templates" / "company"
    templates.mkdir(parents=True)
    (templates / "sample.docx").write_bytes(b"template")
    icons = bundle / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "fallback.svg").write_text("<svg/>", encoding="utf-8")
    (icons / "manifest.json").write_text(
        json.dumps({"files": ["fallback.svg"]}),
        encoding="utf-8",
    )

    data = tmp_path / "data"
    config = tmp_path / "config"
    logs = tmp_path / "logs"
    cache = tmp_path / "cache"
    paths = AppPaths(
        bundle_dir=bundle,
        project_dir=tmp_path,
        data_dir=data,
        config_dir=config,
        log_dir=logs,
        cache_dir=cache,
        projects_dir=data / "projects",
        backups_dir=data / "backups",
        exports_dir=data / "exports",
        temp_dir=cache / "temp",
        templates_dir=bundle / "templates",
        assets_dir=bundle / "assets",
        catalog_dir=data / "catalog",
        database_file=data / "corteris_tender_ai.db",
    )
    for directory in (
        data,
        config,
        logs,
        cache,
        paths.projects_dir,
        paths.backups_dir,
        paths.exports_dir,
        paths.temp_dir,
        paths.catalog_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return StartupContext(paths=paths, config=None, resources=None)  # type: ignore[arg-type]


def test_self_test_writes_successful_json_report(tmp_path) -> None:
    output = tmp_path / "report.json"

    report = run_frozen_self_test(
        _context(tmp_path),
        output_path=output,
        required_modules=("httpx", "certifi"),
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert report.success
    assert payload["success"] is True
    names = {item["name"] for item in payload["checks"]}
    assert "ssl_certificates" in names
    assert "collector_database" in names
    assert "provider_composition" in names
    assert "safe_archive" in names
    assert "chart_rendering" in names
