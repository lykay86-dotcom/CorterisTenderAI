"""Fault-isolated asynchronous provider execution engine."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from time import perf_counter
from typing import Iterable, Sequence

from app.tenders.collector.async_provider import AsyncTenderProvider
from app.tenders.collector.cancellation import (
    CollectorCancellationToken,
    CollectorCancelledError,
)
from app.tenders.collector.health_monitor import (
    ProviderHealthMonitor,
    ProviderOperationalStatus,
)
from app.tenders.provider_base import (
    ProviderCapabilityError,
    ProviderNotConfiguredError,
    TenderProviderError,
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

    @property
    def raw_items(self):
        return tuple(
            item
            for result in self.results
            for item in result.items
        )

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


class AsyncProviderSearchEngine:
    """Execute providers concurrently without propagating one failure."""

    def __init__(
        self,
        providers: Iterable[AsyncTenderProvider],
        *,
        health_monitor: ProviderHealthMonitor | None = None,
        max_concurrent_providers: int = 6,
        provider_timeout_seconds: float = 60.0,
    ) -> None:
        if max_concurrent_providers < 1:
            raise ValueError(
                "max_concurrent_providers must be at least 1"
            )
        if provider_timeout_seconds <= 0:
            raise ValueError("provider_timeout_seconds must be positive")
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

    async def search(
        self,
        query: TenderSearchQuery,
        *,
        provider_ids: Sequence[str] | None = None,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> AsyncProviderBatchResult:
        started_counter = perf_counter()
        started_at = _utc_now()
        selected = self._select(provider_ids)
        semaphore = asyncio.Semaphore(self.max_concurrent_providers)
        token = cancellation_token or CollectorCancellationToken()

        tasks = [
            asyncio.create_task(
                self._execute_provider(
                    provider,
                    query,
                    semaphore=semaphore,
                    cancellation_token=token,
                )
            )
            for provider in selected
        ]

        cancelled = False
        if tasks:
            cancel_task = asyncio.create_task(token.wait_cancelled())
            gather_task = asyncio.ensure_future(
                asyncio.gather(*tasks, return_exceptions=True)
            )
            done, _ = await asyncio.wait(
                {gather_task, cancel_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancel_task in done:
                cancelled = True
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                gather_task.cancel()
                executions = tuple(
                    self._cancelled_execution(provider, token.reason)
                    for provider in selected
                )
            else:
                cancel_task.cancel()
                raw = await gather_task
                executions = tuple(
                    self._coerce_execution(provider, item)
                    for provider, item in zip(selected, raw)
                )
        else:
            executions = ()

        results = tuple(
            execution.result
            for execution in executions
            if execution.result is not None
        )
        outcomes = tuple(
            execution.outcome
            for execution in executions
        )
        effective_cancelled = (
            cancelled
            or token.is_cancelled
            or any(
                outcome.status == AsyncProviderSearchStatus.CANCELLED
                for outcome in outcomes
            )
        )
        return AsyncProviderBatchResult(
            results=results,
            outcomes=outcomes,
            started_at=started_at,
            completed_at=_utc_now(),
            elapsed_ms=round((perf_counter() - started_counter) * 1000),
            cancelled=effective_cancelled,
        )

    def _select(
        self,
        provider_ids: Sequence[str] | None,
    ) -> tuple[AsyncTenderProvider, ...]:
        if provider_ids is None:
            return self.providers
        requested = {
            provider_id.strip().casefold()
            for provider_id in provider_ids
            if provider_id.strip()
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
    ) -> _Execution:
        provider_id = provider.descriptor.id
        display_name = provider.descriptor.display_name
        if not provider.descriptor.capabilities.search:
            return _Execution(
                provider=provider,
                result=None,
                outcome=AsyncProviderSearchOutcome(
                    provider_id=provider_id,
                    display_name=display_name,
                    status=AsyncProviderSearchStatus.UNSUPPORTED,
                    elapsed_ms=0,
                    error_type="ProviderCapabilityError",
                    error_message="Источник не поддерживает поиск.",
                ),
            )

        if not self.health_monitor.can_execute(provider_id):
            snapshot = self.health_monitor.snapshot(provider_id)
            return _Execution(
                provider=provider,
                result=None,
                outcome=AsyncProviderSearchOutcome(
                    provider_id=provider_id,
                    display_name=display_name,
                    status=AsyncProviderSearchStatus.CIRCUIT_OPEN,
                    elapsed_ms=0,
                    error_type="ProviderCircuitOpenError",
                    error_message=(
                        "Источник временно пропущен: "
                        f"{snapshot.status.value}."
                    ),
                ),
            )

        started = perf_counter()
        try:
            cancellation_token.throw_if_cancelled()
            async with semaphore:
                async with asyncio.timeout(
                    self.provider_timeout_seconds
                ):
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
                message=(
                    "Источник не завершил поиск за "
                    f"{self.provider_timeout_seconds:g} сек."
                ),
            )
        except (CollectorCancelledError, asyncio.CancelledError) as exc:
            elapsed_ms = round((perf_counter() - started) * 1000)
            return self._failure_execution(
                provider,
                AsyncProviderSearchStatus.CANCELLED,
                elapsed_ms,
                exc,
                message=cancellation_token.reason,
            )
        except (TenderProviderError, Exception) as exc:
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
        return _Execution(
            provider=provider,
            result=None,
            outcome=AsyncProviderSearchOutcome(
                provider_id=provider.descriptor.id,
                display_name=provider.descriptor.display_name,
                status=status,
                elapsed_ms=elapsed_ms,
                error_type=type(error).__name__,
                error_message=message or str(error),
            ),
        )

    @staticmethod
    def _cancelled_execution(
        provider: AsyncTenderProvider,
        reason: str,
    ) -> _Execution:
        return _Execution(
            provider=provider,
            result=None,
            outcome=AsyncProviderSearchOutcome(
                provider_id=provider.descriptor.id,
                display_name=provider.descriptor.display_name,
                status=AsyncProviderSearchStatus.CANCELLED,
                elapsed_ms=0,
                error_type="CollectorCancelledError",
                error_message=reason,
            ),
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "AsyncProviderBatchResult",
    "AsyncProviderSearchEngine",
    "AsyncProviderSearchOutcome",
    "AsyncProviderSearchStatus",
]
