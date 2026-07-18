"""Non-network smoke test for source and frozen application builds."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime
import importlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
from typing import Iterable, Sequence
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from app.core.path_manager import PathManager
from app.core.ssl_support import build_ssl_context, describe_ssl_context
from app.core.startup import StartupContext
from app.core.version import APP_NAME, APP_VERSION


@dataclass(frozen=True, slots=True)
class FrozenSelfTestCheck:
    name: str
    ok: bool
    message: str
    details: dict[str, object]


@dataclass(frozen=True, slots=True)
class FrozenSelfTestReport:
    application: str
    version: str
    created_at: str
    frozen: bool
    executable: str
    success: bool
    checks: tuple[FrozenSelfTestCheck, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "application": self.application,
            "version": self.version,
            "created_at": self.created_at,
            "frozen": self.frozen,
            "executable": self.executable,
            "success": self.success,
            "checks": [asdict(item) for item in self.checks],
        }


DEFAULT_REQUIRED_MODULES = (
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
)


def run_frozen_self_test(
    context: StartupContext,
    *,
    output_path: str | Path | None = None,
    required_modules: Sequence[str] = DEFAULT_REQUIRED_MODULES,
) -> FrozenSelfTestReport:
    """Run deterministic checks without external HTTP requests."""

    checks: list[FrozenSelfTestCheck] = []
    checks.append(_check_imports(required_modules))
    checks.append(_check_resources(context))
    checks.append(_check_writable_directories(context))
    checks.append(_check_ssl())
    checks.append(_check_collector_database(context))
    checks.append(_check_provider_composition(context))
    checks.append(_check_safe_archive(context))

    report = FrozenSelfTestReport(
        application=APP_NAME,
        version=APP_VERSION,
        created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        frozen=PathManager.is_frozen(),
        executable=str(Path(sys.executable).resolve()),
        success=all(item.ok for item in checks),
        checks=tuple(checks),
    )

    target = (
        Path(output_path).expanduser().resolve()
        if output_path is not None
        else context.paths.data_dir / "diagnostics" / "frozen_self_test.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            report.to_payload(),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report


def run_frozen_self_test_from_argv(
    context: StartupContext,
    argv: Sequence[str] | None = None,
) -> int:
    """Parse self-test arguments, write a report and return an exit code."""

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--self-test-output", default="")
    namespace, _ = parser.parse_known_args(list(argv if argv is not None else sys.argv[1:]))
    if not namespace.self_test:
        raise ValueError("--self-test is required")

    report = run_frozen_self_test(
        context,
        output_path=namespace.self_test_output or None,
    )
    return 0 if report.success else 1


def _check_imports(modules: Iterable[str]) -> FrozenSelfTestCheck:
    missing: list[str] = []
    loaded: list[str] = []
    for module_name in modules:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            missing.append(f"{module_name}: {type(exc).__name__}: {exc}")
        else:
            loaded.append(module_name)
    return FrozenSelfTestCheck(
        name="python_dependencies",
        ok=not missing,
        message=(
            "Обязательные зависимости импортируются."
            if not missing
            else "Не удалось импортировать часть зависимостей."
        ),
        details={"loaded": loaded, "missing": missing},
    )


def _check_resources(context: StartupContext) -> FrozenSelfTestCheck:
    templates = context.paths.templates_dir
    icon_manifest = context.paths.assets_dir / "icons" / "manifest.json"
    icon_files: list[str] = []
    if icon_manifest.is_file():
        try:
            manifest_payload = json.loads(icon_manifest.read_text(encoding="utf-8"))
            icon_files = [str(item) for item in manifest_payload.get("files", ())]
        except (OSError, TypeError, ValueError):
            icon_files = []
    template_files = (
        sorted(str(item.relative_to(templates)) for item in templates.rglob("*") if item.is_file())
        if templates.is_dir()
        else []
    )
    icons_ok = bool(icon_files) and all(
        (icon_manifest.parent / filename).is_file() for filename in icon_files
    )
    ok = bool(template_files) and icons_ok
    return FrozenSelfTestCheck(
        name="bundled_resources",
        ok=ok,
        message=(
            "Шаблоны приложения доступны." if ok else "Каталог шаблонов отсутствует или пуст."
        ),
        details={
            "bundle_dir": str(context.paths.bundle_dir),
            "templates_dir": str(templates),
            "template_count": len(template_files),
            "assets_exists": context.paths.assets_dir.is_dir(),
            "icon_manifest": str(icon_manifest),
            "icon_count": len(icon_files),
            "icons_ok": icons_ok,
        },
    )


def _check_writable_directories(
    context: StartupContext,
) -> FrozenSelfTestCheck:
    marker = context.paths.temp_dir / f"self_test_{uuid4().hex}.tmp"
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("Corteris Tender AI", encoding="utf-8")
        value = marker.read_text(encoding="utf-8")
        ok = value == "Corteris Tender AI"
        message = "Пользовательские каталоги доступны для записи."
        details: dict[str, object] = {
            "data_dir": str(context.paths.data_dir),
            "config_dir": str(context.paths.config_dir),
            "log_dir": str(context.paths.log_dir),
            "temp_dir": str(context.paths.temp_dir),
        }
    except Exception as exc:
        ok = False
        message = "Проверка записи завершилась ошибкой."
        details = {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        marker.unlink(missing_ok=True)
    return FrozenSelfTestCheck(
        name="writable_directories",
        ok=ok,
        message=message,
        details=details,
    )


def _check_ssl() -> FrozenSelfTestCheck:
    try:
        ssl_context = build_ssl_context()
        info = describe_ssl_context(ssl_context)
        ok = info.verification_enabled and info.ca_certificates > 0
        return FrozenSelfTestCheck(
            name="ssl_certificates",
            ok=ok,
            message=(
                "TLS-проверка включена и корневые сертификаты загружены."
                if ok
                else "Не удалось подтвердить доступность корневых сертификатов."
            ),
            details=asdict(info),
        )
    except Exception as exc:
        return FrozenSelfTestCheck(
            name="ssl_certificates",
            ok=False,
            message="Создание проверяемого TLS-контекста завершилось ошибкой.",
            details={"error": f"{type(exc).__name__}: {exc}"},
        )


def _check_collector_database(
    context: StartupContext,
) -> FrozenSelfTestCheck:
    test_root = context.paths.temp_dir / f"collector_db_{uuid4().hex}"
    database = test_root / "tender_registry.sqlite3"
    try:
        from app.tenders.collector.schema import (
            COLLECTOR_SCHEMA_VERSION,
        )
        from app.tenders.collector.store import (
            CollectorStateRepository,
        )

        repository = CollectorStateRepository(database)
        repository.initialize()
        with sqlite3.connect(database) as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        tables = {str(row[0]) for row in rows}
        required = {
            "tender_records",
            "collector_runs",
            "collector_checkpoints",
            "collector_tender_scores",
        }
        missing = sorted(required - tables)
        ok = not missing
        return FrozenSelfTestCheck(
            name="collector_database",
            ok=ok,
            message=(
                "SQLite-схема Collector создаётся."
                if ok
                else "В тестовой базе отсутствуют таблицы Collector."
            ),
            details={
                "schema_version": COLLECTOR_SCHEMA_VERSION,
                "table_count": len(tables),
                "missing_tables": missing,
            },
        )
    except Exception as exc:
        return FrozenSelfTestCheck(
            name="collector_database",
            ok=False,
            message="Инициализация тестовой базы завершилась ошибкой.",
            details={"error": f"{type(exc).__name__}: {exc}"},
        )
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def _check_provider_composition(
    context: StartupContext,
) -> FrozenSelfTestCheck:
    async def scenario() -> tuple[str, ...]:
        from app.tenders.collector.async_provider_factory import (
            create_default_async_providers,
        )
        from app.tenders.collector.network_runtime import (
            create_collector_network_runtime,
        )
        from app.tenders.collector.provider_settings import (
            ProviderEnablementRepository,
        )

        runtime = create_collector_network_runtime()
        try:
            settings = ProviderEnablementRepository(
                context.paths.temp_dir / f"provider_settings_{uuid4().hex}.json"
            )
            providers = create_default_async_providers(
                runtime,
                provider_settings_repository=settings,
                include_disabled=True,
            )
            return tuple(provider.descriptor.id for provider in providers)
        finally:
            await runtime.aclose()

    try:
        provider_ids = asyncio.run(scenario())
        required = {"eis", "mos_supplier"}
        missing = sorted(required - set(provider_ids))
        return FrozenSelfTestCheck(
            name="provider_composition",
            ok=not missing,
            message=(
                "Провайдеры Collector создаются без сетевых запросов."
                if not missing
                else "Не найдены обязательные провайдеры."
            ),
            details={
                "provider_ids": list(provider_ids),
                "missing_provider_ids": missing,
            },
        )
    except Exception as exc:
        return FrozenSelfTestCheck(
            name="provider_composition",
            ok=False,
            message="Создание провайдеров завершилось ошибкой.",
            details={"error": f"{type(exc).__name__}: {exc}"},
        )


def _check_safe_archive(
    context: StartupContext,
) -> FrozenSelfTestCheck:
    test_root = context.paths.temp_dir / f"archive_{uuid4().hex}"
    archive_path = test_root / "sample.zip"
    destination = test_root / "extracted"
    try:
        from app.tenders.safe_archive import SafeArchiveExtractor

        test_root.mkdir(parents=True, exist_ok=True)
        with ZipFile(
            archive_path,
            "w",
            compression=ZIP_DEFLATED,
        ) as archive:
            archive.writestr("documents/readme.txt", "test")
            archive.writestr("../blocked.txt", "blocked")
        result = SafeArchiveExtractor().extract_many(
            (archive_path,),
            destination,
        )
        ok = result.extracted_count == 1 and result.blocked_count == 1
        return FrozenSelfTestCheck(
            name="safe_archive",
            ok=ok,
            message=(
                "Безопасная распаковка работает."
                if ok
                else "Результат проверки безопасной распаковки некорректен."
            ),
            details={
                "extracted_count": result.extracted_count,
                "blocked_count": result.blocked_count,
            },
        )
    except Exception as exc:
        return FrozenSelfTestCheck(
            name="safe_archive",
            ok=False,
            message="Проверка архивов завершилась ошибкой.",
            details={"error": f"{type(exc).__name__}: {exc}"},
        )
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


__all__ = [
    "DEFAULT_REQUIRED_MODULES",
    "FrozenSelfTestCheck",
    "FrozenSelfTestReport",
    "run_frozen_self_test",
    "run_frozen_self_test_from_argv",
]
