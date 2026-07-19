"""Expected-red selection, export parity, and RM-146 adapter contracts."""

from __future__ import annotations

import csv
from io import StringIO
import json

from tests.rm147_analytics_helpers import aggregate, make_record


def test_selection_contains_exact_sorted_contributors() -> None:
    from app.tenders.analytics import resolve_selection

    snapshot = aggregate(
        (
            make_record("z", status="completed"),
            make_record("a", status="completed"),
        )
    )
    metric = next(item for item in snapshot.metrics if item.metric_id == "tenders_by_status")
    point = next(item for item in metric.points if item.bucket_key == "completed")
    selection = resolve_selection(snapshot, metric.metric_id, point.point_id)

    assert selection.snapshot_fingerprint == snapshot.fingerprint
    assert selection.contributor_ids == ("a", "z")


def test_json_csv_export_uses_the_displayed_fingerprint_without_requery() -> None:
    from app.tenders.analytics import export_snapshot_csv, export_snapshot_json

    snapshot = aggregate((make_record("only"),))
    json_payload = json.loads(export_snapshot_json(snapshot))
    csv_rows = tuple(csv.DictReader(StringIO(export_snapshot_csv(snapshot).decode("utf-8"))))

    assert json_payload["snapshot"]["fingerprint"] == snapshot.fingerprint
    assert json_payload["query_fingerprint"] == snapshot.query.fingerprint
    assert csv_rows
    assert {row["snapshot_fingerprint"] for row in csv_rows} == {snapshot.fingerprint}


def test_chart_adapter_translates_only_exact_metric_points() -> None:
    from app.tenders.analytics import TenderAnalyticsChartAdapter
    from app.ui.charts import ChartState

    snapshot = aggregate((make_record("one", status="published"),))
    metric = next(item for item in snapshot.metrics if item.metric_id == "tenders_by_status")
    spec = TenderAnalyticsChartAdapter().adapt(metric, snapshot.coverage)

    assert spec.state is ChartState.READY
    assert tuple(point.point_id for point in spec.series[0].points) == tuple(
        point.point_id for point in metric.points
    )
    assert tuple(int(point.y) for point in spec.series[0].points) == tuple(
        point.value for point in metric.points
    )
    assert spec.source_evidence[0].source_id == snapshot.coverage[0].source_id
