"""Expected-red contracts for PRE-RM-156 Collector P9 stabilization."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from app.tenders.collector import provider_control
from app.tenders.collector.provider_control import CollectorProviderManager


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_pre_rm156_collector_offline.py"
EXPECTED_PROVIDER_IDS = (
    "eis",
    "mos_supplier",
    "zakaz_rf",
    "roseltorg",
    "rad",
    "tek_torg",
    "ets_nep",
    "sber_a",
    "rts_tender",
    "gazprombank",
    "b2b_center",
    "fabrikant",
    "otc",
)


def _diagnostic_module():
    spec = importlib.util.spec_from_file_location("pre_rm156_p9_offline", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_p9_offline_report_covers_exact_canonical_catalog_without_network() -> None:
    module = _diagnostic_module()

    report = module.build_offline_report(project_root=ROOT)

    assert report["schema_version"] == 1
    assert report["network_calls"] == 0
    assert tuple(item["provider_id"] for item in report["providers"]) == EXPECTED_PROVIDER_IDS
    assert report["catalog_count"] == 13
    assert report["passed"] is True


def test_p9_honest_matrix_never_claims_working_without_live_evidence() -> None:
    module = _diagnostic_module()

    report = module.build_offline_report(project_root=ROOT)
    providers = report["providers"]

    assert {item["readiness"] for item in providers} == {"blocked_external"}
    assert all(item["reason_code"] for item in providers)
    assert all(item["evidence"] for item in providers)
    assert not any(item["working"] for item in providers)


def test_p9_reference_samples_are_parsed_from_approved_offline_fixtures() -> None:
    module = _diagnostic_module()

    samples = module.build_offline_report(project_root=ROOT)["samples"]

    assert tuple(item["provider_id"] for item in samples) == ("eis", "mos_supplier")
    assert all(item["status"] == "passed" for item in samples)
    assert all(item["item_count"] > 0 for item in samples)
    assert all(item["fixture_sha256"] for item in samples)
    assert all(item["contract_version"] for item in samples)
    assert all(item["parser_version"] for item in samples)


def test_p9_report_is_bounded_deterministic_and_secret_free() -> None:
    module = _diagnostic_module()

    first = module.build_offline_report(project_root=ROOT)
    second = module.build_offline_report(project_root=ROOT)
    rendered = json.dumps(first, ensure_ascii=False, sort_keys=True)

    assert first == second
    assert len(rendered.encode("utf-8")) <= 64 * 1024
    assert "api_key" not in rendered.casefold()
    assert "authorization" not in rendered.casefold()
    assert "bearer " not in rendered.casefold()
    assert "cookie" not in rendered.casefold()


def test_p9_migration_backup_restore_drill_is_included() -> None:
    module = _diagnostic_module()

    report = module.build_offline_report(project_root=ROOT)
    drill = report["migration_backup_restore"]

    assert drill == {
        "source_schema": 15,
        "target_schema": 16,
        "backup_verified": True,
        "restore_verified": True,
        "restored_schema": 15,
        "source_unchanged": True,
        "temporary_files": 0,
        "passed": True,
    }


def test_p9_unexpected_health_exception_is_sanitized(monkeypatch, tmp_path) -> None:
    sentinel = "P9_BEARER_SECRET_SENTINEL"

    class Runtime:
        async def aclose(self) -> None:
            return None

    class Provider:
        descriptor = SimpleNamespace(id="eis")

        async def check_health(self):
            raise RuntimeError(
                f"Authorization: Bearer {sentinel} https://example.test/check?api_key=private"
            )

    monkeypatch.setattr(
        provider_control,
        "create_collector_network_runtime",
        lambda: Runtime(),
    )
    monkeypatch.setattr(
        provider_control,
        "create_default_async_providers",
        lambda *_args, **_kwargs: (Provider(),),
    )
    manager = CollectorProviderManager(tmp_path, environment={})

    result = asyncio.run(manager._check_real(("eis",)))["eis"]
    rendered = json.dumps(
        {
            "message": result.message,
            "provider_id": result.provider_id,
            "status": result.status.value,
        },
        ensure_ascii=False,
    )

    assert sentinel not in rendered
    assert "api_key" not in rendered.casefold()
    assert "private" not in rendered.casefold()
    assert result.message == "Проверка источника завершилась внутренней ошибкой."


def test_p9_diagnostic_runs_from_outside_project_and_writes_atomic_json(tmp_path) -> None:
    output = tmp_path / "result" / "p9.json"

    completed = subprocess.run(
        (
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(ROOT),
            "--output",
            str(output),
        ),
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["passed"] is True
    assert json.loads(output.read_text(encoding="utf-8"))["network_calls"] == 0
    assert not output.with_suffix(".json.tmp").exists()
