"""Tests for the crash report dialog and Qt bridge."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app.core.crash_reporting import (
    CrashReportResult,
    CrashReportService,
    GlobalCrashHandler,
)
from app.ui.crash_report_dialog import (
    CrashReportDialog,
    QtCrashBridge,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _report(tmp_path) -> CrashReportResult:
    path = tmp_path / "crash.ctcrash"
    path.write_bytes(b"report")
    return CrashReportResult(
        path=path,
        crash_id="abc",
        created_at="2026-07-12T12:00:00",
        origin="main_thread",
        exception_type="builtins.RuntimeError",
        exception_message="boom",
        traceback_text="Traceback\nRuntimeError: boom",
        size_bytes=path.stat().st_size,
    )


def test_dialog_enables_bundle_button_only_with_provider(
    tmp_path,
) -> None:
    _app()
    report = _report(tmp_path)

    disabled = CrashReportDialog(report)
    enabled = CrashReportDialog(
        report,
        support_bundle_provider=lambda target: target,
    )

    assert not disabled.save_bundle_button.isEnabled()
    assert enabled.save_bundle_button.isEnabled()
    assert "RuntimeError" in enabled.error_label.text()


def test_dialog_saves_support_bundle_through_provider(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    report = _report(tmp_path)
    calls: list[Path] = []
    target = tmp_path / "support.ctsupport"

    class Result:
        path = target

    dialog = CrashReportDialog(
        report,
        support_bundle_provider=lambda value: (
            calls.append(Path(value)) or Result()
        ),
    )

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(target), ""),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    dialog._save_support_bundle()

    assert calls == [target]


def test_qt_bridge_registers_callback_and_provider(tmp_path) -> None:
    app = _app()
    handler = GlobalCrashHandler(
        CrashReportService(tmp_path / "crashes"),
        chain_original=False,
    )
    bridge = QtCrashBridge(handler, parent=app)
    provider = lambda target: target

    bridge.set_support_bundle_provider(provider)

    assert handler.report_callback == bridge.notify
    assert bridge.support_bundle_provider is provider
