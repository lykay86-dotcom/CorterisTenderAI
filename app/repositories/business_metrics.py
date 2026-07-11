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


class BusinessRecordKind(StrEnum):
    ESTIMATE = "estimate"
    PROPOSAL = "proposal"
    PROJECT = "project"


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

    SCHEMA_VERSION = 1

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
            Path(path)
            if path is not None
            else get_settings().data_dir / "business_workflow.json"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def list_records(
        self,
        *,
        kind: BusinessRecordKind | str | None = None,
    ) -> list[BusinessWorkflowRecord]:
        normalized_kind = (
            BusinessRecordKind(kind).value
            if kind is not None
            else None
        )
        records = self._read_records()
        if normalized_kind is None:
            return records
        return [
            record
            for record in records
            if record.kind == normalized_kind
        ]

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

    def update_status(
        self,
        record_id: str,
        status: BusinessStatus | str,
    ) -> BusinessWorkflowRecord:
        normalized_status = BusinessStatus(status).value
        with self._lock:
            records = self._read_records_unlocked()
            updated: BusinessWorkflowRecord | None = None
            now = datetime.now().isoformat(timespec="seconds")

            result: list[BusinessWorkflowRecord] = []
            for record in records:
                if record.id == record_id:
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

            self._write_records_unlocked(result)
            return updated

    def summary(
        self,
        *,
        today: date | None = None,
        activity_limit: int = 6,
    ) -> BusinessMetricsSnapshot:
        records = self._read_records()
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

        attention = sum(
            1
            for record in records
            if self._requires_attention(record, current_date)
        )
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
            )

            result = [
                item
                for item in records
                if item.id != record.id
            ]
            result.append(record)
            self._write_records_unlocked(result)
            return record

    def _read_records(self) -> list[BusinessWorkflowRecord]:
        with self._lock:
            return self._read_records_unlocked()

    def _read_records_unlocked(self) -> list[BusinessWorkflowRecord]:
        if not self.path.exists():
            return []

        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return []

        raw_records = payload.get("records", [])
        result: list[BusinessWorkflowRecord] = []
        for raw in raw_records:
            try:
                result.append(BusinessWorkflowRecord(**raw))
            except (TypeError, ValueError):
                continue
        return result

    def _write_records_unlocked(
        self,
        records: Iterable[BusinessWorkflowRecord],
    ) -> None:
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "records": [asdict(record) for record in records],
        }
        temporary = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )
        temporary.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)

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
            if self._status(record)
            in {BusinessStatus.BLOCKED, BusinessStatus.REVIEW}
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
            description=(
                f"Тендер {record.tender_id} · "
                f"статус {record.status}"
            ),
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
    "BusinessMetricsRepository",
    "BusinessMetricsSnapshot",
    "BusinessRecordKind",
    "BusinessStatus",
    "BusinessWorkflowRecord",
]
