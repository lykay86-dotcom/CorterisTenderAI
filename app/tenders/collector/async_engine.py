"""Fault-isolated asynchronous provider execution engine."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from time import perf_counter
from typing import Iterable, Sequence
from uuid import uuid4

from app.tenders.collector.aggregator_discovery import is_aggregator_discovery
from app.tenders.collector.async_provider import AsyncTenderProvider
from app.tenders.collector.cancellation import (
    CollectorCancellationToken,
    CollectorCancelledError,
)
from app.tenders.collector.health_monitor import ProviderHealthMonitor
from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.models import DeduplicationResult
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.progress import (
    CollectorProgressCallback,
    CollectorProgressDispatcher,
    CollectorProgressEvent,
    CollectorProgressPhase,
    ParallelSearchRunState,
    ParallelSearchSnapshot,
    ProviderExecutionSnapshot,
    ProviderExecutionState,
)
from app.tenders.collector.search_errors import (
    SearchErrorCategory,
    classify_search_error,
)
from app.tenders.provider_base import (
    ProviderCapabilityError,
    ProviderNotConfiguredError,
    TenderSearchQuery,
    TenderSearchResult,
)


class AsyncProviderSearchStatus(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    NOT_CONFIGURED = "not_configured"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    CIRCUIT_OPEN = "circuit_open"


@dataclass(frozen=True, slots=True)
class AsyncProviderSearchOutcome:
    provider_id: str
    display_name: str
    status: AsyncProviderSearchStatus
    elapsed_ms: int
    item_count: int = 0
    warnings: tuple[str, ...] = ()
    error_type: str = ""
    error_message: str = ""
    error_category: SearchErrorCategory = SearchErrorCategory.NONE
    error_code: str = ""
    attempt_count: int = 1
    retryable: bool = False
    http_status: int | None = None

    @property
    def successful(self) -> bool:
        return self.status in {
            AsyncProviderSearchStatus.SUCCESS,
            AsyncProviderSearchStatus.EMPTY,
        }


@dataclass(frozen=True, slots=True)
class AsyncProviderBatchResult:
    results: tuple[TenderSearchResult, ...]
    outcomes: tuple[AsyncProviderSearchOutcome, ...]
    started_at: str
    completed_at: str
    elapsed_ms: int
    cancelled: bool = False
    timed_out: bool = False
    run_id: str = ""
    snapshot: ParallelSearchSnapshot | None = None
    deduplication: DeduplicationResult | None = None

    @property
    def raw_items(self):
        return tuple(item for result in self.results for item in result.items)

    @property
    def has_partial_failures(self) -> bool:
        return any(
            not outcome.successful
            for outcome in self.outcomes
            if outcome.status != AsyncProviderSearchStatus.SKIPPED
        )


@dataclass(frozen=True, slots=True)
class _Execution:
    provider: AsyncTenderProvider
    result: TenderSearchResult | None
    outcome: AsyncProviderSearchOutcome


class _SearchLifecycle:
    """Single-run state owner; completion order never becomes output order."""

    def __init__(
        self,
        providers: tuple[AsyncTenderProvider, ...],
        *,
        run_id: str,
        started_at: str,
        dispatcher: CollectorProgressDispatcher,
        normalizer: TenderNormalizer,
        deduplicator: TenderDeduplicator,
    ) -> None:
        self.providers = providers
        self.run_id = run_id
        self.started_at = started_at
        self.dispatcher = dispatcher
        self.normalizer = normalizer
        self.deduplicator = deduplicator
        self.state = ParallelSearchRunState.RUNNING
        self.revision = -1
        self.percent = 0
        self.executions: dict[str, _Execution] = {}
        self.provider_snapshots = {
            provider.descriptor.id: ProviderExecutionSnapshot(
                provider_id=provider.descriptor.id,
                display_name=provider.descriptor.display_name,
                state=ProviderExecutionState.QUEUED,
            )
            for provider in providers
        }
        self.deduplication = DeduplicationResult(items=(), groups=(), raw_count=0)
        self.last_snapshot: ParallelSearchSnapshot | None = None

    @property
    def terminal(self) -> bool:
        return self.state.terminal

    async def start(self) -> None:
        if not self.providers:
            return
        for provider in self.providers:
            await self._publish(
                CollectorProgressPhase.PROVIDER_QUEUED,
                provider_id=provider.descriptor.id,
                display_name=provider.descriptor.display_name,
                message="Источник добавлен в очередь.",
            )

    async def mark_running(self, provider: AsyncTenderProvider) -> bool:
        if self.terminal:
            return False
        provider_id = provider.descriptor.id
        current = self.provider_snapshots[provider_id]
        if current.state is not ProviderExecutionState.QUEUED:
            return False
        self.provider_snapshots[provider_id] = replace(
            current,
            state=ProviderExecutionState.RUNNING,
        )
        await self._publish(
            CollectorProgressPhase.PROVIDER_RUNNING,
            provider_id=provider_id,
            display_name=provider.descriptor.display_name,
            message="Выполняется поиск по источнику…",
        )
        return not self.terminal

    async def accept(self, execution: _Execution) -> bool:
        if self.terminal:
            return False
        provider_id = execution.provider.descriptor.id
        current = self.provider_snapshots[provider_id]
        if current.terminal:
            return False
        outcome = execution.outcome
        self.executions[provider_id] = execution
        self.provider_snapshots[provider_id] = ProviderExecutionSnapshot(
            provider_id=provider_id,
            display_name=outcome.display_name,
            state=ProviderExecutionState(outcome.status.value),
            item_count=outcome.item_count,
            elapsed_ms=outcome.elapsed_ms,
            attempt_count=outcome.attempt_count,
            error_category=outcome.error_category,
            error_code=outcome.error_code,
            error_message=outcome.error_message,
            retryable=outcome.retryable,
            http_status=outcome.http_status,
        )
        self._rebuild_partial()
        await self._publish(
            CollectorProgressPhase.PROVIDER_COMPLETED,
            provider_id=provider_id,
            display_name=outcome.display_name,
            provider_status=outcome.status.value,
            item_count=outcome.item_count,
            elapsed_ms=outcome.elapsed_ms,
            message=outcome.error_message or _provider_status_message(outcome.status),
        )
        return True

    async def finish(self, state: ParallelSearchRunState) -> ParallelSearchSnapshot:
        if self.terminal and self.last_snapshot is not None:
            return self.last_snapshot
        terminal_provider_state = {
            ParallelSearchRunState.CANCELLED: AsyncProviderSearchStatus.CANCELLED,
            ParallelSearchRunState.TIMED_OUT: AsyncProviderSearchStatus.TIMED_OUT,
        }.get(state, AsyncProviderSearchStatus.SKIPPED)
        for provider in self.providers:
            provider_id = provider.descriptor.id
            if self.provider_snapshots[provider_id].terminal:
                continue
            if terminal_provider_state is AsyncProviderSearchStatus.CANCELLED:
                error: BaseException = CollectorCancelledError()
            elif terminal_provider_state is AsyncProviderSearchStatus.TIMED_OUT:
                error = TimeoutError()
            else:
                error = RuntimeError()
            failure = classify_search_error(error)
            outcome = AsyncProviderSearchOutcome(
                provider_id=provider_id,
                display_name=provider.descriptor.display_name,
                status=terminal_provider_state,
                elapsed_ms=0,
                error_type=type(error).__name__,
                error_message=failure.message,
                error_category=failure.category,
                error_code=failure.code,
                attempt_count=failure.attempts,
                retryable=failure.retryable,
                http_status=failure.http_status,
            )
            self.executions[provider_id] = _Execution(provider, None, outcome)
            self.provider_snapshots[provider_id] = ProviderExecutionSnapshot(
                provider_id=provider_id,
                display_name=provider.descriptor.display_name,
                state=ProviderExecutionState(terminal_provider_state.value),
                error_category=failure.category,
                error_code=failure.code,
                error_message=failure.message,
                retryable=failure.retryable,
            )
        self.state = state
        return await self._publish(
            CollectorProgressPhase.SEARCH_TERMINAL,
            message="Параллельный поиск завершён.",
        )

    def ordered_executions(self) -> tuple[_Execution, ...]:
        return tuple(self.executions[provider.descriptor.id] for provider in self.providers)

    def _rebuild_partial(self) -> None:
        raw_items = tuple(
            item
            for provider in self.providers
            for execution in (self.executions.get(provider.descriptor.id),)
            if execution is not None and execution.result is not None
            for item in execution.result.items
            if not is_aggregator_discovery(item)
        )
        normalized = self.normalizer.normalize_many(raw_items)
        self.deduplication = self.deduplicator.deduplicate(normalized)

    async def _publish(
        self,
        phase: CollectorProgressPhase,
        *,
        provider_id: str = "",
        display_name: str = "",
        provider_status: str = "",
        item_count: int = 0,
        elapsed_ms: int = 0,
        message: str = "",
    ) -> ParallelSearchSnapshot:
        self.revision += 1
        providers = tuple(
            self.provider_snapshots[provider.descriptor.id] for provider in self.providers
        )
        completed = sum(item.terminal for item in providers)
        calculated = int((completed / len(providers)) * 90) if providers else 90
        self.percent = 100 if self.state.terminal else max(self.percent, calculated)
        snapshot = ParallelSearchSnapshot(
            run_id=self.run_id,
            revision=self.revision,
            state=self.state,
            providers=providers,
            started_at=self.started_at,
            updated_at=_utc_now(),
            completed=completed,
            percent=self.percent,
            partial_items=self.deduplication.items,
        )
        self.last_snapshot = snapshot
        await self.dispatcher.publish(
            CollectorProgressEvent(
                phase=phase,
                provider_id=provider_id,
                display_name=display_name,
                provider_status=provider_status,
                item_count=item_count,
                elapsed_ms=elapsed_ms,
                total_providers=len(providers),
                raw_count=self.deduplication.raw_count,
                merged_count=self.deduplication.merged_count,
                duplicate_count=self.deduplication.duplicate_count,
                message=message,
                snapshot=snapshot,
            )
        )
        return snapshot


class AsyncProviderSearchEngine:
    """Execute providers concurrently without propagating one failure."""

    def __init__(
        self,
        providers: Iterable[AsyncTenderProvider],
        *,
        health_monitor: ProviderHealthMonitor | None = None,
        max_concurrent_providers: int = 6,
        provider_timeout_seconds: float = 60.0,
        overall_timeout_seconds: float = 180.0,
        progress_queue_size: int = 64,
        progress_shutdown_timeout_seconds: float = 0.2,
        normalizer: TenderNormalizer | None = None,
        deduplicator: TenderDeduplicator | None = None,
    ) -> None:
        if max_concurrent_providers < 1:
            raise ValueError("max_concurrent_providers must be at least 1")
        if provider_timeout_seconds <= 0:
            raise ValueError("provider_timeout_seconds must be positive")
        if overall_timeout_seconds <= 0:
            raise ValueError("overall_timeout_seconds must be positive")
        if progress_queue_size < 1:
            raise ValueError("progress_queue_size must be positive")
        if progress_shutdown_timeout_seconds <= 0:
            raise ValueError("progress_shutdown_timeout_seconds must be positive")
        self.providers = tuple(
            sorted(
                providers,
                key=lambda provider: (
                    provider.descriptor.priority,
                    provider.descriptor.display_name.casefold(),
                    provider.descriptor.id,
                ),
            )
        )
        self.health_monitor = health_monitor or ProviderHealthMonitor()
        self.max_concurrent_providers = int(max_concurrent_providers)
        self.provider_timeout_seconds = float(provider_timeout_seconds)
        self.overall_timeout_seconds = float(overall_timeout_seconds)
        self.progress_queue_size = int(progress_queue_size)
        self.progress_shutdown_timeout_seconds = float(progress_shutdown_timeout_seconds)
        self.normalizer = normalizer or TenderNormalizer()
        self.deduplicator = deduplicator or TenderDeduplicator(self.normalizer)

    async def search(
        self,
        query: TenderSearchQuery,
        *,
        provider_ids: Sequence[str] | None = None,
        cancellation_token: CollectorCancellationToken | None = None,
        progress_callback: CollectorProgressCallback | None = None,
        run_id: str = "",
    ) -> AsyncProviderBatchResult:
        started_counter = perf_counter()
        started_at = _utc_now()
        selected = self._select(provider_ids)
        semaphore = asyncio.Semaphore(self.max_concurrent_providers)
        token = cancellation_token or CollectorCancellationToken()
        effective_run_id = run_id.strip() or uuid4().hex
        dispatcher = CollectorProgressDispatcher(
            progress_callback,
            max_queue_size=self.progress_queue_size,
            shutdown_timeout_seconds=self.progress_shutdown_timeout_seconds,
        )
        lifecycle = _SearchLifecycle(
            selected,
            run_id=effective_run_id,
            started_at=started_at,
            dispatcher=dispatcher,
            normalizer=self.normalizer,
            deduplicator=self.deduplicator,
        )
        await lifecycle.start()

        tasks = [
            asyncio.create_task(
                self._execute_provider(
                    provider,
                    query,
                    semaphore=semaphore,
                    cancellation_token=token,
                    lifecycle=lifecycle,
                )
            )
            for provider in selected
        ]

        cancelled = False
        timed_out = False
        if tasks:
            cancel_task = asyncio.create_task(token.wait_cancelled(poll_interval=0.01))
            deadline_task = asyncio.create_task(asyncio.sleep(self.overall_timeout_seconds))
            gather_task = asyncio.ensure_future(asyncio.gather(*tasks, return_exceptions=True))
            done, _ = await asyncio.wait(
                {gather_task, cancel_task, deadline_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if gather_task in done and not token.is_cancelled and deadline_task not in done:
                cancel_task.cancel()
                deadline_task.cancel()
                await asyncio.gather(cancel_task, deadline_task, return_exceptions=True)
                raw = await gather_task
                for provider, value in zip(selected, raw):
                    await lifecycle.accept(self._coerce_execution(provider, value))
                has_failures = any(
                    not execution.outcome.successful for execution in lifecycle.ordered_executions()
                )
                has_items = bool(lifecycle.deduplication.items)
                terminal_state = (
                    ParallelSearchRunState.PARTIAL
                    if has_failures and has_items
                    else ParallelSearchRunState.FAILED
                    if has_failures
                    else ParallelSearchRunState.COMPLETED
                )
                await lifecycle.finish(terminal_state)
            elif cancel_task in done or token.is_cancelled:
                cancelled = True
                await lifecycle.finish(ParallelSearchRunState.CANCELLED)
                deadline_task.cancel()
                await asyncio.gather(deadline_task, return_exceptions=True)
                for task in tasks:
                    if not task.done():
                        task.cancel()
                gather_task.cancel()
                await asyncio.gather(gather_task, *tasks, return_exceptions=True)
            else:
                timed_out = True
                await lifecycle.finish(ParallelSearchRunState.TIMED_OUT)
                token.cancel("Истекло общее время поиска.")
                cancel_task.cancel()
                await asyncio.gather(cancel_task, return_exceptions=True)
                for task in tasks:
                    if not task.done():
                        task.cancel()
                gather_task.cancel()
                await asyncio.gather(gather_task, *tasks, return_exceptions=True)
        else:
            await lifecycle.finish(ParallelSearchRunState.COMPLETED)

        executions = lifecycle.ordered_executions()
        results = tuple(
            execution.result for execution in executions if execution.result is not None
        )
        outcomes = tuple(execution.outcome for execution in executions)
        result = AsyncProviderBatchResult(
            results=results,
            outcomes=outcomes,
            started_at=started_at,
            completed_at=_utc_now(),
            elapsed_ms=round((perf_counter() - started_counter) * 1000),
            cancelled=cancelled,
            timed_out=timed_out,
            run_id=effective_run_id,
            snapshot=lifecycle.last_snapshot,
            deduplication=lifecycle.deduplication,
        )
        await dispatcher.close()
        return result

    def _select(
        self,
        provider_ids: Sequence[str] | None,
    ) -> tuple[AsyncTenderProvider, ...]:
        if provider_ids is None:
            return self.providers
        requested = {
            provider_id.strip().casefold() for provider_id in provider_ids if provider_id.strip()
        }
        return tuple(
            provider
            for provider in self.providers
            if provider.descriptor.id.casefold() in requested
        )

    async def _execute_provider(
        self,
        provider: AsyncTenderProvider,
        query: TenderSearchQuery,
        *,
        semaphore: asyncio.Semaphore,
        cancellation_token: CollectorCancellationToken,
        lifecycle: _SearchLifecycle,
    ) -> _Execution:
        execution = await self._execute_provider_impl(
            provider,
            query,
            semaphore=semaphore,
            cancellation_token=cancellation_token,
            lifecycle=lifecycle,
        )
        await lifecycle.accept(execution)
        return execution

    async def _execute_provider_impl(
        self,
        provider: AsyncTenderProvider,
        query: TenderSearchQuery,
        *,
        semaphore: asyncio.Semaphore,
        cancellation_token: CollectorCancellationToken,
        lifecycle: _SearchLifecycle,
    ) -> _Execution:
        provider_id = provider.descriptor.id
        display_name = provider.descriptor.display_name
        if not provider.descriptor.capabilities.search:
            return self._failure_execution(
                provider,
                AsyncProviderSearchStatus.UNSUPPORTED,
                0,
                ProviderCapabilityError("search unsupported"),
            )

        if not self.health_monitor.can_execute(provider_id):
            return _Execution(
                provider=provider,
                result=None,
                outcome=AsyncProviderSearchOutcome(
                    provider_id=provider_id,
                    display_name=display_name,
                    status=AsyncProviderSearchStatus.CIRCUIT_OPEN,
                    elapsed_ms=0,
                    error_type="ProviderCircuitOpenError",
                    error_message="Источник временно отключён после повторных ошибок.",
                    error_category=SearchErrorCategory.REMOTE_SERVICE,
                    error_code="provider_circuit_open",
                    retryable=True,
                ),
            )

        started = perf_counter()
        try:
            cancellation_token.throw_if_cancelled()
            async with semaphore:
                cancellation_token.throw_if_cancelled()
                if not await lifecycle.mark_running(provider):
                    raise CollectorCancelledError()
                async with asyncio.timeout(self.provider_timeout_seconds):
                    result = await provider.search(
                        query,
                        cancellation_token=cancellation_token,
                    )
            elapsed_ms = round((perf_counter() - started) * 1000)
            self.health_monitor.register_success(
                provider_id,
                latency_ms=elapsed_ms,
                connection_mode=provider.connection_mode,
                parser_version=provider.parser_version,
            )
            status = (
                AsyncProviderSearchStatus.SUCCESS
                if result.items
                else AsyncProviderSearchStatus.EMPTY
            )
            return _Execution(
                provider=provider,
                result=result,
                outcome=AsyncProviderSearchOutcome(
                    provider_id=provider_id,
                    display_name=display_name,
                    status=status,
                    elapsed_ms=elapsed_ms,
                    item_count=len(result.items),
                    warnings=result.warnings,
                ),
            )
        except ProviderNotConfiguredError as exc:
            elapsed_ms = round((perf_counter() - started) * 1000)
            self.health_monitor.register_not_configured(
                provider_id,
                str(exc),
            )
            return self._failure_execution(
                provider,
                AsyncProviderSearchStatus.NOT_CONFIGURED,
                elapsed_ms,
                exc,
            )
        except ProviderCapabilityError as exc:
            elapsed_ms = round((perf_counter() - started) * 1000)
            return self._failure_execution(
                provider,
                AsyncProviderSearchStatus.UNSUPPORTED,
                elapsed_ms,
                exc,
            )
        except TimeoutError as exc:
            elapsed_ms = round((perf_counter() - started) * 1000)
            self.health_monitor.register_failure(
                provider_id,
                exc,
                latency_ms=elapsed_ms,
                connection_mode=provider.connection_mode,
                parser_version=provider.parser_version,
            )
            return self._failure_execution(
                provider,
                AsyncProviderSearchStatus.TIMED_OUT,
                elapsed_ms,
                exc,
                message=(f"Источник не завершил поиск за {self.provider_timeout_seconds:g} сек."),
            )
        except (CollectorCancelledError, asyncio.CancelledError) as exc:
            elapsed_ms = round((perf_counter() - started) * 1000)
            return self._failure_execution(
                provider,
                AsyncProviderSearchStatus.CANCELLED,
                elapsed_ms,
                exc,
            )
        except Exception as exc:
            elapsed_ms = round((perf_counter() - started) * 1000)
            self.health_monitor.register_failure(
                provider_id,
                exc,
                latency_ms=elapsed_ms,
                connection_mode=provider.connection_mode,
                parser_version=provider.parser_version,
            )
            return self._failure_execution(
                provider,
                AsyncProviderSearchStatus.FAILED,
                elapsed_ms,
                exc,
            )

    @staticmethod
    def _failure_execution(
        provider: AsyncTenderProvider,
        status: AsyncProviderSearchStatus,
        elapsed_ms: int,
        error: BaseException,
        *,
        message: str = "",
    ) -> _Execution:
        failure = classify_search_error(error)
        return _Execution(
            provider=provider,
            result=None,
            outcome=AsyncProviderSearchOutcome(
                provider_id=provider.descriptor.id,
                display_name=provider.descriptor.display_name,
                status=status,
                elapsed_ms=elapsed_ms,
                error_type=type(error).__name__,
                error_message=message or failure.message,
                error_category=failure.category,
                error_code=failure.code,
                attempt_count=failure.attempts,
                retryable=failure.retryable,
                http_status=failure.http_status,
            ),
        )

    @staticmethod
    def _cancelled_execution(
        provider: AsyncTenderProvider,
        reason: str,
    ) -> _Execution:
        return AsyncProviderSearchEngine._failure_execution(
            provider,
            AsyncProviderSearchStatus.CANCELLED,
            0,
            CollectorCancelledError(reason),
        )

    @staticmethod
    def _coerce_execution(
        provider: AsyncTenderProvider,
        value: object,
    ) -> _Execution:
        if isinstance(value, _Execution):
            return value
        if isinstance(value, BaseException):
            return AsyncProviderSearchEngine._failure_execution(
                provider,
                AsyncProviderSearchStatus.FAILED,
                0,
                value,
            )
        return AsyncProviderSearchEngine._failure_execution(
            provider,
            AsyncProviderSearchStatus.FAILED,
            0,
            RuntimeError("Провайдер вернул неподдерживаемый результат."),
        )


def _provider_status_message(
    status: AsyncProviderSearchStatus,
) -> str:
    return {
        AsyncProviderSearchStatus.SUCCESS: "Источник завершён успешно.",
        AsyncProviderSearchStatus.EMPTY: "Подходящие закупки не найдены.",
        AsyncProviderSearchStatus.NOT_CONFIGURED: "Источник не настроен.",
        AsyncProviderSearchStatus.UNSUPPORTED: "Поиск не поддерживается.",
        AsyncProviderSearchStatus.FAILED: "Ошибка источника.",
        AsyncProviderSearchStatus.TIMED_OUT: "Истекло время ожидания.",
        AsyncProviderSearchStatus.CANCELLED: "Источник остановлен.",
        AsyncProviderSearchStatus.SKIPPED: "Источник пропущен.",
        AsyncProviderSearchStatus.CIRCUIT_OPEN: ("Источник временно отключён после ошибок."),
    }[status]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "AsyncProviderBatchResult",
    "AsyncProviderSearchEngine",
    "AsyncProviderSearchOutcome",
    "AsyncProviderSearchStatus",
]
