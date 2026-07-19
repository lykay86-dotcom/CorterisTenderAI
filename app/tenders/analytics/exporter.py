"""Deterministic data exports from an already displayed RM-147 snapshot."""

from __future__ import annotations

import csv
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unicodedata

from app.tenders.analytics.contracts import AnalyticsEvidence, TenderAnalyticsSnapshot


_BIDI_CONTROLS = frozenset(
    {
        "\u061c",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)


def _safe_text(value: str) -> str:
    if any(unicodedata.category(char) == "Cc" or char in _BIDI_CONTROLS for char in value):
        raise ValueError("export text contains forbidden control characters")
    return f"'{value}" if value.startswith(("=", "+", "-", "@")) else value


def _evidence(item: AnalyticsEvidence) -> dict[str, object]:
    return {
        "quality": item.quality.value,
        "source_ids": item.source_ids,
        "run_ids": item.run_ids,
        "contributor_count": item.contributor_count,
        "missing_count": item.missing_count,
        "excluded_count": item.excluded_count,
        "unknown_time_count": item.unknown_time_count,
        "conflict_count": item.conflict_count,
        "reason_codes": item.reason_codes,
    }


def export_snapshot_json(snapshot: TenderAnalyticsSnapshot) -> bytes:
    payload = {
        "contract_version": snapshot.contract_version,
        "query_fingerprint": snapshot.query.fingerprint,
        "query": snapshot.query.projection,
        "snapshot": {
            "generation": snapshot.generation,
            "as_of": snapshot.as_of.isoformat(timespec="seconds"),
            "fingerprint": snapshot.fingerprint,
            "state": snapshot.state.value,
        },
        "coverage": [
            {
                "source_id": item.source_id,
                "requested": item.requested,
                "enabled": item.enabled,
                "outcome": item.outcome,
                "observed_at": item.observed_at.isoformat(timespec="seconds")
                if item.observed_at
                else None,
                "freshness": item.freshness,
                "item_count": item.item_count,
                "reason_code": item.reason_code,
            }
            for item in snapshot.coverage
        ],
        "metrics": [
            {
                "metric_id": metric.metric_id,
                "metric_version": metric.version,
                "title": metric.title,
                "unit": metric.unit,
                "state": metric.state.value,
                "evidence": _evidence(metric.evidence),
                "points": [
                    {
                        "point_id": point.point_id,
                        "bucket_key": point.bucket_key,
                        "bucket_label": point.bucket_label,
                        "value": point.value,
                        "contributor_ids": point.contributor_ids,
                        "bucket_start": point.bucket_start.isoformat(timespec="seconds")
                        if point.bucket_start
                        else None,
                        "bucket_end": point.bucket_end.isoformat(timespec="seconds")
                        if point.bucket_end
                        else None,
                        "evidence": _evidence(point.evidence),
                    }
                    for point in metric.points
                ],
            }
            for metric in snapshot.metrics
        ],
        "reason_codes": snapshot.reason_codes,
    }
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def export_snapshot_csv(snapshot: TenderAnalyticsSnapshot) -> bytes:
    target = StringIO(newline="")
    fieldnames = (
        "metric_id",
        "metric_version",
        "point_id",
        "bucket_key",
        "bucket_label",
        "value",
        "unit",
        "state",
        "interval_start",
        "interval_end",
        "timezone",
        "contributor_count",
        "contributor_ids",
        "source_ids",
        "evidence_quality",
        "snapshot_fingerprint",
    )
    writer = csv.DictWriter(target, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for metric in snapshot.metrics:
        for point in metric.points:
            writer.writerow(
                {
                    "metric_id": metric.metric_id,
                    "metric_version": metric.version,
                    "point_id": point.point_id,
                    "bucket_key": _safe_text(point.bucket_key),
                    "bucket_label": _safe_text(point.bucket_label),
                    "value": str(point.value),
                    "unit": metric.unit,
                    "state": metric.state.value,
                    "interval_start": snapshot.query.interval.start_inclusive.isoformat(
                        timespec="seconds"
                    ),
                    "interval_end": snapshot.query.interval.end_exclusive.isoformat(
                        timespec="seconds"
                    ),
                    "timezone": snapshot.query.interval.timezone_name,
                    "contributor_count": str(len(point.contributor_ids)),
                    "contributor_ids": "|".join(point.contributor_ids),
                    "source_ids": "|".join(point.evidence.source_ids),
                    "evidence_quality": point.evidence.quality.value,
                    "snapshot_fingerprint": snapshot.fingerprint,
                }
            )
    return target.getvalue().encode("utf-8")


def write_export_atomically(path: str | Path, payload: bytes) -> None:
    """Replace one chosen file through a flushed sibling temporary file."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, target)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


__all__ = ["export_snapshot_csv", "export_snapshot_json", "write_export_atomically"]
