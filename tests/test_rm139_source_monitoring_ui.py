import os
from datetime import datetime, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.provider_control import ProviderDisplayState, ProviderUiState
from app.tenders.collector.scheduler import CollectorScheduleRepository
from app.tenders.collector.source_monitoring import SourceMonitoringService
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.vertical_source_verification import VerticalSourceVerificationRepository
from app.ui.tender_provider_manager_dialog import TenderProviderManagerDialog


def test_dialog_renders_monitoring_dimensions_without_calculating_them(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    state = ProviderDisplayState(
        provider_id="eis",
        display_name="ЕИС",
        enabled=True,
        ui_state=ProviderUiState.UNKNOWN,
        status_text="Не проверено",
        connection_mode="HTML",
        implementation_status="test",
        homepage_url="https://example.test/",
        last_checked_at="",
        last_success_at="",
        last_error="",
        latency_ms=None,
        checkpoint_supported=True,
    )
    service = SourceMonitoringService(
        state_repository=CollectorStateRepository(tmp_path / "registry.sqlite3"),
        schedule_repository=CollectorScheduleRepository(tmp_path / "schedule.json"),
        verification_repository=VerticalSourceVerificationRepository(tmp_path / "registry.sqlite3"),
    )
    snapshot = service.snapshot(
        (state,), observed_at=datetime(2026, 7, 18, 12, tzinfo=timezone.utc)
    )
    dialog = TenderProviderManagerDialog((state,), monitoring_snapshot=snapshot)

    headers = [
        dialog.table.horizontalHeaderItem(i).text() for i in range(dialog.table.columnCount())
    ]
    assert "Подключение" in headers
    assert "Сбор/circuit" in headers
    assert "Checkpoint" in headers
    assert "C19" in headers
    assert dialog.table.objectName() == "TenderProviderTable"
    app.processEvents()
