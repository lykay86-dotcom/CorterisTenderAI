"""Tests for non-blocking system health monitoring."""

from __future__ import annotations

import os
from threading import Event

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from app.core.system_health_monitor import SystemHealthMonitor


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _wait_until(predicate, timeout_ms: int = 2000) -> None:
    app = _app()
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(10)

    def check() -> None:
        if predicate():
            timer.stop()
            loop.quit()

    timer.timeout.connect(check)
    timer.start()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    app.processEvents()


def test_monitor_suppresses_duplicate_refreshes() -> None:
    _app()
    entered = Event()
    release = Event()

    def collector():
        entered.set()
        release.wait(timeout=2)
        return object()

    monitor = SystemHealthMonitor(collector)
    assert monitor.request_refresh()
    assert entered.wait(timeout=1)
    assert not monitor.request_refresh()

    release.set()
    _wait_until(lambda: not monitor.is_running)

    assert not monitor.is_running


def test_monitor_emits_result_and_failure() -> None:
    _app()
    snapshots: list[object] = []
    errors: list[str] = []

    successful = SystemHealthMonitor(lambda: "snapshot")
    successful.snapshot_ready.connect(snapshots.append)
    successful.request_refresh()
    _wait_until(lambda: bool(snapshots))

    failing = SystemHealthMonitor(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    failing.check_failed.connect(errors.append)
    failing.request_refresh()
    _wait_until(lambda: bool(errors))

    assert snapshots == ["snapshot"]
    assert errors == ["boom"]
