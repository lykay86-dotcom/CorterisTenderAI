"""PySide6 tests for the unified Tender Collector dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.async_engine import (
    AsyncProviderBatchResult,
    AsyncProviderSearchOutcome,
    AsyncProviderSearchStatus,
)
from app.tenders.collector.models import (
    CollectionPersistenceSummary,
    CollectionRunStatus,
    CollectorRunResult,
    DeduplicationResult,
)
from app.tenders.collector.progress import (
    CollectorProgressEvent,
    CollectorProgressPhase,
)
from app.tenders.collector.provider_control import (
    ProviderDisplayState,
    ProviderUiState,
)
from app.tenders.search_profiles import TenderSearchProfile
from app.ui.tender_collector_dialog import TenderCollectorDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _profile() -> TenderSearchProfile:
    return TenderSearchProfile(
        id="collector-test",
        name="Тестовый профиль",
        keywords=("видеонаблюдение",),
        provider_ids=("eis",),
    )


def _states() -> tuple[ProviderDisplayState, ...]:
    return (
        ProviderDisplayState(
            provider_id="eis",
            display_name="ЕИС",
            enabled=True,
            ui_state=ProviderUiState.LIMITED,
            status_text="Резервный HTML-режим",
            connection_mode="Публичный HTML",
            implementation_status="public_html_async",
            homepage_url="https://zakupki.gov.ru/",
            last_checked_at="",
            last_success_at="",
            last_error="",
            latency_ms=None,
        ),
        ProviderDisplayState(
            provider_id="b2b_center",
            display_name="B2B-Center",
            enabled=False,
            ui_state=ProviderUiState.DISABLED,
            status_text="Отключён пользователем",
            connection_mode="API",
            implementation_status="access_required",
            homepage_url="https://www.b2b-center.ru/",
            last_checked_at="",
            last_success_at="",
            last_error="",
            latency_ms=None,
        ),
    )


def _result() -> CollectorRunResult:
    outcome = AsyncProviderSearchOutcome(
        provider_id="eis",
        display_name="ЕИС",
        status=AsyncProviderSearchStatus.SUCCESS,
        elapsed_ms=120,
        item_count=4,
    )
    batch = AsyncProviderBatchResult(
        results=(),
        outcomes=(outcome,),
        started_at="2026-07-12T10:00:00+00:00",
        completed_at="2026-07-12T10:00:01+00:00",
        elapsed_ms=1000,
    )
    deduplication = DeduplicationResult(
        items=(),
        groups=(),
        raw_count=4,
    )
    persistence = CollectionPersistenceSummary(
        run_id="run-1",
        new_count=2,
        unchanged_count=1,
        changed_count=1,
        merged_count=3,
        duplicate_count=1,
        change_count=1,
        version_count=3,
    )
    return CollectorRunResult(
        run_id="run-1",
        status=CollectionRunStatus.COMPLETED,
        batch_result=batch,
        deduplication=deduplication,
        persistence=persistence,
    )


def test_dialog_selects_only_enabled_sources_and_emits_start() -> None:
    app = _app()
    dialog = TenderCollectorDialog()
    dialog.set_profiles((_profile(),))
    dialog.set_provider_states(_states())
    requested = []
    dialog.start_requested.connect(
        lambda profile_id, provider_ids: requested.append(
            (profile_id, tuple(provider_ids))
        )
    )

    dialog.start_button.click()

    assert requested == [("collector-test", ("eis",))]
    assert dialog.provider_table.rowCount() == 2
    app.processEvents()


def test_dialog_updates_progress_and_summary() -> None:
    app = _app()
    dialog = TenderCollectorDialog()
    dialog.set_profiles((_profile(),))
    dialog.set_provider_states(_states())
    dialog.begin_run("Тестовый профиль", ("eis",))

    dialog.apply_progress(
        CollectorProgressEvent(
            phase=CollectorProgressPhase.PROVIDER_COMPLETED,
            provider_id="eis",
            display_name="ЕИС",
            provider_status="success",
            item_count=4,
            elapsed_ms=120,
            total_providers=1,
            message="Готово",
        )
    )
    dialog.set_result(_result())

    assert dialog.new_value.text() == "2"
    assert dialog.changed_value.text() == "1"
    assert dialog.duplicate_value.text() == "1"
    assert dialog.saved_value.text() == "3"
    assert dialog.progress_bar.value() == 100
    assert not dialog.running
    app.processEvents()


def test_dialog_renders_unverified_provider_without_crashing() -> None:
    app = _app()
    dialog = TenderCollectorDialog()
    state = ProviderDisplayState(
        provider_id="mos_supplier",
        display_name="Портал поставщиков Москвы",
        enabled=True,
        ui_state=ProviderUiState.UNVERIFIED,
        status_text="Требуется полная проверка C19",
        connection_mode="Официальный API",
        implementation_status="official_api_bearer",
        homepage_url="https://zakupki.mos.ru/",
        last_checked_at="",
        last_success_at="",
        last_error="",
        latency_ms=None,
    )

    dialog.set_provider_states((state,))

    assert dialog.provider_table.rowCount() == 1
    assert dialog._provider_ui_color(ProviderUiState.UNVERIFIED)
    app.processEvents()
