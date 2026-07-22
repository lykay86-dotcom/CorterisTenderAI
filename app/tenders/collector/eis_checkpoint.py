"""Checkpoint planning for the public EIS HTML connector.

The public search page does not expose a documented update cursor.  The
collector therefore uses a conservative sliding publication-date window and
persists the last successful request as an operational checkpoint.  This is
not equivalent to an official change feed and is deliberately labelled as a
best-effort public-HTML strategy.
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
class EisCheckpointPolicy:
    """Settings for best-effort incremental collection from public HTML."""

    enabled: bool = True
    overlap_days: int = 14
    use_when_date_from_missing: bool = True

    def __post_init__(self) -> None:
        if self.overlap_days < 1:
            raise ValueError("overlap_days must be at least 1")


@dataclass(frozen=True, slots=True)
class EisPreparedQuery:
    query: TenderSearchQuery
    scope_key: str
    checkpoint: CollectorCheckpoint | None
    incremental_applied: bool
    warnings: tuple[str, ...] = ()


class EisCheckpointCoordinator:
    """Apply and persist EIS sliding-window checkpoints."""

    provider_id = "eis"

    def __init__(
        self,
        repository: CollectorStateRepository | None,
        *,
        policy: EisCheckpointPolicy | None = None,
    ) -> None:
        self.repository = repository
        self.policy = policy or EisCheckpointPolicy()

    def prepare(
        self,
        query: TenderSearchQuery,
        *,
        checkpoint: CollectorCheckpoint | None = None,
        read_repository: bool = True,
    ) -> EisPreparedQuery:
        scope_key = self.scope_key(query)
        if not self.policy.enabled:
            return EisPreparedQuery(
                query=query,
                scope_key=scope_key,
                checkpoint=None,
                incremental_applied=False,
            )

        if checkpoint is None and read_repository and self.repository is not None:
            checkpoint = self.repository.get_checkpoint(
                self.provider_id,
                scope_key=scope_key,
            )
        if checkpoint is None:
            return EisPreparedQuery(
                query=query,
                scope_key=scope_key,
                checkpoint=None,
                incremental_applied=False,
            )

        if not self._incremental_requested(query):
            return EisPreparedQuery(
                query=query,
                scope_key=scope_key,
                checkpoint=checkpoint,
                incremental_applied=False,
            )

        # A non-empty cursor is a crash-resume position inside the same query.
        # Changing its date window would skip or duplicate pages in that run.
        if checkpoint.cursor:
            return EisPreparedQuery(
                query=query,
                scope_key=scope_key,
                checkpoint=checkpoint,
                incremental_applied=False,
            )

        watermark = _parse_watermark(
            checkpoint.watermark or checkpoint.committed_at or checkpoint.updated_at
        )
        if watermark is None:
            return EisPreparedQuery(
                query=query,
                scope_key=scope_key,
                checkpoint=checkpoint,
                incremental_applied=False,
                warnings=(
                    "Checkpoint ЕИС найден, но его дата не распознана; выполнен обычный поиск.",
                ),
            )

        date_from = max(
            date(2000, 1, 1),
            watermark.date() - timedelta(days=self.policy.overlap_days),
        )
        extra = dict(query.extra)
        extra.update(
            {
                "collector_incremental_mode": "sliding_publication_window",
                "collector_checkpoint_scope": scope_key,
                "collector_checkpoint_watermark": checkpoint.watermark,
                "collector_checkpoint_overlap_days": self.policy.overlap_days,
            }
        )
        prepared_query = replace(
            query,
            date_from=date_from,
            extra=extra,
        )
        return EisPreparedQuery(
            query=prepared_query,
            scope_key=scope_key,
            checkpoint=checkpoint,
            incremental_applied=True,
            warnings=(
                "Инкрементальный режим ЕИС использует скользящее "
                f"окно публикации {self.policy.overlap_days} дней. "
                "Это резервная стратегия публичного HTML, а не "
                "официальный журнал изменений.",
            ),
        )

    def mark_success(
        self,
        prepared: EisPreparedQuery,
        result: TenderSearchResult,
        *,
        completed_at: datetime | None = None,
    ) -> CollectorCheckpoint | None:
        if self.repository is None or not self.policy.enabled:
            return None

        moment = completed_at or datetime.now(timezone.utc)
        state: dict[str, object] = {
            "strategy": "sliding_publication_window",
            "overlap_days": self.policy.overlap_days,
            "page": result.page,
            "page_size": result.page_size,
            "item_count": len(result.items),
            "total": result.total,
            "next_page_token": result.next_page_token,
            "query": query_to_payload(prepared.query),
        }
        checkpoint = CollectorCheckpoint(
            provider_id=self.provider_id,
            scope_key=prepared.scope_key,
            cursor=result.next_page_token,
            watermark=moment.isoformat(timespec="seconds"),
            state=state,
            updated_at=moment.isoformat(timespec="seconds"),
        )
        return self.repository.save_checkpoint(checkpoint)

    @staticmethod
    def scope_key(query: TenderSearchQuery) -> str:
        """Build a stable scope excluding paging and explicit date range."""

        payload = query_to_payload(query)
        payload.pop("page", None)
        payload.pop("page_size", None)
        payload.pop("date_from", None)
        payload.pop("date_to", None)
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
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


__all__ = [
    "EisCheckpointCoordinator",
    "EisCheckpointPolicy",
    "EisPreparedQuery",
]
