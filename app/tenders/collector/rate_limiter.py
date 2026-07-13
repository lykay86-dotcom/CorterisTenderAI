"""Per-domain asynchronous rate limiting for tender sources."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from time import monotonic
from typing import AsyncIterator, Awaitable, Callable, Mapping
from urllib.parse import urlparse

from app.tenders.collector.cancellation import CollectorCancellationToken


class DailyRateLimitExceeded(RuntimeError):
    """Raised when a configured daily request budget is exhausted."""


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    requests_per_second: float = 1.0
    max_concurrent: int = 2
    min_interval_seconds: float = 0.0
    max_retries: int = 3
    block_after_429_seconds: float = 60.0
    daily_limit: int | None = None

    def __post_init__(self) -> None:
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        if self.max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        if self.min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must be non-negative")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.block_after_429_seconds < 0:
            raise ValueError("block_after_429_seconds must be non-negative")
        if self.daily_limit is not None and self.daily_limit < 1:
            raise ValueError("daily_limit must be positive")

    @property
    def effective_interval_seconds(self) -> float:
        return max(
            self.min_interval_seconds,
            1.0 / self.requests_per_second,
        )


@dataclass(frozen=True, slots=True)
class RateLimitSnapshot:
    domain: str
    active_requests: int
    request_count_today: int
    daily_limit: int | None
    blocked_for_seconds: float
    effective_interval_seconds: float


class _DomainState:
    def __init__(self, policy: RateLimitPolicy) -> None:
        self.policy = policy
        self.semaphore = asyncio.Semaphore(policy.max_concurrent)
        self.lock = asyncio.Lock()
        self.last_started_at: float | None = None
        self.blocked_until = 0.0
        self.day = date.today()
        self.request_count_today = 0
        self.active_requests = 0


class AsyncRateLimiter:
    """Limit starts, concurrency, cooldowns and daily quotas by domain."""

    def __init__(
        self,
        *,
        default_policy: RateLimitPolicy | None = None,
        domain_policies: Mapping[str, RateLimitPolicy] | None = None,
        clock: Callable[[], float] = monotonic,
        day_provider: Callable[[], date] = date.today,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.default_policy = default_policy or RateLimitPolicy()
        self._domain_policies = {
            self.normalize_domain(key): value for key, value in (domain_policies or {}).items()
        }
        self._clock = clock
        self._day_provider = day_provider
        self._sleeper = sleeper
        self._states: dict[str, _DomainState] = {}
        self._states_lock = asyncio.Lock()

    @staticmethod
    def normalize_domain(value: str) -> str:
        candidate = value.strip()
        parsed = urlparse(candidate if "://" in candidate else f"//{candidate}")
        hostname = (parsed.hostname or candidate).strip().casefold().rstrip(".")
        if not hostname:
            raise ValueError("domain must not be empty")
        return hostname

    def policy_for(self, value: str) -> RateLimitPolicy:
        domain = self.normalize_domain(value)
        return self._domain_policies.get(domain, self.default_policy)

    async def _state_for(self, value: str) -> tuple[str, _DomainState]:
        domain = self.normalize_domain(value)
        async with self._states_lock:
            state = self._states.get(domain)
            if state is None:
                state = _DomainState(self.policy_for(domain))
                state.day = self._day_provider()
                self._states[domain] = state
        return domain, state

    async def block(self, value: str, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        _, state = await self._state_for(value)
        async with state.lock:
            state.blocked_until = max(
                state.blocked_until,
                self._clock() + float(seconds),
            )

    async def snapshot(self, value: str) -> RateLimitSnapshot:
        domain, state = await self._state_for(value)
        async with state.lock:
            self._roll_day(state)
            return RateLimitSnapshot(
                domain=domain,
                active_requests=state.active_requests,
                request_count_today=state.request_count_today,
                daily_limit=state.policy.daily_limit,
                blocked_for_seconds=max(
                    0.0,
                    state.blocked_until - self._clock(),
                ),
                effective_interval_seconds=(state.policy.effective_interval_seconds),
            )

    @asynccontextmanager
    async def limit(
        self,
        value: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> AsyncIterator[None]:
        """Wait for a domain slot and release it after the request."""

        _, state = await self._state_for(value)
        await self._acquire_semaphore(
            state,
            cancellation_token=cancellation_token,
        )
        try:
            await self._wait_for_start(
                state,
                cancellation_token=cancellation_token,
            )
            async with state.lock:
                state.active_requests += 1
            try:
                yield
            finally:
                async with state.lock:
                    state.active_requests = max(
                        0,
                        state.active_requests - 1,
                    )
        finally:
            state.semaphore.release()

    async def _acquire_semaphore(
        self,
        state: _DomainState,
        *,
        cancellation_token: CollectorCancellationToken | None,
    ) -> None:
        if cancellation_token is None:
            await state.semaphore.acquire()
            return

        cancellation_token.throw_if_cancelled()
        acquire_task = asyncio.create_task(state.semaphore.acquire())
        cancel_task = asyncio.create_task(cancellation_token.wait_cancelled())
        done, pending = await asyncio.wait(
            {acquire_task, cancel_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        if cancel_task in done:
            if acquire_task.done() and not acquire_task.cancelled():
                try:
                    acquired = bool(acquire_task.result())
                except BaseException:
                    acquired = False
                if acquired:
                    state.semaphore.release()
            else:
                acquire_task.cancel()
            cancellation_token.throw_if_cancelled()
        await acquire_task

    async def _wait_for_start(
        self,
        state: _DomainState,
        *,
        cancellation_token: CollectorCancellationToken | None,
    ) -> None:
        while True:
            if cancellation_token is not None:
                cancellation_token.throw_if_cancelled()

            async with state.lock:
                self._roll_day(state)
                policy = state.policy
                if (
                    policy.daily_limit is not None
                    and state.request_count_today >= policy.daily_limit
                ):
                    raise DailyRateLimitExceeded("Дневной лимит запросов к источнику исчерпан.")

                now = self._clock()
                wait_for = max(0.0, state.blocked_until - now)
                if state.last_started_at is not None:
                    wait_for = max(
                        wait_for,
                        policy.effective_interval_seconds - (now - state.last_started_at),
                    )

                if wait_for <= 0:
                    state.last_started_at = now
                    state.request_count_today += 1
                    return

            await self._sleep(
                wait_for,
                cancellation_token=cancellation_token,
            )

    async def _sleep(
        self,
        seconds: float,
        *,
        cancellation_token: CollectorCancellationToken | None,
    ) -> None:
        if cancellation_token is None:
            await self._sleeper(seconds)
        else:
            await cancellation_token.sleep(
                seconds,
                sleeper=self._sleeper,
            )

    def _roll_day(self, state: _DomainState) -> None:
        current = self._day_provider()
        if state.day != current:
            state.day = current
            state.request_count_today = 0


__all__ = [
    "AsyncRateLimiter",
    "DailyRateLimitExceeded",
    "RateLimitPolicy",
    "RateLimitSnapshot",
]
