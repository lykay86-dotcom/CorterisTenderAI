"""Persistent business workflow metrics for Dashboard KPI.

The current application stores tenders and analyses in SQLAlchemy, while
commercial proposals, estimates and projects do not yet have ORM tables.
This repository provides an atomic JSON-backed workflow store until those
entities receive dedicated database models.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import json
import math
import os
from pathlib import Path
from threading import RLock
from typing import Any, Iterable
from uuid import uuid4

from app.config.settings import get_settings
from app.financial import (
    MARGIN_CONTRACT_VERSION,
    CurrencyCode,
    FinancialAnalyticsService,
    FinancialAnalyticsSnapshot,
    FinancialMetricId,
    FinancialMigrationError,
    FinancialValueState,
    MoneyAmount,
    WorkflowFinancialFact,
    canonical_money,
    canonical_percentage,
    derive_margin,
    parse_money,
    quantize_percentage,
)


_UNSET = object()


class BusinessRecordKind(StrEnum):
    ESTIMATE = "estimate"
    PROPOSAL = "proposal"
    PROJECT = "project"


class BusinessAuditAction(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    ARCHIVED = "archived"
    RESTORED = "restored"


class BusinessStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    READY = "ready"
    SENT = "sent"
    ACCEPTED = "accepted"
    PLANNED = "planned"
    ACTIVE = "active"
    INSTALLATION = "installation"
    COMMISSIONING = "commissioning"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class BusinessWorkflowRecord:
    id: str
    kind: str
    tender_id: str
    title: str
    status: str
    total: Decimal = Decimal("0.00")
    profit: Decimal = Decimal("0.00")
    margin_percent: Decimal = Decimal("0.00")
    currency: str = CurrencyCode.RUB.value
    margin_version: str = MARGIN_CONTRACT_VERSION
    file_path: str = ""
    due_date: str = ""
    created_at: str = ""
    updated_at: str = ""
    archived_at: str = ""

    def __post_init__(self) -> None:
        for field_name in ("total", "profit"):
            value = getattr(self, field_name)
            if isinstance(value, float):
                raise TypeError(f"{field_name} must not be binary float")
            parsed = parse_money(value)
            if not parsed.is_available or parsed.amount is None:
                raise ValueError(f"invalid {field_name}: {parsed.issue or parsed.state.value}")
            object.__setattr__(self, field_name, Decimal(canonical_money(parsed.amount)))
        if isinstance(self.margin_percent, float):
            raise TypeError("margin_percent must not be binary float")
        margin = Decimal(str(self.margin_percent))
        if not margin.is_finite() or margin < 0 or margin > Decimal("1000"):
            raise ValueError("invalid margin_percent")
        object.__setattr__(self, "margin_percent", quantize_percentage(margin))
        object.__setattr__(self, "currency", CurrencyCode(self.currency).value)
        if self.margin_version not in {MARGIN_CONTRACT_VERSION, "legacy-v2"}:
            raise ValueError("unsupported margin contract version")

    @property
    def is_archived(self) -> bool:
        return bool(self.archived_at.strip())


@dataclass(frozen=True, slots=True)
class BusinessAuditEvent:
    id: str
    record_id: str
    action: str
    occurred_at: str
    field: str = ""
    old_value: str = ""
    new_value: str = ""
    actor: str = "local_user"

    @property
    def timestamp(self) -> datetime:
        try:
            return BusinessMetricsRepository._aware_datetime(
                datetime.fromisoformat(self.occurred_at)
            )
        except ValueError:
            return BusinessMetricsRepository._aware_datetime(datetime.min)


@dataclass(frozen=True, slots=True)
class BusinessActivity:
    key: str
    title: str
    description: str
    timestamp: datetime
    tone: str
    action_key: str = ""


@dataclass(frozen=True, slots=True)
class BusinessMetricsSnapshot:
    proposals_in_work: int = 0
    estimates_in_work: int = 0
    active_projects: int = 0
    attention: int = 0
    potential_profit: Decimal = Decimal("0")
    profit_sources: int = 0
    recent_activities: tuple[BusinessActivity, ...] = ()
    record_count: int = 0
    proposal_ids: tuple[str, ...] = ()
    estimate_ids: tuple[str, ...] = ()
    project_ids: tuple[str, ...] = ()
    attention_ids: tuple[str, ...] = ()
    profit_contributor_ids: tuple[str, ...] = ()


class BusinessMetricsRepository:
    """Atomic JSON repository for estimates, proposals and projects."""

    SCHEMA_VERSION = 3

    PROPOSAL_IN_WORK = {
        BusinessStatus.DRAFT,
        BusinessStatus.REVIEW,
        BusinessStatus.READY,
        BusinessStatus.SENT,
    }
    ESTIMATE_IN_WORK = {
        BusinessStatus.DRAFT,
        BusinessStatus.REVIEW,
    }
    ACTIVE_PROJECTS = {
        BusinessStatus.PLANNED,
        BusinessStatus.ACTIVE,
        BusinessStatus.INSTALLATION,
        BusinessStatus.COMMISSIONING,
    }

    def __init__(self, path: Path | None = None) -> None:
        self.path = (
            Path(path) if path is not None else get_settings().data_dir / "business_workflow.json"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def list_records(
        self,
        *,
        kind: BusinessRecordKind | str | None = None,
        include_archived: bool = False,
        archived_only: bool = False,
    ) -> list[BusinessWorkflowRecord]:
        """List records with explicit archive visibility control."""
        normalized_kind = BusinessRecordKind(kind).value if kind is not None else None
        records = self._read_records()

        if archived_only:
            records = [record for record in records if record.is_archived]
        elif not include_archived:
            records = [record for record in records if not record.is_archived]

        if normalized_kind is None:
            return records
        return [record for record in records if record.kind == normalized_kind]

    def get_record(
        self,
        record_id: str,
    ) -> BusinessWorkflowRecord | None:
        """Return one workflow record by its stable UUID."""
        return next(
            (record for record in self._read_records() if record.id == record_id),
            None,
        )

    def list_history(
        self,
        record_id: str,
        *,
        limit: int | None = None,
    ) -> list[BusinessAuditEvent]:
        """Return newest audit events for one workflow record."""
        with self._lock:
            events = [
                event for event in self._read_events_unlocked() if event.record_id == record_id
            ]

        events.sort(
            key=lambda event: event.timestamp,
            reverse=True,
        )
        if limit is None:
            return events
        return events[: max(0, int(limit))]

    def snapshot_payload(self) -> dict[str, Any]:
        """Return an isolated JSON-compatible copy of the full store."""
        with self._lock:
            payload = self._read_payload_unlocked()
            return self._json_compatible(payload)

    @property
    def requires_migration(self) -> bool:
        with self._lock:
            payload = self._read_payload_unlocked()
            return int(payload.get("schema_version", self.SCHEMA_VERSION)) < self.SCHEMA_VERSION

    def replace_payload(self, payload: dict[str, Any]) -> None:
        """Atomically replace the store with a validated snapshot."""
        if not isinstance(payload, dict):
            raise TypeError("Снимок бизнес-процессов должен быть объектом")

        with self._lock:
            temporary = self.path.with_suffix(self.path.suffix + ".restore.tmp")
            try:
                candidate = self._json_compatible(payload)
                schema = int(candidate.get("schema_version", 1))
                if schema > self.SCHEMA_VERSION:
                    raise ValueError(f"unsupported workflow schema: {schema}")
                self._write_json_fsynced(temporary, candidate)
                readback = json.loads(
                    temporary.read_text(encoding="utf-8"),
                    parse_float=Decimal,
                    parse_int=Decimal,
                )
                if (
                    not isinstance(readback, dict)
                    or int(readback.get("schema_version", 1)) != schema
                ):
                    raise ValueError("workflow snapshot readback validation failed")
                os.replace(temporary, self.path)
            finally:
                temporary.unlink(missing_ok=True)

    def save_record(
        self,
        *,
        kind: BusinessRecordKind | str,
        tender_id: str | int,
        title: str,
        status: BusinessStatus | str,
        total: float | Decimal | int | str = 0,
        profit: float | Decimal | int | str = 0,
        margin_percent: float | Decimal | int | str = 0,
        file_path: str | Path = "",
        due_date: str = "",
    ) -> BusinessWorkflowRecord:
        """Create or update one generic business workflow record."""
        return self._upsert(
            kind=kind,
            tender_id=tender_id,
            title=title,
            status=status,
            total=self._number(total),
            profit=self._number(profit),
            margin_percent=self._percentage(margin_percent),
            file_path=str(file_path),
            due_date=due_date,
        )

    def record_estimate(
        self,
        tender_id: str | int,
        estimate: dict[str, Any],
        *,
        status: BusinessStatus | str = BusinessStatus.DRAFT,
        title: str = "Смета",
        due_date: str = "",
    ) -> BusinessWorkflowRecord:
        total = self._number(
            estimate.get(
                "total",
                estimate.get(
                    "gross",
                    estimate.get("price_with_vat", 0),
                ),
            )
        )
        profit = self._number(estimate.get("profit", 0))
        margin = self._percentage(
            estimate.get(
                "margin_percent",
                estimate.get("margin", 0),
            )
        )
        return self._upsert(
            kind=BusinessRecordKind.ESTIMATE,
            tender_id=tender_id,
            title=title,
            status=status,
            total=total,
            profit=profit,
            margin_percent=margin,
            due_date=due_date,
        )

    def record_proposal(
        self,
        tender_id: str | int,
        *,
        file_path: str | Path = "",
        total: float | Decimal | int | str = 0,
        profit: float | Decimal | int | str = 0,
        status: BusinessStatus | str = BusinessStatus.READY,
        title: str = "Коммерческое предложение",
        due_date: str = "",
    ) -> BusinessWorkflowRecord:
        return self._upsert(
            kind=BusinessRecordKind.PROPOSAL,
            tender_id=tender_id,
            title=title,
            status=status,
            total=self._number(total),
            profit=self._number(profit),
            file_path=str(file_path),
            due_date=due_date,
        )

    def record_project(
        self,
        tender_id: str | int,
        *,
        title: str,
        status: BusinessStatus | str = BusinessStatus.PLANNED,
        total: float | Decimal | int | str = 0,
        expected_profit: float | Decimal | int | str = 0,
        due_date: str = "",
    ) -> BusinessWorkflowRecord:
        return self._upsert(
            kind=BusinessRecordKind.PROJECT,
            tender_id=tender_id,
            title=title,
            status=status,
            total=self._number(total),
            profit=self._number(expected_profit),
            due_date=due_date,
        )

    def update_record(
        self,
        record_id: str,
        *,
        title: Any = _UNSET,
        total: Any = _UNSET,
        profit: Any = _UNSET,
        margin_percent: Any = _UNSET,
        file_path: Any = _UNSET,
        due_date: Any = _UNSET,
    ) -> BusinessWorkflowRecord:
        """Edit mutable record fields while preserving identity and status."""
        with self._lock:
            records = self._read_records_unlocked()
            existing = next(
                (record for record in records if record.id == record_id),
                None,
            )
            if existing is None:
                raise KeyError(record_id)
            if existing.is_archived:
                raise ValueError("Архивную запись нужно сначала восстановить")

            next_title = existing.title if title is _UNSET else str(title).strip()
            if not next_title:
                raise ValueError("Наименование не может быть пустым")

            next_total = existing.total if total is _UNSET else self._number(total)
            next_profit = existing.profit if profit is _UNSET else self._number(profit)
            next_margin = (
                existing.margin_percent
                if margin_percent is _UNSET
                else self._percentage(margin_percent)
            )
            next_file = existing.file_path if file_path is _UNSET else str(file_path).strip()
            next_due = existing.due_date if due_date is _UNSET else str(due_date).strip()

            if next_total < 0:
                raise ValueError("Сумма не может быть отрицательной")
            if next_profit < 0:
                raise ValueError("Прибыль не может быть отрицательной")

            updated = BusinessWorkflowRecord(
                **{
                    **asdict(existing),
                    "title": next_title,
                    "total": next_total,
                    "profit": next_profit,
                    "margin_percent": self._derived_margin(next_total, next_profit, next_margin),
                    "file_path": next_file,
                    "due_date": next_due,
                    "updated_at": self._now_text(),
                }
            )

            result = [updated if record.id == record_id else record for record in records]
            events = self._field_change_events(
                existing,
                updated,
                fields=(
                    "title",
                    "total",
                    "profit",
                    "margin_percent",
                    "file_path",
                    "due_date",
                ),
                occurred_at=updated.updated_at,
            )
            self._write_records_with_events_unlocked(
                result,
                events,
            )
            return updated

    def update_status(
        self,
        record_id: str,
        status: BusinessStatus | str,
    ) -> BusinessWorkflowRecord:
        normalized_status = BusinessStatus(status).value
        with self._lock:
            records = self._read_records_unlocked()
            existing: BusinessWorkflowRecord | None = None
            updated: BusinessWorkflowRecord | None = None
            now = self._now_text()

            result: list[BusinessWorkflowRecord] = []
            for record in records:
                if record.id == record_id:
                    existing = record
                    updated = BusinessWorkflowRecord(
                        **{
                            **asdict(record),
                            "status": normalized_status,
                            "updated_at": now,
                        }
                    )
                    result.append(updated)
                else:
                    result.append(record)

            if updated is None:
                raise KeyError(record_id)
            if updated.is_archived:
                raise ValueError("Нельзя изменять статус архивной записи")

            event = self._new_event(
                record_id=record_id,
                action=BusinessAuditAction.STATUS_CHANGED,
                field="status",
                old_value=existing.status if existing else "",
                new_value=updated.status,
                occurred_at=now,
            )
            self._write_records_with_events_unlocked(
                result,
                [event],
            )
            return updated

    def archive_record(
        self,
        record_id: str,
    ) -> BusinessWorkflowRecord:
        """Soft-delete a workflow record without losing its history."""
        return self._set_archive_state(
            record_id,
            archived=True,
        )

    def restore_record(
        self,
        record_id: str,
    ) -> BusinessWorkflowRecord:
        """Restore a previously archived workflow record."""
        return self._set_archive_state(
            record_id,
            archived=False,
        )

    def _set_archive_state(
        self,
        record_id: str,
        *,
        archived: bool,
    ) -> BusinessWorkflowRecord:
        with self._lock:
            records = self._read_records_unlocked()
            existing = next(
                (record for record in records if record.id == record_id),
                None,
            )
            if existing is None:
                raise KeyError(record_id)

            now = self._now_text()
            updated = BusinessWorkflowRecord(
                **{
                    **asdict(existing),
                    "archived_at": now if archived else "",
                    "updated_at": now,
                }
            )
            result = [updated if record.id == record_id else record for record in records]
            event = self._new_event(
                record_id=record_id,
                action=(BusinessAuditAction.ARCHIVED if archived else BusinessAuditAction.RESTORED),
                field="archived_at",
                old_value=existing.archived_at,
                new_value=updated.archived_at,
                occurred_at=now,
            )
            self._write_records_with_events_unlocked(
                result,
                [event],
            )
            return updated

    def summary(
        self,
        *,
        today: date | None = None,
        activity_limit: int = 6,
    ) -> BusinessMetricsSnapshot:
        records = [record for record in self._read_records() if not record.is_archived]
        current_date = today or date.today()

        proposals = [
            record
            for record in records
            if (
                record.kind == BusinessRecordKind.PROPOSAL.value
                and self._status(record) in self.PROPOSAL_IN_WORK
            )
        ]
        estimates = [
            record
            for record in records
            if (
                record.kind == BusinessRecordKind.ESTIMATE.value
                and self._status(record) in self.ESTIMATE_IN_WORK
            )
        ]
        projects = [
            record
            for record in records
            if (
                record.kind == BusinessRecordKind.PROJECT.value
                and self._status(record) in self.ACTIVE_PROJECTS
            )
        ]

        attention = [record for record in records if self._requires_attention(record, current_date)]
        financial = self._financial_snapshot(records)
        profit_metric = financial.metric(FinancialMetricId.POTENTIAL_PROFIT)
        potential_profit = profit_metric.exact_value or Decimal("0.00")
        record_by_id = {record.id: record for record in records}
        profit_contributors = tuple(
            record_by_id[record_id]
            for record_id in profit_metric.contributor_ids
            if record_id in record_by_id
        )
        activities = tuple(
            self._activity(record)
            for record in sorted(
                records,
                key=self._updated_at,
                reverse=True,
            )[: max(0, int(activity_limit))]
        )

        return BusinessMetricsSnapshot(
            proposals_in_work=len(proposals),
            estimates_in_work=len(estimates),
            active_projects=len(projects),
            attention=len(attention),
            potential_profit=potential_profit,
            profit_sources=len(profit_contributors),
            recent_activities=activities,
            record_count=len(records),
            proposal_ids=tuple(record.id for record in proposals),
            estimate_ids=tuple(record.id for record in estimates),
            project_ids=tuple(record.id for record in projects),
            attention_ids=tuple(record.id for record in attention),
            profit_contributor_ids=tuple(record.id for record in profit_contributors),
        )

    def financial_snapshot(
        self,
        *,
        generated_at: datetime | None = None,
    ) -> FinancialAnalyticsSnapshot:
        """Return the immutable financial source for KPIs, charts and exports."""
        records = [record for record in self._read_records() if not record.is_archived]
        return self._financial_snapshot(records, generated_at=generated_at)

    def _financial_snapshot(
        self,
        records: Iterable[BusinessWorkflowRecord],
        *,
        generated_at: datetime | None = None,
    ) -> FinancialAnalyticsSnapshot:
        facts = tuple(
            WorkflowFinancialFact(
                record_id=record.id,
                tender_id=record.tender_id,
                kind=record.kind,
                status=record.status,
                total=MoneyAmount(record.total, CurrencyCode(record.currency)),
                profit=MoneyAmount(record.profit, CurrencyCode(record.currency)),
                created_at=self._record_datetime(record.created_at),
                archived=record.is_archived,
            )
            for record in records
        )
        return FinancialAnalyticsService().build(
            facts,
            generated_at=generated_at or datetime.now().astimezone(),
        )

    def _upsert(
        self,
        *,
        kind: BusinessRecordKind | str,
        tender_id: str | int,
        title: str,
        status: BusinessStatus | str,
        total: Decimal,
        profit: Decimal,
        margin_percent: Decimal = Decimal("0.00"),
        file_path: str = "",
        due_date: str = "",
    ) -> BusinessWorkflowRecord:
        normalized_kind = BusinessRecordKind(kind).value
        normalized_status = BusinessStatus(status).value
        normalized_tender_id = str(tender_id)
        now = self._now_text()

        with self._lock:
            records = self._read_records_unlocked()
            existing = next(
                (
                    record
                    for record in records
                    if (
                        record.kind == normalized_kind
                        and record.tender_id == normalized_tender_id
                        and not record.is_archived
                    )
                ),
                None,
            )

            record = BusinessWorkflowRecord(
                id=existing.id if existing else str(uuid4()),
                kind=normalized_kind,
                tender_id=normalized_tender_id,
                title=title.strip() or normalized_kind,
                status=normalized_status,
                total=total,
                profit=profit,
                margin_percent=self._derived_margin(total, profit, margin_percent),
                currency=CurrencyCode.RUB.value,
                margin_version=MARGIN_CONTRACT_VERSION,
                file_path=file_path,
                due_date=due_date.strip(),
                created_at=existing.created_at if existing else now,
                updated_at=now,
                archived_at=existing.archived_at if existing else "",
            )

            result = [item for item in records if item.id != record.id]
            result.append(record)

            if existing is None:
                events = [
                    self._new_event(
                        record_id=record.id,
                        action=BusinessAuditAction.CREATED,
                        new_value=record.title,
                        occurred_at=now,
                    )
                ]
            else:
                events = self._field_change_events(
                    existing,
                    record,
                    fields=(
                        "title",
                        "status",
                        "total",
                        "profit",
                        "margin_percent",
                        "file_path",
                        "due_date",
                    ),
                    occurred_at=now,
                )

            self._write_records_with_events_unlocked(
                result,
                events,
            )
            return record

    def _read_records(self) -> list[BusinessWorkflowRecord]:
        with self._lock:
            return self._read_records_unlocked()

    def _read_payload_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": self.SCHEMA_VERSION,
                "records": [],
                "events": [],
            }

        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8"),
                parse_float=Decimal,
                parse_int=Decimal,
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise FinancialMigrationError(
                "workflow store is unreadable; original bytes preserved"
            ) from exc

        if not isinstance(payload, dict):
            raise FinancialMigrationError("workflow payload must be an object")

        payload.setdefault("records", [])
        payload.setdefault("events", [])
        schema = int(payload.get("schema_version", 1))
        if schema > self.SCHEMA_VERSION:
            raise ValueError(f"unsupported workflow schema: {schema}")
        return payload

    def _read_records_unlocked(self) -> list[BusinessWorkflowRecord]:
        payload = self._read_payload_unlocked()
        schema = int(payload.get("schema_version", 1))
        result: list[BusinessWorkflowRecord] = []

        for raw in payload.get("records", []):
            if not isinstance(raw, dict):
                continue
            try:
                values = dict(raw)
                values["total"] = self._number(values.get("total", 0))
                values["profit"] = self._number(values.get("profit", 0))
                values["margin_percent"] = self._percentage(values.get("margin_percent", 0))
                values["currency"] = (
                    str(values.get("currency", CurrencyCode.RUB.value))
                    if schema >= self.SCHEMA_VERSION
                    else CurrencyCode.RUB.value
                )
                values["margin_version"] = (
                    str(values.get("margin_version", MARGIN_CONTRACT_VERSION))
                    if schema >= self.SCHEMA_VERSION
                    else "legacy-v2"
                )
                result.append(BusinessWorkflowRecord(**values))
            except (TypeError, ValueError) as exc:
                raise FinancialMigrationError(
                    f"workflow record {values.get('id', '<unknown>')} is invalid"
                ) from exc
        return result

    def _read_events_unlocked(self) -> list[BusinessAuditEvent]:
        payload = self._read_payload_unlocked()
        result: list[BusinessAuditEvent] = []

        for raw in payload.get("events", []):
            if not isinstance(raw, dict):
                continue
            try:
                result.append(BusinessAuditEvent(**raw))
            except (TypeError, ValueError):
                continue
        return result

    def _write_records_unlocked(
        self,
        records: Iterable[BusinessWorkflowRecord],
    ) -> None:
        self._write_state_unlocked(
            records,
            self._read_events_unlocked(),
        )

    def _write_records_with_events_unlocked(
        self,
        records: Iterable[BusinessWorkflowRecord],
        new_events: Iterable[BusinessAuditEvent],
    ) -> None:
        events = self._read_events_unlocked()
        events.extend(new_events)
        self._write_state_unlocked(records, events)

    def _write_state_unlocked(
        self,
        records: Iterable[BusinessWorkflowRecord],
        events: Iterable[BusinessAuditEvent],
    ) -> None:
        self._ensure_current_schema_unlocked()
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "updated_at": self._now_text(),
            "records": [self._record_payload(record) for record in records],
            "events": [asdict(event) for event in events],
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        self._write_json_fsynced(temporary, payload)
        os.replace(temporary, self.path)

    def _field_change_events(
        self,
        before: BusinessWorkflowRecord,
        after: BusinessWorkflowRecord,
        *,
        fields: Iterable[str],
        occurred_at: str,
    ) -> list[BusinessAuditEvent]:
        events: list[BusinessAuditEvent] = []
        for field in fields:
            old_value = getattr(before, field)
            new_value = getattr(after, field)
            if old_value == new_value:
                continue

            action = (
                BusinessAuditAction.STATUS_CHANGED
                if field == "status"
                else BusinessAuditAction.UPDATED
            )
            events.append(
                self._new_event(
                    record_id=after.id,
                    action=action,
                    field=field,
                    old_value=old_value,
                    new_value=new_value,
                    occurred_at=occurred_at,
                )
            )
        return events

    @staticmethod
    def _new_event(
        *,
        record_id: str,
        action: BusinessAuditAction | str,
        field: str = "",
        old_value: Any = "",
        new_value: Any = "",
        occurred_at: str | None = None,
    ) -> BusinessAuditEvent:
        return BusinessAuditEvent(
            id=str(uuid4()),
            record_id=record_id,
            action=BusinessAuditAction(action).value,
            occurred_at=(occurred_at or BusinessMetricsRepository._now_text()),
            field=field,
            old_value=BusinessMetricsRepository._audit_value(old_value),
            new_value=BusinessMetricsRepository._audit_value(new_value),
        )

    @staticmethod
    def _audit_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, Decimal):
            return format(value, ".2f")
        return str(value)

    def _requires_attention(
        self,
        record: BusinessWorkflowRecord,
        today: date,
    ) -> bool:
        status = self._status(record)
        if status == BusinessStatus.BLOCKED:
            return True
        if not record.due_date:
            return False

        try:
            due = date.fromisoformat(record.due_date)
        except ValueError:
            try:
                due = datetime.strptime(
                    record.due_date,
                    "%d.%m.%Y",
                ).date()
            except ValueError:
                return False

        days = (due - today).days
        return 0 <= days <= 3

    def _activity(
        self,
        record: BusinessWorkflowRecord,
    ) -> BusinessActivity:
        labels = {
            BusinessRecordKind.ESTIMATE.value: "Смета",
            BusinessRecordKind.PROPOSAL.value: "Коммерческое предложение",
            BusinessRecordKind.PROJECT.value: "Проект",
        }
        tone = (
            "warning"
            if self._status(record) in {BusinessStatus.BLOCKED, BusinessStatus.REVIEW}
            else "success"
            if self._status(record)
            in {
                BusinessStatus.APPROVED,
                BusinessStatus.READY,
                BusinessStatus.ACTIVE,
                BusinessStatus.INSTALLATION,
            }
            else "neutral"
        )
        return BusinessActivity(
            key=f"business-{record.id}",
            title=f"{labels.get(record.kind, record.kind)}: {record.title}",
            description=(f"Тендер {record.tender_id} · статус {record.status}"),
            timestamp=self._updated_at(record),
            tone=tone,
            action_key=f"open_tender_id:{record.tender_id}",
        )

    @staticmethod
    def _number(value: Any) -> Decimal:
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("financial value must be finite")
            value = Decimal(str(value))
        parsed = parse_money(value)
        if not parsed.is_available or parsed.amount is None:
            raise ValueError(f"invalid financial value: {parsed.issue or parsed.state.value}")
        return Decimal(canonical_money(parsed.amount))

    @staticmethod
    def _percentage(value: Any) -> Decimal:
        try:
            parsed = Decimal(str(value if value not in {None, ""} else 0))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("invalid percentage value") from exc
        if not parsed.is_finite() or parsed < 0 or parsed > Decimal("1000"):
            raise ValueError("percentage value is out of range")
        if max(0, -parsed.as_tuple().exponent) > 2:
            raise ValueError("percentage has more than two fractional digits")
        return quantize_percentage(parsed)

    @staticmethod
    def _derived_margin(total: Decimal, profit: Decimal, supplied: Decimal) -> Decimal:
        del supplied  # Legacy/manual margin is evidence, never an authoritative operand.
        derived = derive_margin(MoneyAmount(total), MoneyAmount(profit))
        if derived.state is FinancialValueState.AVAILABLE and derived.value is not None:
            return quantize_percentage(derived.value)
        return Decimal("0.00")

    def _ensure_current_schema_unlocked(self) -> None:
        if not self.path.exists():
            return
        payload = self._read_payload_unlocked()
        schema = int(payload.get("schema_version", 1))
        if schema < self.SCHEMA_VERSION:
            raise FinancialMigrationError(
                f"workflow schema {schema} requires controlled migration to {self.SCHEMA_VERSION}"
            )

    @staticmethod
    def _now_text() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    @staticmethod
    def _aware_datetime(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return value

    @classmethod
    def _record_datetime(cls, value: str) -> datetime | None:
        if not value.strip():
            return None
        try:
            return cls._aware_datetime(datetime.fromisoformat(value))
        except ValueError:
            return None

    @classmethod
    def _write_json_fsynced(cls, path: Path, payload: dict[str, Any]) -> None:
        encoded = json.dumps(
            cls._json_compatible(payload),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        with path.open("wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _record_payload(record: BusinessWorkflowRecord) -> dict[str, Any]:
        payload = asdict(record)
        payload["total"] = canonical_money(record.total)
        payload["profit"] = canonical_money(record.profit)
        payload["margin_percent"] = canonical_percentage(record.margin_percent)
        payload["currency"] = record.currency
        payload["margin_version"] = record.margin_version
        return payload

    @classmethod
    def _json_compatible(cls, value: Any) -> Any:
        if isinstance(value, Decimal):
            return int(value) if value == value.to_integral_value() else float(value)
        if isinstance(value, dict):
            return {str(key): cls._json_compatible(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._json_compatible(item) for item in value]
        return value

    @staticmethod
    def _status(
        record: BusinessWorkflowRecord,
    ) -> BusinessStatus:
        try:
            return BusinessStatus(record.status)
        except ValueError:
            return BusinessStatus.DRAFT

    @staticmethod
    def _updated_at(
        record: BusinessWorkflowRecord,
    ) -> datetime:
        try:
            return BusinessMetricsRepository._aware_datetime(
                datetime.fromisoformat(record.updated_at)
            )
        except ValueError:
            return BusinessMetricsRepository._aware_datetime(datetime.min)


__all__ = [
    "BusinessActivity",
    "BusinessAuditAction",
    "BusinessAuditEvent",
    "BusinessMetricsRepository",
    "BusinessMetricsSnapshot",
    "BusinessRecordKind",
    "BusinessStatus",
    "BusinessWorkflowRecord",
]
