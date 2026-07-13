# ruff: noqa: E402
"""Preflight validation before PyInstaller builds Corteris Tender AI."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from importlib import import_module, metadata
import json
from pathlib import Path
import platform
import shutil
import struct
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.ssl_support import build_ssl_context, describe_ssl_context
from app.tenders.collector.async_provider_factory import (
    create_default_async_providers,
)
from app.tenders.collector.network_runtime import (
    create_collector_network_runtime,
)
from app.tenders.collector.store import CollectorStateRepository


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    message: str
    details: dict[str, object]


REQUIRED_PATHS = (
    "app/main.py",
    "app/bootstrap.py",
    "templates",
    "requirements.txt",
    "requirements-build.txt",
    "installer/corteris_tender_ai.spec",
    "installer/version_info.txt",
    "installer/setup.iss",
)

REQUIRED_IMPORTS = (
    "PySide6",
    "httpx",
    "certifi",
    "sqlalchemy",
    "pydantic",
    "docx",
    "openpyxl",
    "pypdf",
    "PIL",
    "keyring",
    "cryptography",
    "py7zr",
    "rarfile",
    "PyInstaller",
    "pytest",
)

DISTRIBUTIONS = (
    "PySide6",
    "httpx",
    "httpcore",
    "certifi",
    "SQLAlchemy",
    "pydantic",
    "keyring",
    "cryptography",
    "py7zr",
    "rarfile",
    "pyinstaller",
    "pytest",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON report path.",
    )
    parser.add_argument(
        "--allow-non-windows",
        action="store_true",
        help="Used by CI tests; production Windows build should omit it.",
    )
    args = parser.parse_args(argv)

    checks = [
        _check_platform(args.allow_non_windows),
        _check_paths(),
        _check_imports(),
        _check_ssl(),
        _check_collector_database(),
        _check_provider_factory(),
    ]
    success = all(item.ok for item in checks)
    report = {
        "success": success,
        "python": sys.version,
        "platform": platform.platform(),
        "architecture_bits": struct.calcsize("P") * 8,
        "project_root": str(PROJECT_ROOT),
        "versions": _versions(),
        "checks": [asdict(item) for item in checks],
    }

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output is not None:
        target = args.output.expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if success else 1


def _check_platform(allow_non_windows: bool) -> CheckResult:
    version_ok = sys.version_info[:2] in {(3, 12), (3, 13)}
    bits_ok = struct.calcsize("P") * 8 == 64
    windows_ok = sys.platform == "win32" or allow_non_windows
    ok = version_ok and bits_ok and windows_ok
    return CheckResult(
        "platform",
        ok,
        (
            "Python and platform are suitable for the build."
            if ok
            else "Build requires Windows x64 and Python 3.12 or 3.13."
        ),
        {
            "python": platform.python_version(),
            "bits": struct.calcsize("P") * 8,
            "system": platform.system(),
            "allow_non_windows": allow_non_windows,
        },
    )


def _check_paths() -> CheckResult:
    missing = [relative for relative in REQUIRED_PATHS if not (PROJECT_ROOT / relative).exists()]
    return CheckResult(
        "project_structure",
        not missing,
        (
            "Required build paths are present."
            if not missing
            else "Required build paths are missing."
        ),
        {"missing": missing},
    )


def _check_imports() -> CheckResult:
    failures: list[str] = []
    loaded: list[str] = []
    for module_name in REQUIRED_IMPORTS:
        try:
            import_module(module_name)
        except Exception as exc:
            failures.append(f"{module_name}: {type(exc).__name__}: {exc}")
        else:
            loaded.append(module_name)
    return CheckResult(
        "dependencies",
        not failures,
        (
            "All build/runtime dependencies import successfully."
            if not failures
            else "Some build/runtime dependencies cannot be imported."
        ),
        {"loaded": loaded, "failures": failures},
    )


def _check_ssl() -> CheckResult:
    try:
        info = describe_ssl_context(build_ssl_context())
        ok = info.verification_enabled and info.ca_certificates > 0
        return CheckResult(
            "ssl",
            ok,
            (
                "TLS verification and CA roots are available."
                if ok
                else "TLS verification or CA roots are unavailable."
            ),
            asdict(info),
        )
    except Exception as exc:
        return CheckResult(
            "ssl",
            False,
            "TLS context creation failed.",
            {"error": f"{type(exc).__name__}: {exc}"},
        )


def _check_collector_database() -> CheckResult:
    root = Path(tempfile.mkdtemp(prefix="corteris_build_db_"))
    try:
        repository = CollectorStateRepository(root / "tender_registry.sqlite3")
        repository.initialize()
        with repository._connect() as connection:
            score_table = connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table'
                  AND name='collector_tender_scores'
                """
            ).fetchone()
        ok = score_table is not None
        return CheckResult(
            "collector_database",
            ok,
            ("Collector schema initializes." if ok else "Collector score table was not created."),
            {"database": str(repository.path)},
        )
    except Exception as exc:
        return CheckResult(
            "collector_database",
            False,
            "Collector schema initialization failed.",
            {"error": f"{type(exc).__name__}: {exc}"},
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _check_provider_factory() -> CheckResult:
    async def scenario() -> tuple[str, ...]:
        runtime = create_collector_network_runtime()
        try:
            providers = create_default_async_providers(
                runtime,
                include_disabled=True,
            )
            return tuple(provider.descriptor.id for provider in providers)
        finally:
            await runtime.aclose()

    try:
        providers = asyncio.run(scenario())
        missing = sorted({"eis", "mos_supplier"} - set(providers))
        return CheckResult(
            "provider_factory",
            not missing,
            (
                "Collector providers compose without network I/O."
                if not missing
                else "Required Collector providers are missing."
            ),
            {"providers": list(providers), "missing": missing},
        )
    except Exception as exc:
        return CheckResult(
            "provider_factory",
            False,
            "Provider composition failed.",
            {"error": f"{type(exc).__name__}: {exc}"},
        )


def _versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for name in DISTRIBUTIONS:
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = "not installed"
    return result


if __name__ == "__main__":
    raise SystemExit(main())
