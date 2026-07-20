"""Qt-free validation for privacy-safe RM-152 native evidence reports."""

from __future__ import annotations

from collections.abc import Mapping


STATUSES = frozenset({"PASS", "FAIL", "BLOCKED", "NOT_EXECUTED"})


def _required_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_owner_exceptions(
    payload: Mapping[str, object],
    cells: Mapping[str, Mapping[str, object]],
) -> tuple[list[str], set[str]]:
    """Validate explicit owner exceptions without changing native cell truth."""

    errors: list[str] = []
    accepted: set[str] = set()
    raw_decision = payload.get("owner_exception_decision")
    raw_exceptions = payload.get("owner_exceptions")
    if raw_decision is None and raw_exceptions is None:
        return errors, accepted

    decision_valid = True
    if not isinstance(raw_decision, Mapping):
        errors.append("matrix: invalid_owner_exception_decision")
        decision_valid = False
        decision_id = ""
    else:
        decision_id = str(raw_decision.get("id", "")).strip()
        if not decision_id:
            errors.append("matrix: missing_owner_exception_decision_id")
            decision_valid = False
        if raw_decision.get("approved") is not True:
            errors.append("matrix: owner_exceptions_not_approved")
            decision_valid = False
        if raw_decision.get("approved_by") != "project_owner":
            errors.append("matrix: invalid_owner_exception_approver")
            decision_valid = False
        for field in ("approved_at", "statement", "policy"):
            if not _required_text(raw_decision.get(field)):
                errors.append(f"matrix: missing_owner_exception_{field}")
                decision_valid = False

    if not isinstance(raw_exceptions, list):
        errors.append("matrix: owner_exceptions_must_be_list")
        return errors, accepted

    seen_ids: set[str] = set()
    seen_cells: set[str] = set()
    for raw_exception in raw_exceptions:
        if not isinstance(raw_exception, Mapping):
            errors.append("matrix: invalid_owner_exception")
            continue
        exception_id = str(raw_exception.get("id", "")).strip()
        cell_id = str(raw_exception.get("cell_id", "")).strip()
        exception_valid = decision_valid
        if not exception_id:
            errors.append("matrix: missing_owner_exception_id")
            exception_valid = False
        elif exception_id in seen_ids:
            errors.append(f"{exception_id}: duplicate_owner_exception")
            exception_valid = False
        else:
            seen_ids.add(exception_id)
        if not cell_id:
            errors.append(f"{exception_id or 'matrix'}: missing_exception_cell_id")
            continue
        if cell_id in seen_cells:
            errors.append(f"{cell_id}: duplicate_owner_exception_cell")
            exception_valid = False
        else:
            seen_cells.add(cell_id)
        cell = cells.get(cell_id)
        if cell is None:
            errors.append(f"{cell_id}: exception_for_unknown_cell")
            continue
        status = str(cell.get("status", "")).strip()
        if status == "PASS":
            errors.append(f"{cell_id}: exception_for_pass")
            exception_valid = False
        if raw_exception.get("decision_id") != decision_id:
            errors.append(f"{cell_id}: exception_decision_mismatch")
            exception_valid = False
        if raw_exception.get("approved_by") != "project_owner":
            errors.append(f"{cell_id}: invalid_exception_approver")
            exception_valid = False
        if not _required_text(raw_exception.get("approved_at")):
            errors.append(f"{cell_id}: missing_exception_approved_at")
            exception_valid = False
        environment = raw_exception.get("environment")
        if not isinstance(environment, Mapping) or not environment:
            errors.append(f"{cell_id}: missing_exception_environment")
            exception_valid = False
        elif not all(
            _required_text(environment.get(field)) for field in ("available", "unavailable")
        ):
            errors.append(f"{cell_id}: incomplete_exception_environment")
            exception_valid = False
        for field in ("reason", "residual_risk"):
            if not _required_text(raw_exception.get(field)):
                errors.append(f"{cell_id}: missing_exception_{field}")
                exception_valid = False
        if raw_exception.get("status_retained") != status:
            errors.append(f"{cell_id}: exception_status_mismatch")
            exception_valid = False
        if raw_exception.get("accepted_without_pass") is not True:
            errors.append(f"{cell_id}: exception_must_retain_truthful_status")
            exception_valid = False
        if exception_valid:
            accepted.add(cell_id)
    return errors, accepted


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
    cells_by_id: dict[str, Mapping[str, object]] = {}
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
        cells_by_id[cell_id] = raw_cell

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

    exception_errors, accepted_exceptions = _validate_owner_exceptions(payload, cells_by_id)
    errors.extend(exception_errors)
    if require_complete:
        for cell_id, raw_cell in cells_by_id.items():
            status = str(raw_cell.get("status", "")).strip()
            if status != "PASS" and cell_id not in accepted_exceptions:
                errors.append(f"{cell_id}: incomplete")

    return tuple(errors)


__all__ = ["STATUSES", "validate_native_matrix"]
