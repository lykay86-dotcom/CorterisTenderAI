"""Local-only RM-147 application controller."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QFileDialog

from app.tenders.analytics import (
    AnalyticsGrain,
    AnalyticsInterval,
    AnalyticsProviderOutcome,
    TenderAnalyticsQuery,
    TenderAnalyticsService,
    TenderAnalyticsViewModel,
    export_snapshot_csv,
    export_snapshot_json,
    resolve_timezone,
    write_export_atomically,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.pages.tender_analytics_page import TenderAnalyticsPage


_COMPLETE_OUTCOMES = frozenset({"success", "empty"})


def _aware_or_none(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


class TenderAnalyticsController(QObject):
    """Own local repository reads, generations, publication, and export intent."""

    def __init__(
        self,
        page: TenderAnalyticsPage,
        registry: TenderRegistryRepository,
        collector: CollectorStateRepository,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if registry.path.resolve() != collector.path.resolve():
            raise ValueError("analytics repositories must share tender_registry.sqlite3")
        self.page = page
        self.registry = registry
        self.collector = collector
        self.service = TenderAnalyticsService()
        self.view_model = TenderAnalyticsViewModel()
        self._generation = 0
        self._shutdown = False
        page.refresh_requested.connect(self.refresh)
        page.filters_applied.connect(self.refresh)
        page.filters_reset.connect(self.refresh)
        page.export_requested.connect(self.export_displayed)

    def start(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        if self._shutdown:
            return
        self._generation += 1
        generation = self._generation
        self.view_model.begin(generation)
        self.page.set_loading(retain_snapshot=self.page.snapshot is not None)
        try:
            as_of = datetime.now(timezone.utc)
            query = self._query(as_of)
            records = self.registry.list_analytics_facts(
                include_archived=query.include_archived,
                limit=10_001,
                deadline_now=as_of,
                deadline_user_timezone=resolve_timezone(query.interval.timezone_name),
            )
            observations = self.collector.list_analytics_source_observations()
            conflicts = self.collector.list_analytics_conflicts()
            outcomes = tuple(
                AnalyticsProviderOutcome(
                    source_id=item.provider_id,
                    run_id=item.run_id,
                    outcome=item.status,
                    observed_at=_aware_or_none(item.completed_at),
                    item_count=(item.item_count if item.status in _COMPLETE_OUTCOMES else None),
                    reason_code=item.error_code,
                )
                for item in self.collector.list_provider_outcomes(limit=1000)
            )
            snapshot = self.service.aggregate(
                query,
                records,
                source_observations=observations,
                provider_outcomes=outcomes,
                conflicts=conflicts,
                as_of=as_of,
                generation=generation,
            )
        except Exception:
            self.view_model.fail(generation=generation, reason_code="analytics_read_failed")
            self.page.set_error(
                "analytics_read_failed",
                stale=self.view_model.displayed_snapshot is not None,
            )
            return
        if self.view_model.accept(snapshot, generation=generation):
            self.page.set_snapshot(snapshot)

    def export_displayed(self, export_format: str) -> None:
        snapshot = self.view_model.displayed_snapshot
        normalized = export_format.strip().casefold()
        if snapshot is None or normalized not in {"json", "csv"}:
            self.page.set_error("export_unavailable", stale=snapshot is not None)
            return
        payload = (
            export_snapshot_json(snapshot)
            if normalized == "json"
            else export_snapshot_csv(snapshot)
        )
        suggested = (
            f"tender-analytics-{snapshot.query.interval.start_inclusive.date().isoformat()}-"
            f"{snapshot.query.interval.end_exclusive.date().isoformat()}.{normalized}"
        )
        path, _selected_filter = QFileDialog.getSaveFileName(
            self.page,
            "Экспорт аналитики тендеров",
            suggested,
            "JSON (*.json)" if normalized == "json" else "CSV (*.csv)",
        )
        if not path:
            return
        try:
            write_export_atomically(path, payload)
        except OSError:
            self.page.set_error("export_failed", stale=True)

    def shutdown(self) -> bool:
        if self._shutdown:
            return True
        self._shutdown = True
        return True

    def _query(self, as_of: datetime) -> TenderAnalyticsQuery:
        days, grain, include_archived = self.page.filter_values()
        zone = resolve_timezone("Europe/Moscow")
        local_now = as_of.astimezone(zone)
        end = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=days)
        return TenderAnalyticsQuery(
            interval=AnalyticsInterval(start, end, "Europe/Moscow"),
            grain=AnalyticsGrain(grain),
            include_archived=include_archived,
        )


__all__ = ["TenderAnalyticsController"]
