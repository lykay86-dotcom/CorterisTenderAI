"""Run the PRE-RM-156 Collector P9 diagnostic without external network access."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from typing import Any

import httpx

PATCH_ROOT = Path(__file__).resolve().parents[1]
if str(PATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(PATCH_ROOT))

from app.tenders.collector.async_provider_factory import (  # noqa: E402
    create_default_async_providers,
)
from app.tenders.collector.network_runtime import (  # noqa: E402
    create_collector_network_runtime,
)
from app.tenders.collector.provider_definitions import (  # noqa: E402
    canonical_provider_definitions,
)
from app.tenders.collector.schema import CollectorSchemaMigrator  # noqa: E402
from app.tenders.providers.eis import EisHtmlParser  # noqa: E402
from app.tenders.providers.eis_async import AsyncEisTenderProvider  # noqa: E402
from app.tenders.providers.mos_supplier_api import (  # noqa: E402
    AsyncMosSupplierTenderProvider,
)
from app.tenders.providers.mos_supplier_parser import MosSupplierApiParser  # noqa: E402


_READINESS: dict[str, tuple[str, str]] = {
    "eis": (
        "live_verification_not_approved",
        "docs/PRE_RM156_COLLECTOR_P4_EIS_VALIDATION.md",
    ),
    "mos_supplier": (
        "credential_and_live_verification_required",
        "docs/PRE_RM156_COLLECTOR_P4_MOS_SUPPLIER_VALIDATION.md",
    ),
    "zakaz_rf": (
        "machine_contract_required",
        "docs/PRE_RM156_COLLECTOR_P6_ZAKAZ_RF_ACCESS_AUDIT.md",
    ),
    "roseltorg": (
        "machine_contract_required",
        "docs/PRE_RM156_COLLECTOR_P6_ROSELTORG_ACCESS_AUDIT.md",
    ),
    "rad": (
        "written_automation_permission_required",
        "docs/PRE_RM156_COLLECTOR_P6_RAD_ACCESS_AUDIT.md",
    ),
    "tek_torg": (
        "contract_fixtures_and_rate_rules_required",
        "docs/PRE_RM156_COLLECTOR_P6_TEK_TORG_ACCESS_AUDIT.md",
    ),
    "ets_nep": (
        "identity_reaudit_required",
        "docs/PRE_RM156_COLLECTOR_P6_ETS_NEP_ACCESS_AUDIT.md",
    ),
    "sber_a": (
        "machine_contract_required",
        "docs/PRE_RM156_COLLECTOR_P6_SBER_A_ACCESS_AUDIT.md",
    ),
    "rts_tender": (
        "machine_contract_required",
        "docs/PRE_RM156_COLLECTOR_P6_RTS_TENDER_ACCESS_AUDIT.md",
    ),
    "gazprombank": (
        "published_feed_unavailable",
        "docs/PRE_RM156_COLLECTOR_P6_GAZPROMBANK_ACCESS_AUDIT.md",
    ),
    "b2b_center": (
        "contract_and_permission_gated",
        "docs/PRE_RM156_COLLECTOR_P7_B2B_CENTER_ACCESS_AUDIT.md",
    ),
    "fabrikant": (
        "published_api_scope_mismatch",
        "docs/PRE_RM156_COLLECTOR_P7_FABRIKANT_ACCESS_AUDIT.md",
    ),
    "otc": (
        "public_html_without_machine_contract",
        "docs/PRE_RM156_COLLECTOR_P7_OTC_ACCESS_AUDIT.md",
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reference_samples(project_root: Path) -> list[dict[str, object]]:
    eis_fixture = project_root / "tests" / "fixtures" / "eis" / "search_44_current.html"
    mos_fixture = (
        project_root / "tests" / "fixtures" / "mos_supplier_search_documented_contract.json"
    )
    eis_result = EisHtmlParser(base_url="https://zakupki.gov.ru/").parse_search(
        eis_fixture.read_text(encoding="utf-8")
    )
    mos_result = MosSupplierApiParser().parse_search(
        json.loads(mos_fixture.read_text(encoding="utf-8"))
    )
    return [
        {
            "provider_id": "eis",
            "status": "passed",
            "item_count": len(eis_result.items),
            "fixture": eis_fixture.relative_to(project_root).as_posix(),
            "fixture_sha256": _sha256(eis_fixture),
            "contract_version": AsyncEisTenderProvider.contract_version,
            "parser_version": AsyncEisTenderProvider.parser_version,
        },
        {
            "provider_id": "mos_supplier",
            "status": "passed",
            "item_count": len(mos_result.items),
            "fixture": mos_fixture.relative_to(project_root).as_posix(),
            "fixture_sha256": _sha256(mos_fixture),
            "contract_version": AsyncMosSupplierTenderProvider.contract_version,
            "parser_version": AsyncMosSupplierTenderProvider.parser_version,
        },
    ]


def _migration_backup_restore_drill() -> dict[str, object]:
    with TemporaryDirectory(prefix="pre-rm156-p9-") as raw_directory:
        root = Path(raw_directory)
        source = root / "registry.sqlite3"
        with closing(sqlite3.connect(source)) as connection:
            connection.executescript(
                """
                CREATE TABLE tender_registry_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT INTO tender_registry_meta(key, value)
                VALUES('collector_schema_version', '15');
                CREATE TABLE p9_restore_sentinel (
                    value TEXT NOT NULL
                );
                INSERT INTO p9_restore_sentinel(value)
                VALUES('preserved');
                """
            )
            connection.commit()
            inventory = CollectorSchemaMigrator().inspect(connection)
            assert inventory.current_version == 15
            assert inventory.target_version == 16
            CollectorSchemaMigrator().migrate(connection)
            connection.commit()

        backups = tuple((root / "backups").glob("collector-v15-to-v16-*.sqlite3"))
        if len(backups) != 1:
            raise RuntimeError("P9 migration drill did not create exactly one backup")
        backup = backups[0]
        with closing(sqlite3.connect(backup)) as connection:
            backup_integrity = connection.execute("PRAGMA integrity_check").fetchone()
            backup_version = int(
                connection.execute(
                    "SELECT value FROM tender_registry_meta WHERE key='collector_schema_version'"
                ).fetchone()[0]
            )
        restored = CollectorSchemaMigrator.restore_verified_backup(
            backup,
            root / "restored.sqlite3",
        )
        with closing(sqlite3.connect(restored)) as connection:
            restore_integrity = connection.execute("PRAGMA integrity_check").fetchone()
            restored_version = int(
                connection.execute(
                    "SELECT value FROM tender_registry_meta WHERE key='collector_schema_version'"
                ).fetchone()[0]
            )
            restored_sentinel = connection.execute(
                "SELECT value FROM p9_restore_sentinel"
            ).fetchone()[0]
        with closing(sqlite3.connect(source)) as connection:
            migrated_version = int(
                connection.execute(
                    "SELECT value FROM tender_registry_meta WHERE key='collector_schema_version'"
                ).fetchone()[0]
            )
            source_sentinel = connection.execute(
                "SELECT value FROM p9_restore_sentinel"
            ).fetchone()[0]
        temporary_files = sum(
            1 for path in root.rglob("*") if path.is_file() and path.suffix in {".tmp", ".restore"}
        )
        passed = (
            backup_integrity is not None
            and str(backup_integrity[0]).casefold() == "ok"
            and restore_integrity is not None
            and str(restore_integrity[0]).casefold() == "ok"
            and backup_version == 15
            and restored_version == 15
            and migrated_version == 16
            and restored_sentinel == "preserved"
            and source_sentinel == "preserved"
            and temporary_files == 0
        )
        return {
            "source_schema": 15,
            "target_schema": 16,
            "backup_verified": (
                backup_integrity is not None
                and str(backup_integrity[0]).casefold() == "ok"
                and backup_version == 15
            ),
            "restore_verified": (
                restore_integrity is not None
                and str(restore_integrity[0]).casefold() == "ok"
                and restored_sentinel == "preserved"
            ),
            "restored_schema": restored_version,
            "source_unchanged": source_sentinel == "preserved",
            "temporary_files": temporary_files,
            "passed": passed,
        }


def _factory_provider_ids() -> tuple[tuple[str, ...], int]:
    network_calls = 0

    async def reject_network(request: httpx.Request) -> httpx.Response:
        nonlocal network_calls
        network_calls += 1
        raise AssertionError(f"P9 offline diagnostic attempted network: {request.url.host}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(reject_network))
    runtime = create_collector_network_runtime(client=client)
    try:
        providers = create_default_async_providers(
            runtime,
            include_commercial_catalog=True,
            include_disabled=True,
            environment={},
        )
        return tuple(item.descriptor.id for item in providers), network_calls
    finally:
        asyncio.run(runtime.aclose())


def build_offline_report(*, project_root: str | Path = PATCH_ROOT) -> dict[str, Any]:
    """Compose accepted P9 evidence without credentials or external requests."""

    root = Path(project_root).expanduser().resolve()
    descriptors = canonical_provider_definitions()
    provider_ids = tuple(item.id for item in descriptors)
    factory_ids, network_calls = _factory_provider_ids()
    if factory_ids != provider_ids:
        raise RuntimeError("P9 factory projection does not match canonical provider catalog")
    missing_evidence = tuple(
        evidence for _, evidence in _READINESS.values() if not (root / evidence).is_file()
    )
    if missing_evidence:
        raise RuntimeError("P9 readiness evidence is missing: " + ", ".join(missing_evidence))
    providers = [
        {
            "provider_id": descriptor.id,
            "readiness": "blocked_external",
            "reason_code": _READINESS[descriptor.id][0],
            "evidence": _READINESS[descriptor.id][1],
            "working": False,
        }
        for descriptor in descriptors
    ]
    samples = _reference_samples(root)
    drill = _migration_backup_restore_drill()
    passed = (
        len(providers) == 13
        and network_calls == 0
        and all(item["readiness"] == "blocked_external" for item in providers)
        and all(item["status"] == "passed" for item in samples)
        and drill["passed"] is True
    )
    return {
        "schema_version": 1,
        "catalog_count": len(providers),
        "network_calls": network_calls,
        "providers": providers,
        "samples": samples,
        "migration_backup_restore": drill,
        "passed": passed,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default=str(PATCH_ROOT),
        help="CorterisTenderAI project root containing approved offline fixtures.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional JSON output path. Standard output is always emitted.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = build_offline_report(project_root=args.project_root)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(output)
    print(rendered, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
