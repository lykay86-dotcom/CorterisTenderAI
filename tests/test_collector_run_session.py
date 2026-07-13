"""Network lifetime tests for one-shot collector sessions."""

from __future__ import annotations

import asyncio

from app.tenders.collector.run_session import CollectorRunSession
from app.tenders.provider_base import TenderSearchQuery


class FakeRuntime:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class FakeService:
    def __init__(self, result=None, error=None) -> None:
        self.result = result
        self.error = error
        self.calls = []

    async def collect(self, query, **kwargs):
        self.calls.append((query, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


def test_session_closes_runtime_after_success(tmp_path) -> None:
    async def scenario() -> None:
        runtime = FakeRuntime()
        service = FakeService(result="done")
        factory_calls = []

        def service_factory(data_directory, created_runtime, **kwargs):
            factory_calls.append((data_directory, created_runtime, kwargs))
            return service

        session = CollectorRunSession(
            tmp_path,
            runtime_factory=lambda: runtime,
            service_factory=service_factory,
        )
        result = await session.run(
            TenderSearchQuery(),
            provider_ids=("eis",),
        )

        assert result == "done"
        assert runtime.closed
        assert factory_calls[0][2]["include_commercial_catalog"]
        assert service.calls[0][1]["provider_ids"] == ("eis",)

    asyncio.run(scenario())


def test_session_closes_runtime_after_failure(tmp_path) -> None:
    async def scenario() -> None:
        runtime = FakeRuntime()
        service = FakeService(error=RuntimeError("failed"))
        session = CollectorRunSession(
            tmp_path,
            runtime_factory=lambda: runtime,
            service_factory=lambda *_args, **_kwargs: service,
        )

        try:
            await session.run(TenderSearchQuery())
        except RuntimeError:
            pass
        else:
            raise AssertionError("RuntimeError expected")

        assert runtime.closed

    asyncio.run(scenario())
