"""Incremental checkpoint planning for the Moscow Supplier Portal API.

The documented quote-session methods do not expose a verified change-feed
cursor in the current Corteris integration contract.  The coordinator stores
the latest observed publication timestamp and applies an overlap window.  It
is explicitly a polling checkpoint, not a guarantee that every remote change
is represented by a cursor.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from typing import Mapping

from app.tenders.collector.checkpoint import CollectorCheckpoint
from app.tenders.collector.codec import query_to_payload, stable_hash
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery, TenderSearchResult


@dataclass(frozen=True, slots=True)
class MosSupplierCheckpointPolicy:
    enabled: bool = True
    overlap_days: int = 7
    use_when_date_from_missing: bool = True

    def __post_init__(self) -> None:
        if self.overlap_days < 1:
            raise ValueError("overlap_days must be at least 1")


@dataclass(frozen=True, slots=True)
class MosSupplierPreparedQuery:
    query: TenderSearchQuery
    scope_key: str
    checkpoint: CollectorCheckpoint | None
    incremental_applied: bool
    warnings: tuple[str, ...] = ()


class MosSupplierCheckpointCoordinator:
    provider_id = "mos_supplier"

    def __init__(
        self,
        repository: CollectorStateRepository | None,
        *,
        policy: MosSupplierCheckpointPolicy | None = None,
    ) -> None:
        self.repository = repository
        self.policy = policy or MosSupplierCheckpointPolicy()

    def prepare(
        self,
        query: TenderSearchQuery,
    ) -> MosSupplierPreparedQuery:
        scope_key = self.scope_key(query)
        if self.repository is None or not self.policy.enabled:
            return MosSupplierPreparedQuery(
                query=query,
                scope_key=scope_key,
                checkpoint=None,
                incremental_applied=False,
            )
        checkpoint = self.repository.get_checkpoint(
            self.provider_id,
            scope_key=scope_key,
        )
        if checkpoint is None or not self._incremental_requested(query):
            return MosSupplierPreparedQuery(
                query=query,
                scope_key=scope_key,
                checkpoint=checkpoint,
                incremental_applied=False,
            )
        watermark = _parse_watermark(checkpoint.watermark)
        if watermark is None:
            return MosSupplierPreparedQuery(
                query=query,
                scope_key=scope_key,
                checkpoint=checkpoint,
                incremental_applied=False,
                warnings=(
                    "Checkpoint Портала поставщиков найден, но его дата "
                    "не распознана; выполнен обычный поиск.",
                ),
            )
        start = max(
            date(2000, 1, 1),
            watermark.date() - timedelta(days=self.policy.overlap_days),
        )
        extra = dict(query.extra)
        extra.update(
            {
                "collector_incremental_mode": "publication_overlap",
                "collector_checkpoint_scope": scope_key,
                "collector_checkpoint_watermark": checkpoint.watermark,
                "collector_checkpoint_overlap_days": self.policy.overlap_days,
            }
        )
        return MosSupplierPreparedQuery(
            query=replace(query, date_from=start, extra=extra),
            scope_key=scope_key,
            checkpoint=checkpoint,
            incremental_applied=True,
            warnings=(
                "Инкрементальный режим Портала поставщиков использует "
                f"перекрытие {self.policy.overlap_days} дней и локальную "
                "фильтрацию даты публикации.",
            ),
        )

    def mark_success(
        self,
        prepared: MosSupplierPreparedQuery,
        result: TenderSearchResult,
        *,
        completed_at: datetime | None = None,
    ) -> CollectorCheckpoint | None:
        if self.repository is None or not self.policy.enabled:
            return None
        moment = completed_at or datetime.now(timezone.utc)
        observed = [item.published_at for item in result.items if item.published_at is not None]
        watermark = max(observed, default=moment)
        if watermark.tzinfo is None:
            watermark = watermark.replace(tzinfo=timezone.utc)
        checkpoint = CollectorCheckpoint(
            provider_id=self.provider_id,
            scope_key=prepared.scope_key,
            cursor=result.next_page_token,
            watermark=watermark.isoformat(timespec="seconds"),
            state={
                "strategy": "publication_overlap",
                "overlap_days": self.policy.overlap_days,
                "page": result.page,
                "page_size": result.page_size,
                "item_count": len(result.items),
                "total": result.total,
                "query": query_to_payload(prepared.query),
            },
            updated_at=moment.isoformat(timespec="seconds"),
        )
        return self.repository.save_checkpoint(checkpoint)

    @staticmethod
    def scope_key(query: TenderSearchQuery) -> str:
        payload = query_to_payload(query)
        for key in ("page", "page_size", "date_from", "date_to"):
            payload.pop(key, None)
        extra = payload.get("extra")
        if isinstance(extra, Mapping):
            payload["extra"] = {
                key: value
                for key, value in extra.items()
                if not str(key).startswith("collector_checkpoint_")
                and key != "collector_incremental_mode"
            }
        return "search:" + stable_hash(payload)[:24]

    def _incremental_requested(self, query: TenderSearchQuery) -> bool:
        if query.date_from is not None and self.policy.use_when_date_from_missing:
            return False
        value = query.extra.get("incremental", True)
        if isinstance(value, str):
            return value.strip().casefold() not in {
                "0",
                "false",
                "off",
                "no",
                "нет",
            }
        return bool(value)


def _parse_watermark(value: str) -> datetime | None:
    rendered = value.strip()
    if not rendered:
        return None
    try:
        parsed = datetime.fromisoformat(rendered.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


__all__ = [
    "MosSupplierCheckpointCoordinator",
    "MosSupplierCheckpointPolicy",
    "MosSupplierPreparedQuery",
]
