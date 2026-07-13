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
from pathlib import Path
from threading import RLock
from typing import Any, Iterable
from uuid import uuid4

from app.config.settings import get_settings


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
    total: float = 0.0
    profit: float = 0.0
    margin_percent: float = 0.0
    file_path: str = ""
    due_date: str = ""
    created_at: str = ""
    updated_at: str = ""
    archived_at: str = ""

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
            return datetime.fromisoformat(self.occurred_at)
        except ValueError:
            return datetime.min


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


class BusinessMetricsRepository:
    """Atomic JSON repository for estimates, proposals and projects."""

    SCHEMA_VERSION = 2

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
            return json.loads(json.dumps(payload, ensure_ascii=False))

    def replace_payload(self, payload: dict[str, Any]) -> None:
        """Atomically replace the store with a validated snapshot."""
        if not isinstance(payload, dict):
            raise TypeError("Снимок бизнес-процессов должен быть объектом")

        with self._lock:
            temporary = self.path.with_suffix(self.path.suffix + ".restore.tmp")
            try:
                temporary.write_text(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                temporary.replace(self.path)
            finally:
                temporary.unlink(missing_ok=True)

    def save_record(
        self,
        *,
        kind: BusinessRecordKind | str,
        tender_id: str | int,
        title: str,
        status: BusinessStatus | str,
        total: float | Decimal = 0,
        profit: float | Decimal = 0,
        margin_percent: float | Decimal = 0,
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
            margin_percent=self._number(margin_percent),
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
        margin = self._number(
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
        total: float | Decimal = 0,
        profit: float | Decimal = 0,
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
        total: float | Decimal = 0,
        expected_profit: float | Decimal = 0,
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
                else self._number(margin_percent)
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
                    "total": float(next_total),
                    "profit": float(next_profit),
                    "margin_percent": float(next_margin),
                    "file_path": next_file,
                    "due_date": next_due,
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
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
            now = datetime.now().isoformat(timespec="seconds")

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

            now = datetime.now().isoformat(timespec="seconds")
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

        attention = sum(1 for record in records if self._requires_attention(record, current_date))
        potential_profit, sources = self._potential_profit(records)
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
            attention=attention,
            potential_profit=potential_profit,
            profit_sources=sources,
            recent_activities=activities,
            record_count=len(records),
        )

    def _upsert(
        self,
        *,
        kind: BusinessRecordKind | str,
        tender_id: str | int,
        title: str,
        status: BusinessStatus | str,
        total: float,
        profit: float,
        margin_percent: float = 0,
        file_path: str = "",
        due_date: str = "",
    ) -> BusinessWorkflowRecord:
        normalized_kind = BusinessRecordKind(kind).value
        normalized_status = BusinessStatus(status).value
        normalized_tender_id = str(tender_id)
        now = datetime.now().isoformat(timespec="seconds")

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
                total=float(total),
                profit=float(profit),
                margin_percent=float(margin_percent),
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
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "schema_version": self.SCHEMA_VERSION,
                "records": [],
                "events": [],
            }

        if not isinstance(payload, dict):
            return {
                "schema_version": self.SCHEMA_VERSION,
                "records": [],
                "events": [],
            }

        payload.setdefault("records", [])
        payload.setdefault("events", [])
        return payload

    def _read_records_unlocked(self) -> list[BusinessWorkflowRecord]:
        payload = self._read_payload_unlocked()
        result: list[BusinessWorkflowRecord] = []

        for raw in payload.get("records", []):
            if not isinstance(raw, dict):
                continue
            try:
                result.append(BusinessWorkflowRecord(**raw))
            except (TypeError, ValueError):
                continue
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
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "records": [asdict(record) for record in records],
            "events": [asdict(event) for event in events],
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)

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
            occurred_at=(occurred_at or datetime.now().isoformat(timespec="seconds")),
            field=field,
            old_value=BusinessMetricsRepository._audit_value(old_value),
            new_value=BusinessMetricsRepository._audit_value(new_value),
        )

    @staticmethod
    def _audit_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, Decimal):
            return format(value, "f")
        return str(value)

    def _potential_profit(
        self,
        records: list[BusinessWorkflowRecord],
    ) -> tuple[Decimal, int]:
        by_tender: dict[str, BusinessWorkflowRecord] = {}

        for record in sorted(
            records,
            key=self._updated_at,
            reverse=True,
        ):
            status = self._status(record)
            if status in {
                BusinessStatus.CANCELLED,
                BusinessStatus.COMPLETED,
            }:
                continue
            if record.profit <= 0:
                continue

            current = by_tender.get(record.tender_id)
            if current is None:
                by_tender[record.tender_id] = record
                continue

            # Active project profit has priority over an estimate/proposal.
            if (
                record.kind == BusinessRecordKind.PROJECT.value
                and current.kind != BusinessRecordKind.PROJECT.value
            ):
                by_tender[record.tender_id] = record

        total = sum(
            (Decimal(str(record.profit)) for record in by_tender.values()),
            Decimal("0"),
        )
        return total, len(by_tender)

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
    def _number(value: Any) -> float:
        try:
            return float(Decimal(str(value or 0)))
        except (InvalidOperation, TypeError, ValueError):
            return 0.0

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
            return datetime.fromisoformat(record.updated_at)
        except ValueError:
            return datetime.min


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
