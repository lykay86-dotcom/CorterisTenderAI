"""Local-only RM-147 application controller."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QFileDialog

from app.financial import snapshot_to_csv_bytes, snapshot_to_json_bytes
from app.repositories.business_metrics import BusinessMetricsRepository
from app.tenders.analytics import (
    AnalyticsGrain,
    AnalyticsInterval,
    AnalyticsProviderOutcome,
    AnalyticsTenderFact,
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
        business_repository: BusinessMetricsRepository | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if registry.path.resolve() != collector.path.resolve():
            raise ValueError("analytics repositories must share tender_registry.sqlite3")
        self.page = page
        self.registry = registry
        self.collector = collector
        self.business_repository = business_repository
        self.service = TenderAnalyticsService()
        self.view_model = TenderAnalyticsViewModel()
        self._generation = 0
        self._shutdown = False
        page.refresh_requested.connect(self.refresh)
        page.filters_applied.connect(self.refresh)
        page.filters_reset.connect(self.refresh)
        page.export_requested.connect(self.export_displayed)
        page.financial_export_requested.connect(self.export_financial_displayed)

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
            filter_values = self.page.filter_values()
            records = self.registry.list_analytics_facts(
                include_archived=filter_values[-1],
                limit=10_001,
                deadline_now=as_of,
                deadline_user_timezone=resolve_timezone("Europe/Moscow"),
            )
            self.page.set_filter_options(records)
            query = self._query(as_of, records)
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
            financial_snapshot = (
                self.business_repository.financial_snapshot(generated_at=as_of)
                if self.business_repository is not None
                else None
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
            if financial_snapshot is not None:
                self.page.set_financial_snapshot(financial_snapshot)

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

    def export_financial_displayed(self, export_format: str) -> None:
        snapshot = self.page.financial_snapshot
        normalized = export_format.strip().casefold()
        if snapshot is None or normalized not in {"json", "csv"}:
            self.page.set_error(
                "financial_export_unavailable", stale=self.page.snapshot is not None
            )
            return
        payload = (
            snapshot_to_json_bytes(snapshot)
            if normalized == "json"
            else snapshot_to_csv_bytes(snapshot)
        )
        suggested = f"workflow-financial-{snapshot.fingerprint[:12]}.{normalized}"
        path, _selected_filter = QFileDialog.getSaveFileName(
            self.page,
            "Экспорт финансового снимка",
            suggested,
            "JSON (*.json)" if normalized == "json" else "CSV (*.csv)",
        )
        if not path:
            return
        try:
            write_export_atomically(path, payload)
        except OSError:
            self.page.set_error("financial_export_failed", stale=True)

    def shutdown(self) -> bool:
        if self._shutdown:
            return True
        self._shutdown = True
        return True

    def _query(
        self,
        as_of: datetime,
        records: tuple[AnalyticsTenderFact, ...],
    ) -> TenderAnalyticsQuery:
        (
            preset,
            custom_start,
            custom_end,
            grain,
            source_ids,
            statuses,
            laws,
            include_archived,
        ) = self.page.filter_values()
        zone = resolve_timezone("Europe/Moscow")
        local_now = as_of.astimezone(zone)
        today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        if preset == "last_7_complete_days":
            start, end = today - timedelta(days=7), today
        elif preset == "current_month":
            start, end = today.replace(day=1), local_now.replace(microsecond=0)
        elif preset == "custom":
            start = datetime.combine(custom_start, time.min, tzinfo=zone)
            end = datetime.combine(custom_end, time.min, tzinfo=zone)
        elif preset == "all_available":
            confirmed = tuple(
                parsed
                for item in records
                if (parsed := _aware_or_none(item.first_seen_at)) is not None
            )
            end = local_now.replace(microsecond=0)
            start = min(confirmed).astimezone(zone) if confirmed else today - timedelta(days=30)
        else:
            start, end = today - timedelta(days=30), today
        return TenderAnalyticsQuery(
            interval=AnalyticsInterval(start, end, "Europe/Moscow"),
            grain=AnalyticsGrain(grain),
            source_ids=source_ids,
            statuses=statuses,
            laws=laws,
            include_archived=include_archived,
        )


__all__ = ["TenderAnalyticsController"]
