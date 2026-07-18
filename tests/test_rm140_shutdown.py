"""Expected RM-140 application and persistence shutdown contract."""

from __future__ import annotations

import inspect
import sqlite3

import pytest

from app.tenders.collector.store import CollectorStateRepository
from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.modern_main_window import ModernMainWindow
from app.ui.tender_collector_scheduler_controller import (
    TenderCollectorSchedulerUiController,
)
from app.ui.tender_search_ui_controller import TenderSearchUiController


def test_application_owners_expose_idempotent_bounded_shutdown() -> None:
    tender_signature = inspect.signature(TenderSearchUiController.shutdown)
    scheduler_signature = inspect.signature(TenderCollectorSchedulerUiController.shutdown)

    assert "timeout_ms" in tender_signature.parameters
    assert tuple(scheduler_signature.parameters) == ("self",)


def test_modern_shell_closes_tender_owner_before_dashboard_owner() -> None:
    source = inspect.getsource(ModernMainWindow.closeEvent)

    tender_position = source.index("tender_search")
    dashboard_position = source.index("dashboard_controller.shutdown")
    assert tender_position < dashboard_position


@pytest.mark.parametrize(
    "repository_type",
    (TenderRegistryRepository, CollectorStateRepository),
)
def test_repository_connection_scope_always_calls_close(
    tmp_path,
    monkeypatch,
    repository_type,
) -> None:
    original_connect = sqlite3.connect
    created: list[sqlite3.Connection] = []
    closed: list[sqlite3.Connection] = []

    class TrackingConnection(sqlite3.Connection):
        def close(self) -> None:
            closed.append(self)
            super().close()

    def tracking_connect(*args, **kwargs):
        kwargs["factory"] = TrackingConnection
        connection = original_connect(*args, **kwargs)
        created.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", tracking_connect)

    repository_type(tmp_path / "registry.sqlite3").initialize()

    assert created
    assert closed == created
