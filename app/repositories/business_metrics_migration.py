"""Controlled byte-backed workflow v2 to exact financial v3 migration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from app.financial import (
    MARGIN_CONTRACT_VERSION,
    CurrencyCode,
    FinancialMigrationError,
    FinancialValueState,
    MoneyAmount,
    canonical_money,
    canonical_percentage,
    derive_margin,
    parse_money,
)
from app.repositories.business_metrics import BusinessMetricsRepository


@dataclass(frozen=True, slots=True)
class BusinessMetricsMigrationIssue:
    record_id: str
    field: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class BusinessMetricsMigrationPlan:
    source_sha256: str
    source_schema: int
    target_schema: int
    record_count: int
    issues: tuple[BusinessMetricsMigrationIssue, ...]
    _source_bytes: bytes = field(repr=False)
    _candidate_bytes: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class BusinessMetricsMigrationResult:
    backup_path: Path
    source_sha256: str
    target_sha256: str
    record_count: int


class BusinessMetricsV3Migration:
    """One explicit, idempotent and rollback-capable schema operation."""

    def __init__(self, repository: BusinessMetricsRepository) -> None:
        self.repository = repository

    def dry_run(self) -> BusinessMetricsMigrationPlan:
        with self.repository._lock:
            if not self.repository.path.exists():
                raise FinancialMigrationError("workflow store does not exist")
            source = self.repository.path.read_bytes()
            source_sha = hashlib.sha256(source).hexdigest()
            try:
                payload = json.loads(
                    source.decode("utf-8"),
                    parse_float=Decimal,
                    parse_int=Decimal,
                )
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise FinancialMigrationError("workflow JSON is corrupt") from exc
            if not isinstance(payload, dict):
                raise FinancialMigrationError("workflow payload must be an object")
            schema = int(payload.get("schema_version", 1))
            if schema == self.repository.SCHEMA_VERSION:
                return BusinessMetricsMigrationPlan(
                    source_sha,
                    schema,
                    schema,
                    len(payload.get("records", [])),
                    (),
                    source,
                    source,
                )
            if schema != 2:
                raise FinancialMigrationError(f"unsupported source schema: {schema}")
            records = payload.get("records")
            if not isinstance(records, list):
                raise FinancialMigrationError("workflow records must be a list")

            issues: list[BusinessMetricsMigrationIssue] = []
            migrated: list[dict[str, Any]] = []
            for index, raw in enumerate(records):
                if not isinstance(raw, dict):
                    issues.append(
                        BusinessMetricsMigrationIssue(
                            f"row-{index + 1}",
                            "record",
                            "record_not_object",
                            "Record must be an object.",
                        )
                    )
                    continue
                record_id = str(raw.get("id", f"row-{index + 1}"))
                total = self._money(raw.get("total", 0), record_id, "total", issues)
                profit = self._money(raw.get("profit", 0), record_id, "profit", issues)
                supplied_margin = self._percentage(
                    raw.get("margin_percent", 0),
                    record_id,
                    issues,
                )
                if total is None or profit is None or supplied_margin is None:
                    continue
                derived = derive_margin(MoneyAmount(total), MoneyAmount(profit))
                if derived.state is FinancialValueState.AVAILABLE and derived.value is not None:
                    derived_text = canonical_percentage(derived.value)
                    if (
                        supplied_margin != 0
                        and canonical_percentage(supplied_margin) != derived_text
                    ):
                        issues.append(
                            BusinessMetricsMigrationIssue(
                                record_id,
                                "margin_percent",
                                "margin_conflict",
                                "Stored margin does not match total and profit.",
                            )
                        )
                        continue
                elif supplied_margin != 0:
                    issues.append(
                        BusinessMetricsMigrationIssue(
                            record_id,
                            "margin_percent",
                            "margin_undefined",
                            "Margin is not defined for these operands.",
                        )
                    )
                    continue
                else:
                    derived_text = "0.00"
                candidate = dict(raw)
                candidate.update(
                    {
                        "total": canonical_money(total),
                        "profit": canonical_money(profit),
                        "currency": CurrencyCode.RUB.value,
                        "margin_percent": derived_text,
                        "margin_version": MARGIN_CONTRACT_VERSION,
                    }
                )
                migrated.append(candidate)

            target = dict(payload)
            target["schema_version"] = self.repository.SCHEMA_VERSION
            target["records"] = migrated
            candidate_bytes = (
                json.dumps(
                    self.repository._json_compatible(target),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8")
            ordered_issues = tuple(
                sorted(issues, key=lambda item: (item.record_id, item.field, item.code))
            )
            return BusinessMetricsMigrationPlan(
                source_sha,
                schema,
                self.repository.SCHEMA_VERSION,
                len(records),
                ordered_issues,
                source,
                candidate_bytes,
            )

    def execute(
        self,
        plan: BusinessMetricsMigrationPlan | None = None,
    ) -> BusinessMetricsMigrationResult:
        with self.repository._lock:
            prepared = plan or self.dry_run()
            if prepared.issues:
                detail = "; ".join(
                    f"{issue.record_id}.{issue.field}:{issue.code}" for issue in prepared.issues
                )
                raise FinancialMigrationError(f"migration validation failed: {detail}")
            current = self.repository.path.read_bytes()
            if hashlib.sha256(current).hexdigest() != prepared.source_sha256:
                raise FinancialMigrationError("workflow store changed after migration dry-run")
            if prepared.source_schema == prepared.target_schema:
                return BusinessMetricsMigrationResult(
                    self.repository.path,
                    prepared.source_sha256,
                    prepared.source_sha256,
                    prepared.record_count,
                )

            timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
            backup = self.repository.path.with_suffix(
                self.repository.path.suffix + f".v2.safety-{timestamp}.json"
            )
            temporary = self.repository.path.with_suffix(self.repository.path.suffix + ".v3.tmp")
            self._write_fsynced(backup, current)
            try:
                self._write_fsynced(temporary, prepared._candidate_bytes)
                os.replace(temporary, self.repository.path)
                expected_ids = tuple(
                    str(item["id"])
                    for item in json.loads(prepared._candidate_bytes.decode("utf-8"))["records"]
                )
                restored_ids = tuple(
                    item.id for item in self.repository.list_records(include_archived=True)
                )
                if set(restored_ids) != set(expected_ids) or len(restored_ids) != len(expected_ids):
                    raise FinancialMigrationError("v3 readback validation failed")
            except Exception as exc:
                temporary.unlink(missing_ok=True)
                try:
                    self._write_fsynced(temporary, current)
                    os.replace(temporary, self.repository.path)
                except Exception as rollback_exc:
                    raise FinancialMigrationError(
                        f"migration failed and rollback failed: {rollback_exc}"
                    ) from exc
                if isinstance(exc, FinancialMigrationError):
                    raise
                raise FinancialMigrationError("migration failed; original bytes restored") from exc
            finally:
                temporary.unlink(missing_ok=True)

            target = self.repository.path.read_bytes()
            return BusinessMetricsMigrationResult(
                backup,
                prepared.source_sha256,
                hashlib.sha256(target).hexdigest(),
                prepared.record_count,
            )

    @staticmethod
    def _money(
        value: object,
        record_id: str,
        field_name: str,
        issues: list[BusinessMetricsMigrationIssue],
    ) -> Decimal | None:
        if isinstance(value, Decimal) and "E" in str(value).upper():
            parsed = None
        else:
            try:
                result = parse_money(value)
            except Exception:
                result = None
            parsed = result.amount if result is not None and result.is_available else None
        if parsed is None:
            issues.append(
                BusinessMetricsMigrationIssue(
                    record_id,
                    field_name,
                    "invalid_money",
                    "Money must be finite, non-negative fixed point with at most two decimals.",
                )
            )
        return parsed

    @staticmethod
    def _percentage(
        value: object,
        record_id: str,
        issues: list[BusinessMetricsMigrationIssue],
    ) -> Decimal | None:
        try:
            result = Decimal(str(value))
        except Exception:
            result = Decimal("NaN")
        if (
            not result.is_finite()
            or result < 0
            or result > Decimal("1000")
            or max(0, -result.as_tuple().exponent) > 2
        ):
            issues.append(
                BusinessMetricsMigrationIssue(
                    record_id,
                    "margin_percent",
                    "invalid_percentage",
                    "Margin must be finite percentage points with at most two decimals.",
                )
            )
            return None
        return result

    @staticmethod
    def _write_fsynced(path: Path, payload: bytes) -> None:
        with path.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())


__all__ = [
    "BusinessMetricsMigrationIssue",
    "BusinessMetricsMigrationPlan",
    "BusinessMetricsMigrationResult",
    "BusinessMetricsV3Migration",
]
