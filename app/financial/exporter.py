"""Canonical snapshot JSON/CSV projections with no repository access."""

from __future__ import annotations

import csv
from io import StringIO
import json

from app.financial.contracts import FinancialAnalyticsSnapshot
from app.financial.metrics import _metric_projection


def _snapshot_projection(snapshot: FinancialAnalyticsSnapshot) -> dict[str, object]:
    return {
        "contract_version": snapshot.contract_version,
        "generated_at": snapshot.generated_at.isoformat(timespec="seconds"),
        "source_fingerprint": snapshot.source_fingerprint,
        "fingerprint": snapshot.fingerprint,
        "metrics": [_metric_projection(metric) for metric in snapshot.metrics],
    }


def snapshot_to_json_bytes(snapshot: FinancialAnalyticsSnapshot) -> bytes:
    return (
        json.dumps(
            _snapshot_projection(snapshot),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def snapshot_to_csv_bytes(snapshot: FinancialAnalyticsSnapshot) -> bytes:
    target = StringIO(newline="")
    writer = csv.writer(target, lineterminator="\n")
    writer.writerow(
        (
            "snapshot_id",
            "metric_id",
            "version",
            "value",
            "currency",
            "unit",
            "state",
            "contributors",
        )
    )
    for metric in snapshot.metrics:
        item = _metric_projection(metric)
        writer.writerow(
            (
                snapshot.fingerprint,
                item["metric_id"],
                item["version"],
                item["value"] or "",
                item["currency"] or "",
                item["unit"],
                item["state"],
                "|".join(metric.contributor_ids),
            )
        )
    return target.getvalue().encode("utf-8")


__all__ = ["snapshot_to_csv_bytes", "snapshot_to_json_bytes"]
