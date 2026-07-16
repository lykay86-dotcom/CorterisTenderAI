"""RM-128 reusable unified tender-search panel."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.tenders.collector.provider_control import ProviderDisplayState, ProviderUiState
from app.tenders.search_profiles import TenderSearchProfile
from app.tenders.unified_search import UnifiedTenderSearchRequest
from app.ui.tender_unified_search_panel import TenderUnifiedSearchPanel


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _profile(profile_id: str, providers: tuple[str, ...]) -> TenderSearchProfile:
    return TenderSearchProfile(
        id=profile_id,
        name=f"Профиль {profile_id}",
        description="Описание профиля",
        keywords=("камеры",),
        provider_ids=providers,
    )


def _state(provider_id: str, *, enabled: bool) -> ProviderDisplayState:
    return ProviderDisplayState(
        provider_id=provider_id,
        display_name=provider_id.upper(),
        enabled=enabled,
        ui_state=ProviderUiState.LIMITED if enabled else ProviderUiState.DISABLED,
        status_text="Доступен" if enabled else "Отключён",
        connection_mode="Тест",
        implementation_status="test",
        homepage_url="https://example.invalid/",
        last_checked_at="",
        last_success_at="",
        last_error="",
        latency_ms=None,
    )


def test_panel_has_stable_names_and_deterministic_defaults() -> None:
    _app()
    panel = TenderUnifiedSearchPanel()
    panel.set_provider_states((_state("eis", enabled=True), _state("disabled", enabled=False)))
    panel.set_profiles(
        (_profile("first", ("disabled",)), _profile("second", ("eis",))),
        select_id="second",
    )

    assert panel.objectName() == "TenderUnifiedSearchPanel"
    assert panel.profile_combo.objectName() == "UnifiedTenderSearchProfileCombo"
    assert panel.query_edit.objectName() == "UnifiedTenderSearchQuery"
    assert panel.provider_list.objectName() == "UnifiedTenderSearchProviders"
    assert panel.start_button.objectName() == "UnifiedTenderSearchStartButton"
    assert panel.stop_button.objectName() == "UnifiedTenderSearchStopButton"
    assert panel.profiles_button.objectName() == "UnifiedTenderSearchProfilesButton"
    assert panel.sources_button.objectName() == "UnifiedTenderSearchSourcesButton"
    assert panel.registry_button.objectName() == "UnifiedTenderSearchRegistryButton"
    assert panel.progress_bar.objectName() == "UnifiedTenderSearchProgress"
    assert panel.status_label.objectName() == "UnifiedTenderSearchStatus"
    assert panel.profile_combo.currentData() == "second"
    assert panel.selected_provider_ids() == ("eis",)
    assert panel.start_button.isEnabled()
    disabled = panel.provider_list.item(1)
    assert not bool(disabled.flags() & Qt.ItemFlag.ItemIsUserCheckable)


def test_panel_emits_one_typed_request_and_tracks_busy_state() -> None:
    app = _app()
    panel = TenderUnifiedSearchPanel()
    panel.set_provider_states((_state("eis", enabled=True),))
    panel.set_profiles((_profile("video", ("eis",)),))
    requested: list[UnifiedTenderSearchRequest] = []
    panel.start_requested.connect(requested.append)
    panel.query_edit.setText("  камеры   IP  ")

    panel.start_button.click()

    assert requested == [UnifiedTenderSearchRequest("video", "камеры IP", ("eis",))]
    panel.begin_run("Профиль video", ("eis",))
    assert panel.running
    assert not panel.start_button.isEnabled()
    assert panel.stop_button.isEnabled()
    panel.mark_cancel_requested()
    assert "Остановка" in panel.status_label.text()
    app.processEvents()


def test_panel_refresh_preserves_only_valid_source_selection() -> None:
    _app()
    panel = TenderUnifiedSearchPanel()
    panel.set_provider_states((_state("eis", enabled=True), _state("mos", enabled=True)))
    panel.set_profiles((_profile("video", ("eis", "mos")),))
    panel.set_selected_provider_ids(("mos",))

    panel.set_provider_states((_state("eis", enabled=True), _state("mos", enabled=False)))

    assert panel.selected_provider_ids() == ()
    assert not panel.start_button.isEnabled()
    assert "нет доступных" in panel.status_label.text().casefold()


def test_profile_refresh_keeps_still_valid_per_run_source_selection() -> None:
    _app()
    panel = TenderUnifiedSearchPanel()
    profiles = (_profile("video", ("eis", "mos")),)
    panel.set_provider_states((_state("eis", enabled=True), _state("mos", enabled=True)))
    panel.set_profiles(profiles)
    panel.set_selected_provider_ids(("mos",))

    panel.set_profiles(profiles, select_id="video")

    assert panel.selected_provider_ids() == ("mos",)
