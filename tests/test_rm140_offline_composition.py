"""RM-140 startup, local UI and shutdown remain offline until explicit run."""

from __future__ import annotations

import os
import socket
from urllib import request as urllib_request

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import keyring
from PySide6.QtWidgets import QApplication

from app.tenders.search_runtime import create_tender_search_runtime
from app.ui.tender_search_ui_controller import TenderSearchUiController


class ForbiddenTransport:
    def get(self, *_args, **_kwargs):
        raise AssertionError("HTTP is forbidden during offline composition")


def test_runtime_dialog_loads_and_repeated_shutdown_do_not_use_network_or_keyring(
    tmp_path,
    monkeypatch,
) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("external I/O is forbidden before an accepted run")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(urllib_request, "urlopen", forbidden)
    monkeypatch.setattr(keyring, "get_password", forbidden)

    application = QApplication.instance() or QApplication([])
    runtime = create_tender_search_runtime(tmp_path, http_transport=ForbiddenTransport())
    controller = TenderSearchUiController(tmp_path, runtime=runtime)

    controller.open_profiles_dialog()
    controller.open_provider_manager_dialog()
    controller.open_registry_dialog()
    application.processEvents()
    controller.shutdown(timeout_ms=3_000)
    controller.shutdown(timeout_ms=3_000)

    assert runtime.engine is None
    assert runtime.runner is None
    assert controller.lifecycle_snapshot.state.value == "closed"
