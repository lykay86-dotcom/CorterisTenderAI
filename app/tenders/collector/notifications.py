"""Persistent in-application notifications for collector runs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
import hashlib
import json
from pathlib import Path
from threading import RLock
from typing import Iterable, Mapping
from uuid import uuid4

from app.tenders.collector.models import (
    CollectionRunStatus,
    CollectorRunResult,
)
from app.tenders.collector.scheduler import (
    CollectorScheduleSettings,
)


class CollectorNotificationKind(StrEnum):
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class CollectorNotification:
    id: str
    created_at: str
    title: str
    message: str
    kind: CollectorNotificationKind
    read: bool = False
    run_id: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("notification id must not be empty")
        if not self.title.strip():
            raise ValueError("notification title must not be empty")
        if not self.message.strip():
            raise ValueError("notification message must not be empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "title": self.title,
            "message": self.message,
            "kind": self.kind.value,
            "read": self.read,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "CollectorNotification":
        return cls(
            id=str(payload.get("id", "")),
            created_at=str(payload.get("created_at", "")),
            title=str(payload.get("title", "")),
            message=str(payload.get("message", "")),
            kind=CollectorNotificationKind(str(payload.get("kind", "info"))),
            read=bool(payload.get("read", False)),
            run_id=str(payload.get("run_id", "")),
        )


class CollectorNotificationRepository:
    """Atomic capped JSON notification history."""

    SCHEMA_VERSION = 1

    def __init__(
        self,
        path: str | Path,
        *,
        max_items: int = 200,
    ) -> None:
        if max_items < 1:
            raise ValueError("max_items must be positive")
        self.path = Path(path).expanduser()
        self.max_items = int(max_items)
        self._lock = RLock()

    def list_notifications(
        self,
        *,
        unread_only: bool = False,
    ) -> tuple[CollectorNotification, ...]:
        with self._lock:
            items = self._load_unlocked()
        if unread_only:
            items = [item for item in items if not item.read]
        return tuple(items)

    def unread_count(self) -> int:
        return len(self.list_notifications(unread_only=True))

    def add_many(
        self,
        notifications: Iterable[CollectorNotification],
    ) -> tuple[CollectorNotification, ...]:
        incoming = tuple(notifications)
        if not incoming:
            return ()
        with self._lock:
            existing = {item.id: item for item in self._load_unlocked()}
            for item in incoming:
                existing[item.id] = item
            ordered = sorted(
                existing.values(),
                key=lambda item: item.created_at,
                reverse=True,
            )[: self.max_items]
            self._write_unlocked(ordered)
        return incoming

    def mark_all_read(self) -> int:
        with self._lock:
            items = self._load_unlocked()
            unread = sum(not item.read for item in items)
            if unread:
                items = [replace(item, read=True) for item in items]
                self._write_unlocked(items)
            return unread

    def clear(self) -> None:
        with self._lock:
            self._write_unlocked([])

    def _load_unlocked(
        self,
    ) -> list[CollectorNotification]:
        if not self.path.is_file():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (
            OSError,
            TypeError,
            json.JSONDecodeError,
        ):
            return []
        raw_items = payload.get("notifications", []) if isinstance(payload, dict) else []
        if not isinstance(raw_items, list):
            return []
        result: list[CollectorNotification] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            try:
                result.append(CollectorNotification.from_dict(raw))
            except (ValueError, TypeError):
                continue
        return result

    def _write_unlocked(
        self,
        items: Iterable[CollectorNotification],
    ) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "schema_version": self.SCHEMA_VERSION,
                    "notifications": [item.to_dict() for item in items],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)


class CollectorNotificationService:
    """Build explainable notifications from run results."""

    def for_result(
        self,
        result: CollectorRunResult,
        settings: CollectorScheduleSettings,
    ) -> tuple[CollectorNotification, ...]:
        created_at = _now_iso()
        run_id = result.run_id
        items: list[CollectorNotification] = []
        summary = result.persistence

        high_score_count = int(result.metadata.get("high_score_count", 0) or 0)
        if settings.notify_new and high_score_count:
            items.append(
                CollectorNotification(
                    id=f"{run_id}:high-score",
                    created_at=created_at,
                    title="Тендеры с высокой оценкой",
                    message=(f"{high_score_count} тендеров имеют оценку участия 80 баллов и выше."),
                    kind=CollectorNotificationKind.SUCCESS,
                    run_id=run_id,
                )
            )

        if settings.notify_new and summary.new_count:
            items.append(
                CollectorNotification(
                    id=f"{run_id}:new",
                    created_at=created_at,
                    title="Новые тендеры",
                    message=(f"Найдено {summary.new_count} новых тендеров."),
                    kind=CollectorNotificationKind.SUCCESS,
                    run_id=run_id,
                )
            )

        if settings.notify_changed and summary.changed_count:
            items.append(
                CollectorNotification(
                    id=f"{run_id}:changed",
                    created_at=created_at,
                    title="Тендеры изменены",
                    message=(f"Изменения обнаружены у {summary.changed_count} тендеров."),
                    kind=CollectorNotificationKind.INFO,
                    run_id=run_id,
                )
            )

        if settings.notify_failures and result.status in {
            CollectionRunStatus.PARTIAL,
            CollectionRunStatus.CANCELLED,
        }:
            text = (
                "Сбор завершён частично. Проверьте состояние источников."
                if result.status == CollectionRunStatus.PARTIAL
                else ("Сбор был остановлен. Уже полученные данные сохранены.")
            )
            items.append(
                CollectorNotification(
                    id=f"{run_id}:{result.status.value}",
                    created_at=created_at,
                    title="Статус сборщика",
                    message=text,
                    kind=CollectorNotificationKind.WARNING,
                    run_id=run_id,
                )
            )

        return tuple(items)

    def for_failure(
        self,
        message: str,
        settings: CollectorScheduleSettings,
        *,
        run_id: str = "",
    ) -> tuple[CollectorNotification, ...]:
        if not settings.notify_failures:
            return ()
        identifier = f"{run_id}:failed" if run_id else f"failed:{uuid4().hex}"
        return (
            CollectorNotification(
                id=identifier,
                created_at=_now_iso(),
                title="Ошибка сборщика тендеров",
                message=message.strip() or "Сбор завершился ошибкой.",
                kind=CollectorNotificationKind.ERROR,
                run_id=run_id,
            ),
        )

    def for_monitoring_transitions(
        self,
        transitions: Iterable[object],
        settings: CollectorScheduleSettings,
    ) -> tuple[CollectorNotification, ...]:
        """Build deduplicated safe alerts for RM-139 source-state transitions."""

        if not settings.notify_failures:
            return ()
        from app.tenders.collector.source_monitoring import (
            SourceMonitoringTransition,
            SourceMonitoringTransitionKind,
        )

        presentation = {
            SourceMonitoringTransitionKind.OPERATIONAL_DEGRADED: (
                "Источник требует внимания",
                "Сбор из источника завершился с ошибкой или временно ограничен.",
                CollectorNotificationKind.WARNING,
            ),
            SourceMonitoringTransitionKind.OPERATIONAL_RECOVERED: (
                "Источник восстановлен",
                "Источник снова успешно участвует в сборе.",
                CollectorNotificationKind.SUCCESS,
            ),
            SourceMonitoringTransitionKind.CHECKPOINT_STALE: (
                "Checkpoint источника устарел",
                "Инкрементальное состояние источника требует обновления.",
                CollectorNotificationKind.WARNING,
            ),
            SourceMonitoringTransitionKind.VERIFICATION_LOST: (
                "Проверка C19 требует внимания",
                "Полная live-проверка источника больше не считается актуальной.",
                CollectorNotificationKind.WARNING,
            ),
            SourceMonitoringTransitionKind.EVIDENCE_INVALID: (
                "Состояние источника недостоверно",
                "Локальное время наблюдения повреждено или находится в будущем.",
                CollectorNotificationKind.ERROR,
            ),
        }
        result: list[CollectorNotification] = []
        for value in transitions:
            if not isinstance(value, SourceMonitoringTransition):
                continue
            title, message, kind = presentation[value.kind]
            digest = hashlib.sha256(value.evidence_id.encode("utf-8")).hexdigest()[:20]
            result.append(
                CollectorNotification(
                    id=f"source:{value.provider_id}:{value.kind.value}:{digest}",
                    created_at=value.observed_at.isoformat(timespec="seconds"),
                    title=title,
                    message=message,
                    kind=kind,
                )
            )
        return tuple(result)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


__all__ = [
    "CollectorNotification",
    "CollectorNotificationKind",
    "CollectorNotificationRepository",
    "CollectorNotificationService",
]
