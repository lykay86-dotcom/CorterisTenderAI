"""Final one-owner runtime composition acceptance for RM-155."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from app.core.system_health_monitor import SystemHealthMonitor
from app.ui.modern_main_window import ModernMainWindow
from app.ui.pages.business_workflow_page import BusinessWorkflowPage
from tests.test_rm127_modern_main_window_composition import _window as _rm127_window


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_one_shell_stack_page_and_lifecycle_owner_per_surface(monkeypatch) -> None:
    app = _app()
    monkeypatch.setattr(
        "app.ui.pages.business_workflow_page.SystemHealthMonitor.request_refresh",
        lambda _self: False,
    )
    window = _rm127_window(monkeypatch)

    assert isinstance(window, ModernMainWindow)
    assert window.findChildren(QMainWindow) == []
    assert window.workspace.findChildren(
        QStackedWidget,
        options=Qt.FindChildOption.FindDirectChildrenOnly,
    ) == [window.workspace.pages]
    assert window.workspace.pages.count() == 4
    assert window.findChildren(BusinessWorkflowPage) == [window.workflow_page]
    assert window.findChildren(SystemHealthMonitor) == [window.workflow_page.system_health_monitor]
    assert not hasattr(window, "quotes_page")
    assert not hasattr(window, "estimates_page")
    assert window.findChildren(QThread) == []
    assert all(timer.parent() is not None for timer in window.findChildren(QTimer))

    window.close()
    window.deleteLater()
    app.processEvents()
