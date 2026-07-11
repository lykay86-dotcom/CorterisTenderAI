from __future__ import annotations

import asyncio

import pytest

from app.tenders.collector.cancellation import (
    CollectorCancellationToken,
    CollectorCancelledError,
)


def test_cancellation_is_idempotent_and_keeps_first_reason() -> None:
    token = CollectorCancellationToken()

    assert token.cancel("Остановлено пользователем")
    assert not token.cancel("Другая причина")
    assert token.reason == "Остановлено пользователем"
    assert token.snapshot().cancelled

    with pytest.raises(CollectorCancelledError):
        token.throw_if_cancelled()


def test_cancellable_sleep_stops_promptly() -> None:
    async def scenario() -> None:
        token = CollectorCancellationToken()
        task = asyncio.create_task(token.sleep(10))
        await asyncio.sleep(0.01)
        token.cancel("stop")
        with pytest.raises(CollectorCancelledError):
            await asyncio.wait_for(task, timeout=0.3)

    asyncio.run(scenario())
