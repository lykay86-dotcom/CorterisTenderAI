"""Global crash capture and privacy-aware local crash reports."""

from __future__ import annotations

import atexit
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import re
import sys
from threading import RLock
import threading
import traceback
from types import TracebackType
from typing import Any, Callable
from uuid import uuid4
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from app.core.version import APP_NAME, APP_VERSION


@dataclass(frozen=True, slots=True)
class CrashReportResult:
    path: Path
    crash_id: str
    created_at: str
    origin: str
    exception_type: str
    exception_message: str
    traceback_text: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class CrashReportInspection:
    path: Path
    valid: bool
    crash_id: str = ""
    created_at: str = ""
    file_count: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CrashReportDetails:
    path: Path
    crash_id: str
    created_at: str
    origin: str
    thread_name: str
    exception_type: str
    exception_message: str
    traceback_text: str
    environment: dict[str, Any]
    size_bytes: int

    @property
    def created_timestamp(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.created_at)
        except (TypeError, ValueError):
            return None


class _CrashRedactor:
    EMAIL = re.compile(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        re.IGNORECASE,
    )
    BEARER = re.compile(
        r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{6,}"
    )
    SECRET = re.compile(
        r"""(?ix)
        \b(
            api[_\-\s]?key
            |access[_\-\s]?token
            |refresh[_\-\s]?token
            |token
            |password
            |passwd
            |secret
            |authorization
        )
        (\s*[:=]\s*)
        (["']?)[^,\s;"']+\3
        """
    )

    def __init__(self, roots: tuple[str | Path, ...]) -> None:
        candidates: list[str] = []
        for root in roots:
            value = str(root).strip()
            if value:
                candidates.append(value)

        for variable in ("USERPROFILE", "HOME", "HOMEPATH"):
            value = os.environ.get(variable, "").strip()
            if value:
                candidates.append(value)

        try:
            candidates.append(str(Path.home()))
        except RuntimeError:
            pass

        variants: list[str] = []
        seen: set[str] = set()
        for value in candidates:
            for variant in {
                value,
                value.replace("\\", "/"),
                value.replace("/", "\\"),
            }:
                identity = variant.casefold()
                if variant and identity not in seen:
                    seen.add(identity)
                    variants.append(variant)

        variants.sort(key=len, reverse=True)
        self._roots = tuple(variants)

    def text(self, value: Any) -> str:
        result = str(value)
        for root in self._roots:
            result = re.sub(
                re.escape(root),
                "<PRIVATE_PATH>",
                result,
                flags=re.IGNORECASE,
            )

        result = self.EMAIL.sub("<EMAIL>", result)
        result = self.BEARER.sub(
            "Bearer <REDACTED>",
            result,
        )
        result = self.SECRET.sub(
            lambda match: (
                f"{match.group(1)}"
                f"{match.group(2)}"
                "<REDACTED>"
            ),
            result,
        )
        return result


