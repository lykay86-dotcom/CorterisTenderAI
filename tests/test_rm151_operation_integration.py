"""Representative owner-boundary integrations for RM-151 operation feedback."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.core.crash_reporting import CrashReportResult
from app.operations.contracts import OperationState
from app.repositories.business_metrics import BusinessMetricsRepository
from app.ui.controllers.dashboard_controller import DashboardController
from app.ui.crash_report_dialog import CrashReportDialog
from app.ui.pages.business_workflow_page import BusinessWorkflowPage
from tests.test_dashboard_background_refresh import FakePage
from tests.test_rm140_search_lifecycle import QueuedThreadPool, _controller


MALICIOUS = (
    "RM151_OWNER_SECRET Authorization: Bearer FAKE_TOKEN "
    "C:\\Users\\private\\report.txt "
    "https://example.invalid/?token=secret <script>unsafe</script> "
    "TRACEBACK_MARKER \u202e"
)
FORBIDDEN = (
    "RM151_OWNER_SECRET",
    "FAKE_TOKEN",
    "C:\\Users\\private",
    "token=secret",
    "<script>",
    "TRACEBACK_MARKER",
    "\u202e",
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _assert_safe(value: str) -> None:
    assert all(marker not in value for marker in FORBIDDEN)
    assert "diagnostic-" in value


def test_j07_search_owner_mirrors_generation_cancel_close_and_rejects_late_result(
    tmp_path,
) -> None:
    pool = QueuedThreadPool()
    controller = _controller(tmp_path, pool)

    assert controller.try_start_collector("all-corteris", ("eis",))
    queued = controller.operation_episode
    assert queued is not None
    assert queued.state is OperationState.QUEUED
    assert queued.generation == controller.lifecycle_snapshot.generation

    controller.stop_collector()
    cancelling = controller.operation_episode
    assert cancelling is not None
    assert cancelling.state is OperationState.CANCELLING
    assert cancelling.finished_at is None

    worker = pool.runnables[0]
    assert controller.shutdown(timeout_ms=50)
    closed = controller.operation_episode
    assert closed is not None
    assert closed.state is OperationState.CLOSED

    worker.run()
    assert controller.operation_episode == closed


@pytest.mark.parametrize(
    ("dialog_store", "handler_name", "setter_name", "handler_args"),
    (
        (
            "_document_dialogs",
            "_on_document_download_failed",
            "set_download_error",
            (object(), "RuntimeError", MALICIOUS),
        ),
        (
            "_full_analysis_dialogs",
            "_on_full_analysis_failed",
            "set_error",
            ("RuntimeError", MALICIOUS),
        ),
        (
            "_score_dialogs",
            "_on_participation_score_failed",
            "set_error",
            ("RuntimeError", MALICIOUS),
        ),
        (
            "_analysis_dialogs",
            "_on_requirement_analysis_failed",
            "set_analysis_error",
            ("RuntimeError", MALICIOUS),
        ),
    ),
)
def test_j09_worker_failures_are_safe_at_existing_controller_boundary(
    tmp_path,
    dialog_store,
    handler_name,
    setter_name,
    handler_args,
) -> None:
    controller = _controller(tmp_path, QueuedThreadPool())
    captured: list[str] = []
    dialog = type("CaptureDialog", (), {setter_name: lambda _self, value: captured.append(value)})()
    getattr(controller, dialog_store)["registry-151"] = dialog

    getattr(controller, handler_name)("registry-151", *handler_args)

    assert len(captured) == 1
    _assert_safe(captured[0])
    assert len(controller.operation_diagnostic_registry) == 1
    assert controller.shutdown(timeout_ms=50)


def test_dashboard_terminal_feedback_hides_exception_and_keeps_correlation() -> None:
    _app()
    page = FakePage()
    controller = DashboardController(page, auto_refresh_ms=0)

    controller._handle_refresh_failure(RuntimeError(MALICIOUS))

    assert page.errors
    _assert_safe(page.errors[-1])
    assert len(controller.operation_diagnostic_registry) == 1
    controller.shutdown()


def test_j13_workflow_feedback_hides_exception_and_keeps_correlation(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    monkeypatch.setattr(
        "app.ui.pages.business_workflow_page.SystemHealthMonitor.request_refresh",
        lambda _self: False,
    )
    page = BusinessWorkflowPage(repository=BusinessMetricsRepository(tmp_path / "workflow.json"))

    rendered = page._safe_workflow_error(RuntimeError(MALICIOUS))

    _assert_safe(rendered)
    assert len(page.operation_diagnostic_registry) == 1
    assert page.shutdown(timeout_ms=1000)
    page.close()


def test_j02_crash_dialog_uses_neutral_artifact_label_and_safe_clipboard(tmp_path) -> None:
    app = _app()
    private_path = tmp_path / "private-user" / "crash-151.ctcrash"
    private_path.parent.mkdir()
    private_path.write_bytes(b"synthetic")
    report = CrashReportResult(
        path=private_path,
        crash_id="crash-151",
        created_at="2026-07-20T12:00:00+00:00",
        origin="rm151-test",
        exception_type="builtins.RuntimeError",
        exception_message=MALICIOUS,
        traceback_text=MALICIOUS,
        size_bytes=9,
    )
    dialog = CrashReportDialog(report)

    assert str(private_path.parent) not in dialog.path_label.text()
    assert dialog.path_label.text().endswith(private_path.name)
    assert all(marker not in dialog.error_label.text() for marker in FORBIDDEN)
    assert "RuntimeError" in dialog.error_label.text()

    dialog._copy_details()
    clipboard = app.clipboard().text()
    assert "crash-151" in clipboard
    assert str(private_path.parent) not in clipboard
    assert all(marker not in clipboard for marker in FORBIDDEN)

    dialog.close()
