"""Expected-red contract for bounded workflow health lifecycle ownership."""

from __future__ import annotations

import os
from threading import Event
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QThreadPool, QTimer
from PySide6.QtWidgets import QApplication

import app.core.system_health_monitor as health_monitor_module
from app.core.system_health_monitor import SystemHealthMonitor
from app.repositories.business_metrics import BusinessMetricsRepository
from app.ui.pages.business_workflow_page import BusinessWorkflowPage
from tests.test_rm127_modern_main_window_composition import _window as _rm127_window


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


def _lifecycle_state_type():
    return getattr(health_monitor_module, "SystemHealthLifecycleState")


def test_monitor_uses_owned_pool_and_rejects_refresh_after_close() -> None:
    _app()
    state_type = _lifecycle_state_type()
    monitor = SystemHealthMonitor(lambda: object())

    assert monitor.thread_pool is not QThreadPool.globalInstance()
    assert monitor.thread_pool.parent() is monitor
    assert monitor.lifecycle_state is state_type.OPEN
    assert monitor.shutdown(timeout_ms=1000) is True
    assert monitor.lifecycle_state is state_type.CLOSED
    assert monitor.request_refresh() is False
    assert monitor.shutdown(timeout_ms=0) is True


def test_late_generation_is_suppressed_and_finishes_closing() -> None:
    _app()
    state_type = _lifecycle_state_type()
    entered = Event()
    release = Event()
    snapshots: list[object] = []
    failures: list[str] = []
    busy: list[bool] = []

    def collector():
        entered.set()
        release.wait(timeout=2)
        return "late"

    monitor = SystemHealthMonitor(collector)
    monitor.snapshot_ready.connect(snapshots.append)
    monitor.check_failed.connect(failures.append)
    monitor.busy_changed.connect(busy.append)

    assert monitor.request_refresh() is True
    assert entered.wait(timeout=1)
    assert monitor.shutdown(timeout_ms=0) is False
    assert monitor.lifecycle_state is state_type.CLOSING
    assert monitor.request_refresh() is False

    release.set()
    _wait_until(lambda: monitor.lifecycle_state is state_type.CLOSED)

    assert monitor.lifecycle_state is state_type.CLOSED
    assert snapshots == []
    assert failures == []
    assert busy == [True]
    assert monitor.shutdown(timeout_ms=0) is True


def test_page_shutdown_stops_sources_and_guards_pending_callbacks(
    tmp_path,
    monkeypatch,
) -> None:
    app = _app()
    pending: list[object] = []
    callbacks: list[str] = []
    monkeypatch.setattr(
        "app.ui.pages.business_workflow_page.QTimer.singleShot",
        lambda _delay, callback: pending.append(callback),
    )
    monkeypatch.setattr(
        BusinessWorkflowPage,
        "_initialize_database_safety",
        lambda _self: callbacks.append("database"),
    )
    monkeypatch.setattr(
        BusinessWorkflowPage,
        "_request_system_health_refresh",
        lambda _self: callbacks.append("health"),
    )

    page = BusinessWorkflowPage(repository=BusinessMetricsRepository(tmp_path / "workflow.json"))
    assert page.shutdown(timeout_ms=1000) is True
    assert page.shutdown(timeout_ms=0) is True
    assert not page._auto_backup_timer.isActive()
    assert not page._system_health_timer.isActive()

    for callback in pending:
        callback()
    app.processEvents()
    assert callbacks == []

    page.close()
    page.deleteLater()
    app.processEvents()


def test_shell_shutdown_order_includes_workflow_after_search_preflight(monkeypatch) -> None:
    app = _app()
    monkeypatch.setattr(
        "app.ui.pages.business_workflow_page.SystemHealthMonitor.request_refresh",
        lambda _self: False,
    )
    window = _rm127_window(monkeypatch)
    calls: list[str] = []
    window._tender_search_ui_controller = SimpleNamespace(
        shutdown=lambda: calls.append("search") or True,
    )
    monkeypatch.setattr(
        window.workflow_page,
        "shutdown",
        lambda: calls.append("workflow") or True,
    )
    monkeypatch.setattr(
        window.dashboard_controller,
        "shutdown",
        lambda: calls.append("dashboard"),
    )

    assert window.close() is True
    app.processEvents()
    assert calls == ["search", "workflow", "dashboard"]

    window.deleteLater()
    app.processEvents()
