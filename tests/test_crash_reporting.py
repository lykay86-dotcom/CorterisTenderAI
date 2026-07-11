"""Tests for automatic local crash reports and global hooks."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

from app.core.crash_reporting import (
    CrashReportService,
    GlobalCrashHandler,
)


NOW = datetime(2026, 7, 12, 12, 0, 0)


def _exception():
    try:
        raise RuntimeError(
            "Failure email=user@example.com "
            "api_key=super-secret"
        )
    except RuntimeError:
        return sys.exc_info()


def test_crash_report_is_verified_and_redacts_sensitive_data(
    tmp_path,
) -> None:
    private_root = tmp_path / "private-user"
    log_file = private_root / "logs" / "app.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_text(
        (
            f"Path={private_root}\n"
            "Authorization: Bearer abcdefghijklmnop\n"
        ),
        encoding="utf-8",
    )

    service = CrashReportService(
        private_root / "crash_reports",
        log_file=log_file,
    )
    exc_type, exc_value, tb = _exception()

    result = service.create_report(
        exc_type,
        exc_value,
        tb,
        origin="test",
        created_at=NOW,
    )

    assert result.path.suffix == ".ctcrash"
    assert service.inspect_report(result.path).valid

    with ZipFile(result.path) as archive:
        combined = "\n".join(
            archive.read(name).decode(
                "utf-8-sig",
                errors="replace",
            )
            for name in archive.namelist()
        )

    assert "user@example.com" not in combined
    assert "super-secret" not in combined
    assert "abcdefghijklmnop" not in combined
    assert str(private_root) not in combined
    assert "<EMAIL>" in combined
    assert "<REDACTED>" in combined
    assert "<PRIVATE_PATH>" in combined


def test_crash_report_inspection_detects_tampering(tmp_path) -> None:
    service = CrashReportService(tmp_path / "crashes")
    exc_type, exc_value, tb = _exception()
    valid = service.create_report(
        exc_type,
        exc_value,
        tb,
        origin="test",
        created_at=NOW,
    )

    tampered = tmp_path / "tampered.ctcrash"
    with ZipFile(valid.path) as source, ZipFile(
        tampered,
        "w",
        compression=ZIP_DEFLATED,
    ) as target:
        for name in source.namelist():
            content = source.read(name)
            if name == "traceback.txt":
                content = b"changed"
            target.writestr(name, content)

    inspection = service.inspect_report(tampered)

    assert not inspection.valid
    assert any(
        "traceback.txt" in error
        and "сумма" in error
        for error in inspection.errors
    )


def test_global_handler_installs_captures_and_restores_hooks(
    tmp_path,
) -> None:
    service = CrashReportService(tmp_path / "crashes")
    captured = []
    original = sys.excepthook
    handler = GlobalCrashHandler(
        service,
        report_callback=captured.append,
        chain_original=False,
    )

    handler.install()
    try:
        assert handler.is_installed
        assert sys.excepthook == handler._sys_hook

        exc_type, exc_value, tb = _exception()
        handler._sys_hook(exc_type, exc_value, tb)

        assert len(captured) == 1
        assert captured[0].path.exists()
    finally:
        handler.uninstall()

    assert not handler.is_installed
    assert sys.excepthook == original


def test_thread_hook_records_thread_origin(tmp_path) -> None:
    service = CrashReportService(tmp_path / "crashes")
    captured = []
    handler = GlobalCrashHandler(
        service,
        report_callback=captured.append,
        chain_original=False,
    )
    exc_type, exc_value, tb = _exception()
    thread = threading.Thread(name="TenderWorker")
    args = SimpleNamespace(
        exc_type=exc_type,
        exc_value=exc_value,
        exc_traceback=tb,
        thread=thread,
    )

    handler._thread_hook(args)

    assert len(captured) == 1
    assert captured[0].origin == "thread:TenderWorker"
