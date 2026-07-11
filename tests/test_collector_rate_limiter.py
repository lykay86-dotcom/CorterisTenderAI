from __future__ import annotations

import asyncio
from datetime import date

import pytest

from app.tenders.collector.rate_limiter import (
    AsyncRateLimiter,
    DailyRateLimitExceeded,
    RateLimitPolicy,
)


class FakeTime:
    def __init__(self) -> None:
        self.value = 0.0

    def clock(self) -> float:
        return self.value

    async def sleep(self, seconds: float) -> None:
        self.value += seconds
        await asyncio.sleep(0)


def test_rate_limiter_spaces_requests_and_tracks_daily_count() -> None:
    async def scenario() -> None:
        fake = FakeTime()
        limiter = AsyncRateLimiter(
            default_policy=RateLimitPolicy(
                requests_per_second=2,
                max_concurrent=1,
            ),
            clock=fake.clock,
            sleeper=fake.sleep,
            day_provider=lambda: date(2026, 7, 12),
        )
        starts: list[float] = []
        for _ in range(3):
            async with limiter.limit("https://example.org/path"):
                starts.append(fake.clock())

        assert starts == [0.0, 0.5, 1.0]
        snapshot = await limiter.snapshot("example.org")
        assert snapshot.request_count_today == 3
        assert snapshot.active_requests == 0

    asyncio.run(scenario())


def test_rate_limiter_honours_cooldown_and_daily_limit() -> None:
    async def scenario() -> None:
        fake = FakeTime()
        limiter = AsyncRateLimiter(
            default_policy=RateLimitPolicy(
                requests_per_second=100,
                max_concurrent=1,
                daily_limit=1,
            ),
            clock=fake.clock,
            sleeper=fake.sleep,
            day_provider=lambda: date(2026, 7, 12),
        )
        await limiter.block("example.org", 5)
        async with limiter.limit("example.org"):
            assert fake.clock() == 5
        with pytest.raises(DailyRateLimitExceeded):
            async with limiter.limit("example.org"):
                pass

    asyncio.run(scenario())