class CrashReportService:
    """Create and verify a single-file .ctcrash diagnostic report."""

    FORMAT_NAME = "corteris.crash_report"
    FORMAT_VERSION = 1
    DEFAULT_EXTENSION = ".ctcrash"
    MANIFEST_NAME = "manifest.json"
    REQUIRED_FILES = {
        "crash.json",
        "traceback.txt",
        "environment.json",
        "privacy_report.json",
    }
    MAX_LOG_TAIL_BYTES = 256 * 1024

    def __init__(
        self,
        directory: str | Path,
        *,
        log_file: str | Path | None = None,
    ) -> None:
        self.directory = Path(directory).expanduser()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.log_file = (
            Path(log_file).expanduser()
            if log_file is not None
            else None
        )

    def create_report(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        traceback_object: TracebackType | None,
        *,
        origin: str,
        thread_name: str | None = None,
        created_at: datetime | None = None,
    ) -> CrashReportResult:
        timestamp = created_at or datetime.now()
        crash_id = uuid4().hex
        redactor = _CrashRedactor(
            (
                self.directory,
                self.directory.parent,
                self.log_file or "",
                self.log_file.parent if self.log_file is not None else "",
            )
        )

        raw_traceback = "".join(
            traceback.format_exception(
                exc_type,
                exc_value,
                traceback_object,
            )
        )
        traceback_text = redactor.text(raw_traceback)
        exception_type = (
            f"{exc_type.__module__}.{exc_type.__qualname__}"
        )
        exception_message = redactor.text(exc_value)

        crash_payload = {
            "crash_id": crash_id,
            "created_at": timestamp.isoformat(timespec="seconds"),
            "origin": redactor.text(origin),
            "thread_name": redactor.text(
                thread_name or threading.current_thread().name
            ),
            "thread_ident": threading.get_ident(),
            "exception_type": exception_type,
            "exception_message": exception_message,
            "application": {
                "name": APP_NAME,
                "version": APP_VERSION,
            },
        }
        environment_payload = {
            "python": {
                "version": sys.version,
                "implementation": platform.python_implementation(),
                "executable": redactor.text(sys.executable),
                "frozen": bool(getattr(sys, "frozen", False)),
            },
            "operating_system": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "platform": platform.platform(),
            },
            "arguments": [
                redactor.text(argument)
                for argument in sys.argv
            ],
        }
        privacy_payload = {
            "business_database_included": False,
            "business_documents_included": False,
            "local_variables_included": False,
            "credentials_intentionally_included": False,
            "filesystem_paths_redacted": True,
            "emails_redacted": True,
            "common_secret_values_redacted": True,
            "note": (
                "Отчёт сохраняется только локально. Он содержит тип "
                "исключения, очищенный traceback, техническое окружение "
                "и ограниченный хвост журнала приложения."
            ),
        }

        files: dict[str, bytes] = {
            "crash.json": self._json_bytes(crash_payload),
            "traceback.txt": self._text_bytes(traceback_text),
            "environment.json": self._json_bytes(environment_payload),
            "privacy_report.json": self._json_bytes(privacy_payload),
        }

        log_tail = self._read_log_tail(redactor)
        if log_tail:
            files["recent_log_tail.txt"] = self._text_bytes(log_tail)

        manifest_files = [
            {
                "name": name,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in sorted(files.items())
        ]
        manifest = {
            "format": self.FORMAT_NAME,
            "format_version": self.FORMAT_VERSION,
            "crash_id": crash_id,
            "created_at": timestamp.isoformat(timespec="seconds"),
            "files": manifest_files,
        }

        destination = (
            self.directory
            / (
                "CORTERIS_crash_"
                f"{timestamp:%Y%m%d_%H%M%S}_"
                f"{crash_id[:8]}"
                f"{self.DEFAULT_EXTENSION}"
            )
        )
        temporary = destination.with_suffix(
            destination.suffix + ".tmp"
        )

        try:
            with ZipFile(
                temporary,
                "w",
                compression=ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                archive.writestr(
                    self.MANIFEST_NAME,
                    self._json_bytes(manifest),
                )
                for name, content in sorted(files.items()):
                    archive.writestr(name, content)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

        inspection = self.inspect_report(destination)
        if not inspection.valid:
            destination.unlink(missing_ok=True)
            raise RuntimeError(
                "Crash-report не прошёл проверку: "
                + "; ".join(inspection.errors)
            )

        return CrashReportResult(
            path=destination,
            crash_id=crash_id,
            created_at=timestamp.isoformat(timespec="seconds"),
            origin=origin,
            exception_type=exception_type,
            exception_message=exception_message,
            traceback_text=traceback_text,
            size_bytes=destination.stat().st_size,
        )

    def inspect_report(
        self,
        source: str | Path,
    ) -> CrashReportInspection:
        path = Path(source).expanduser()
        errors: list[str] = []

        if not path.is_file():
            return CrashReportInspection(
                path=path,
                valid=False,
                errors=(f"Файл не найден: {path}",),
            )

        try:
            with ZipFile(path, "r") as archive:
                names = set(archive.namelist())
                if self.MANIFEST_NAME not in names:
                    return CrashReportInspection(
                        path=path,
                        valid=False,
                        errors=("В отчёте отсутствует manifest.json.",),
                    )

                try:
                    manifest = json.loads(
                        archive.read(self.MANIFEST_NAME).decode(
                            "utf-8"
                        )
                    )
                except (
                    KeyError,
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                ) as exc:
                    return CrashReportInspection(
                        path=path,
                        valid=False,
                        errors=(f"Повреждён manifest.json: {exc}",),
                    )

                if not isinstance(manifest, dict):
                    errors.append(
                        "manifest.json должен быть объектом."
                    )
                    manifest = {}

                if manifest.get("format") != self.FORMAT_NAME:
                    errors.append(
                        "Файл не является crash-report CORTERIS."
                    )
                if self._integer(
                    manifest.get("format_version", 0)
                ) != self.FORMAT_VERSION:
                    errors.append(
                        "Неподдерживаемая версия crash-report."
                    )

                listed = manifest.get("files", [])
                if not isinstance(listed, list):
                    errors.append(
                        "Поле files должно быть списком."
                    )
                    listed = []

                listed_names: set[str] = set()
                for item in listed:
                    if not isinstance(item, dict):
                        errors.append(
                            "Некорректная запись файла в manifest.json."
                        )
                        continue

                    name = str(item.get("name", "")).strip()
                    if not name:
                        errors.append(
                            "В manifest.json есть файл без имени."
                        )
                        continue
                    listed_names.add(name)

                    if name not in names:
                        errors.append(
                            f"В архиве отсутствует {name}."
                        )
                        continue

                    content = archive.read(name)
                    expected_size = self._integer(
                        item.get("size_bytes", -1)
                    )
                    if expected_size != len(content):
                        errors.append(
                            f"Размер {name} не совпадает."
                        )

                    expected_hash = str(
                        item.get("sha256", "")
                    ).strip()
                    actual_hash = hashlib.sha256(content).hexdigest()
                    if expected_hash != actual_hash:
                        errors.append(
                            f"Контрольная сумма {name} не совпадает."
                        )

                for name in sorted(
                    self.REQUIRED_FILES - listed_names
                ):
                    errors.append(
                        f"Отсутствует обязательный файл {name}."
                    )

                unexpected = (
                    names
                    - listed_names
                    - {self.MANIFEST_NAME}
                )
                for name in sorted(unexpected):
                    errors.append(
                        f"Файл {name} не описан в manifest.json."
                    )

                return CrashReportInspection(
                    path=path,
                    valid=not errors,
                    crash_id=str(
                        manifest.get("crash_id", "")
                    ),
                    created_at=str(
                        manifest.get("created_at", "")
                    ),
                    file_count=len(listed_names),
                    errors=tuple(errors),
                )
        except (BadZipFile, OSError) as exc:
            return CrashReportInspection(
                path=path,
                valid=False,
                errors=(f"Не удалось прочитать crash-report: {exc}",),
            )

    def read_report(
        self,
        source: str | Path,
    ) -> CrashReportDetails:
        """Read a verified crash report without extracting it to disk."""
        path = Path(source).expanduser()
        inspection = self.inspect_report(path)
        if not inspection.valid:
            raise ValueError(
                "Crash-report не прошёл проверку:\n"
                + "\n".join(
                    f"• {error}"
                    for error in inspection.errors
                )
            )

        try:
            with ZipFile(path, "r") as archive:
                crash_payload = json.loads(
                    archive.read("crash.json").decode("utf-8")
                )
                environment = json.loads(
                    archive.read("environment.json").decode(
                        "utf-8"
                    )
                )
                traceback_text = archive.read(
                    "traceback.txt"
                ).decode("utf-8-sig", errors="replace")
        except (
            BadZipFile,
            OSError,
            KeyError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                f"Не удалось прочитать crash-report: {exc}"
            ) from exc

        if not isinstance(crash_payload, dict):
            raise ValueError("crash.json должен быть объектом.")
        if not isinstance(environment, dict):
            environment = {}

        return CrashReportDetails(
            path=path,
            crash_id=str(
                crash_payload.get(
                    "crash_id",
                    inspection.crash_id,
                )
            ),
            created_at=str(
                crash_payload.get(
                    "created_at",
                    inspection.created_at,
                )
            ),
            origin=str(crash_payload.get("origin", "")),
            thread_name=str(
                crash_payload.get("thread_name", "")
            ),
            exception_type=str(
                crash_payload.get("exception_type", "")
            ),
            exception_message=str(
                crash_payload.get("exception_message", "")
            ),
            traceback_text=traceback_text,
            environment=environment,
            size_bytes=path.stat().st_size,
        )

    def _read_log_tail(
        self,
        redactor: _CrashRedactor,
    ) -> str:
        path = self.log_file
        if path is None or not path.is_file():
            return ""

        try:
            with path.open("rb") as handle:
                handle.seek(0, 2)
                size = handle.tell()
                handle.seek(
                    max(0, size - self.MAX_LOG_TAIL_BYTES)
                )
                raw = handle.read(self.MAX_LOG_TAIL_BYTES)
        except OSError:
            return ""

        return redactor.text(
            raw.decode("utf-8", errors="replace")
        )

    @staticmethod
    def _json_bytes(payload: Any) -> bytes:
        return json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")

    @staticmethod
    def _text_bytes(value: str) -> bytes:
        return value.encode("utf-8-sig")

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


CrashReportCallback = Callable[[CrashReportResult], None]


class GlobalCrashHandler:
    """Install sys/thread/unraisable hooks and persist every uncaught crash."""

    def __init__(
        self,
        service: CrashReportService,
        *,
        report_callback: CrashReportCallback | None = None,
        chain_original: bool = True,
    ) -> None:
        self.service = service
        self.report_callback = report_callback
        self.chain_original = chain_original
        self._lock = RLock()
        self._handling = False
        self._installed = False
        self._original_sys_hook = sys.excepthook
        self._original_thread_hook = getattr(
            threading,
            "excepthook",
            None,
        )
        self._original_unraisable_hook = getattr(
            sys,
            "unraisablehook",
            None,
        )

    @property
    def is_installed(self) -> bool:
        return self._installed

    def set_report_callback(
        self,
        callback: CrashReportCallback | None,
    ) -> None:
        self.report_callback = callback

    def install(self) -> None:
        if self._installed:
            return

        self._original_sys_hook = sys.excepthook
        self._original_thread_hook = getattr(
            threading,
            "excepthook",
            None,
        )
        self._original_unraisable_hook = getattr(
            sys,
            "unraisablehook",
            None,
        )

        sys.excepthook = self._sys_hook
        if hasattr(threading, "excepthook"):
            threading.excepthook = self._thread_hook
        if hasattr(sys, "unraisablehook"):
            sys.unraisablehook = self._unraisable_hook

        self._installed = True
        atexit.register(self.uninstall)

    def uninstall(self) -> None:
        if not self._installed:
            return

        if sys.excepthook == self._sys_hook:
            sys.excepthook = self._original_sys_hook
        if (
            hasattr(threading, "excepthook")
            and threading.excepthook == self._thread_hook
            and self._original_thread_hook is not None
        ):
            threading.excepthook = self._original_thread_hook
        if (
            hasattr(sys, "unraisablehook")
            and sys.unraisablehook == self._unraisable_hook
            and self._original_unraisable_hook is not None
        ):
            sys.unraisablehook = self._original_unraisable_hook

        self._installed = False

    def capture_exception(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        traceback_object: TracebackType | None,
        *,
        origin: str,
        thread_name: str | None = None,
        notify: bool = True,
    ) -> CrashReportResult | None:
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            return None

        with self._lock:
            if self._handling:
                return None
            self._handling = True

        try:
            result = self.service.create_report(
                exc_type,
                exc_value,
                traceback_object,
                origin=origin,
                thread_name=thread_name,
            )
            logging.getLogger(__name__).critical(
                "Необработанная ошибка сохранена: %s",
                result.path,
                exc_info=(
                    exc_type,
                    exc_value,
                    traceback_object,
                ),
            )

            if notify and self.report_callback is not None:
                try:
                    self.report_callback(result)
                except Exception:
                    logging.getLogger(__name__).exception(
                        "Не удалось показать уведомление о crash-report"
                    )
            return result
        except Exception:
            logging.getLogger(__name__).exception(
                "Не удалось создать crash-report"
            )
            return None
        finally:
            with self._lock:
                self._handling = False

    def capture_current(
        self,
        *,
        origin: str,
        notify: bool = True,
    ) -> CrashReportResult | None:
        exc_type, exc_value, tb = sys.exc_info()
        if exc_type is None or exc_value is None:
            return None
        return self.capture_exception(
            exc_type,
            exc_value,
            tb,
            origin=origin,
            notify=notify,
        )

    def _sys_hook(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        traceback_object: TracebackType | None,
    ) -> None:
        self.capture_exception(
            exc_type,
            exc_value,
            traceback_object,
            origin="main_thread",
        )
        if self.chain_original:
            self._original_sys_hook(
                exc_type,
                exc_value,
                traceback_object,
            )

    def _thread_hook(self, args: Any) -> None:
        self.capture_exception(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
            origin=f"thread:{args.thread.name}",
            thread_name=args.thread.name,
        )
        if (
            self.chain_original
            and self._original_thread_hook is not None
        ):
            self._original_thread_hook(args)

    def _unraisable_hook(self, args: Any) -> None:
        exc_value = args.exc_value
        exc_type = args.exc_type or type(exc_value)
        self.capture_exception(
            exc_type,
            exc_value,
            args.exc_traceback,
            origin="unraisable",
        )
        if (
            self.chain_original
            and self._original_unraisable_hook is not None
        ):
            self._original_unraisable_hook(args)


__all__ = [
    "CrashReportDetails",
    "CrashReportInspection",
    "CrashReportResult",
    "CrashReportService",
    "GlobalCrashHandler",
]
