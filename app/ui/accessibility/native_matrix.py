"""Qt-free validation for privacy-safe RM-152 native evidence reports."""

from __future__ import annotations

from collections.abc import Mapping


STATUSES = frozenset({"PASS", "FAIL", "BLOCKED", "NOT_EXECUTED"})


def validate_native_matrix(
    payload: Mapping[str, object],
    *,
    require_complete: bool = False,
) -> tuple[str, ...]:
    """Return deterministic report errors without promoting unobserved evidence."""

    errors: list[str] = []
    if payload.get("schema") != "rm152-native-matrix-v1":
        errors.append("matrix: unsupported_schema")
    cells = payload.get("cells")
    if not isinstance(cells, list):
        return (*errors, "matrix: cells_must_be_list")

    seen: set[str] = set()
    for raw_cell in cells:
        if not isinstance(raw_cell, Mapping):
            errors.append("matrix: invalid_cell")
            continue
        cell_id = str(raw_cell.get("id", "")).strip()
        if not cell_id:
            errors.append("matrix: missing_cell_id")
            continue
        if cell_id in seen:
            errors.append(f"{cell_id}: duplicate_cell")
            continue
        seen.add(cell_id)

        status = str(raw_cell.get("status", "")).strip()
        observed = raw_cell.get("observed") is True
        environment = raw_cell.get("environment")
        evidence = raw_cell.get("evidence")
        if status not in STATUSES:
            errors.append(f"{cell_id}: invalid_status")
            continue
        if status == "PASS" and not observed:
            errors.append(f"{cell_id}: pass_without_observation")
        if observed and status == "NOT_EXECUTED":
            errors.append(f"{cell_id}: observed_not_executed")
        if status == "PASS" or observed:
            if not isinstance(environment, Mapping) or not environment:
                errors.append(f"{cell_id}: missing_environment")
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"{cell_id}: missing_evidence")
        if require_complete and status != "PASS":
            errors.append(f"{cell_id}: incomplete")

    return tuple(errors)


__all__ = ["STATUSES", "validate_native_matrix"]
