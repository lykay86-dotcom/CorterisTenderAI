"""Green characterization of the owners RM-147 must extend, not replace."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
import json

import pytest
from PySide6.QtWidgets import QApplication

from app.tenders.collector.freshness import (
    DeadlineTimezoneStatus,
    normalize_application_deadline,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.tender_registry import (
    TenderRegistryQuery,
    TenderRegistryRepository,
    TenderRegistrySort,
)
from app.ui.charts import (
    ChartAxis,
    ChartAxisScale,
    ChartKind,
    ChartPoint,
    ChartSeries,
    ChartSourceEvidence,
    ChartSpec,
    export_chart_csv,
    export_chart_json,
)
from app.ui.navigation import DEFAULT_ROUTE_REGISTRY, RouteId
from app.ui.tender_registry_dialog import TenderRegistryDialog
from app.ui.viewmodels.dashboard_viewmodel import DashboardSourceEvidence
from tests.test_collector_store import _run_and_save
from tests.test_tender_registry import _evaluated_tender, _run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_registry_key_is_the_stable_identity_and_first_seen_order_is_exact(
    tmp_path,
) -> None:
    repository = TenderRegistryRepository(tmp_path / "tender_registry.sqlite3")
    first = _evaluated_tender(score=70)
    second = _evaluated_tender(score=95, title="Updated title")

    repository.record_profile_run(
        _run(first, executed_at="2026-07-18T08:00:00+00:00"),
        run_id="run-1",
    )
    original = repository.get_by_procurement_number(first.tender.procurement_number)
    repository.record_profile_run(
        _run(second, executed_at="2026-07-18T09:00:00+00:00"),
        run_id="run-2",
    )
    updated = repository.get_by_procurement_number(first.tender.procurement_number)
    ordered = repository.search_tenders(
        TenderRegistryQuery(
            include_archived=True,
            sort=TenderRegistrySort.FIRST_SEEN_DESC,
            limit=1000,
        )
    )

    assert original is not None and updated is not None
    assert updated.registry_key == original.registry_key
    assert updated.first_seen_at == original.first_seen_at
    assert updated.last_seen_at == "2026-07-18T09:00:00+00:00"
    assert updated.seen_count == 2
    assert tuple(item.registry_key for item in ordered) == (updated.registry_key,)


def test_registry_and_collector_read_the_same_sqlite_facts(tmp_path) -> None:
    path = tmp_path / "tender_registry.sqlite3"
    collector = CollectorStateRepository(path)
    deduplicated, _summary = _run_and_save(
        collector,
        _evaluated_tender().tender,
        "collector-run",
    )
    registry_key = deduplicated.items[0].canonical_key

    record = TenderRegistryRepository(path).get_record(registry_key)
    sources = collector.list_sources(registry_key)
    outcomes = collector.list_provider_outcomes(limit=10)

    assert record is not None
    assert record.registry_key == registry_key
    assert tuple((item.source, item.external_id) for item in sources) == (
        (record.source, record.external_id),
    )
    assert outcomes == ()  # no provider evidence is fabricated from a completed run


def test_naive_legacy_deadline_stays_unknown_without_an_invented_offset() -> None:
    tender = _evaluated_tender().tender

    normalized = normalize_application_deadline(
        tender,
        now=datetime(2026, 7, 18, 8, tzinfo=timezone.utc),
        user_timezone="+03:00",
    )

    assert normalized.timezone_status is DeadlineTimezoneStatus.UNKNOWN
    assert normalized.deadline_utc == ""
    assert normalized.deadline_user_local == ""
    assert normalized.seconds_remaining is None


def test_navigation_keeps_one_stable_analytics_id_and_alias() -> None:
    canonical = DEFAULT_ROUTE_REGISTRY.get(RouteId.FUTURE_ANALYTICS)
    alias = DEFAULT_ROUTE_REGISTRY.resolve("analytics")

    assert RouteId.FUTURE_ANALYTICS.value == "future.analytics"
    assert alias is canonical
    assert tuple(route.route_id for route in DEFAULT_ROUTE_REGISTRY.primary_routes[:3]) == (
        RouteId.DASHBOARD,
        RouteId.TENDERS,
        RouteId.WORKFLOW,
    )


def test_registry_dialog_refresh_preserves_selection_by_registry_key(tmp_path) -> None:
    app = _app()
    repository = TenderRegistryRepository(tmp_path / "tender_registry.sqlite3")
    repository.record_profile_run(
        _run(
            _evaluated_tender(score=95),
            _evaluated_tender(
                procurement_number="0373100000126000002",
                external_id="eis-2",
                score=70,
            ),
        ),
        run_id="run-1",
    )
    dialog = TenderRegistryDialog(repository)
    dialog.table.selectRow(1)
    selected = dialog.selected_record()

    assert selected is not None
    selected_key = selected.registry_key
    dialog.refresh_records()

    assert dialog.selected_record() is not None
    assert dialog.selected_record().registry_key == selected_key
    app.processEvents()


def test_rm145_evidence_is_immutable_aware_and_reused_by_rm146() -> None:
    observed_at = datetime(2026, 7, 18, 9, tzinfo=timezone.utc)
    evidence = DashboardSourceEvidence(
        source_id="tender_registry",
        generation=7,
        observed_at=observed_at,
        record_count=2,
        contributor_ids=("eis", "eis", "rts"),
    )

    assert ChartSourceEvidence is DashboardSourceEvidence
    assert evidence.contributor_ids == ("eis", "rts")
    with pytest.raises(FrozenInstanceError):
        evidence.generation = 8  # type: ignore[misc]


def test_rm146_exports_the_exact_chart_model_in_source_order() -> None:
    evidence = ChartSourceEvidence(
        source_id="tender_registry",
        generation=3,
        observed_at=datetime(2026, 7, 18, 9, tzinfo=timezone.utc),
        record_count=2,
    )
    spec = ChartSpec(
        chart_id="tenders-by-status",
        kind=ChartKind.BAR,
        title="Tenders by status",
        x_axis=ChartAxis(ChartAxisScale.CATEGORY, title="Status"),
        y_axis=ChartAxis(ChartAxisScale.NUMERIC, title="Tenders"),
        series=(
            ChartSeries(
                series_id="tenders",
                label="Tenders",
                points=(
                    ChartPoint("status-open", "open", Decimal(2)),
                    ChartPoint("status-unknown", "unknown", Decimal(1)),
                ),
            ),
        ),
        source_evidence=(evidence,),
    )

    json_payload = json.loads(export_chart_json(spec))
    csv_payload = export_chart_csv(spec).decode("utf-8-sig")

    assert [point["point_id"] for point in json_payload["series"][0]["points"]] == [
        "status-open",
        "status-unknown",
    ]
    assert csv_payload.index("status-open") < csv_payload.index("status-unknown")
    assert json_payload["source_evidence"][0]["source_id"] == "tender_registry"
