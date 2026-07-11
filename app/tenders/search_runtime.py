"""Composition root for the tender-search subsystem."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.tenders.corteris_search import CorterisTenderSearchService
from app.tenders.http_client import HttpTransport
from app.tenders.provider_factory import create_default_provider_registry
from app.tenders.provider_registry import TenderProviderRegistry
from app.tenders.search_engine import TenderSearchEngine
from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.tenders.search_profile_runner import TenderSearchProfileRunner


@dataclass(frozen=True, slots=True)
class TenderSearchRuntime:
    """Ready-to-use tender-search services sharing one configuration."""

    data_directory: Path
    repository: TenderSearchProfileRepository
    registry: TenderProviderRegistry
    engine: TenderSearchEngine
    search_service: CorterisTenderSearchService
    runner: TenderSearchProfileRunner


def create_tender_search_runtime(
    data_directory: str | Path,
    *,
    http_transport: HttpTransport | None = None,
    max_workers: int = 6,
    timeout_seconds: float = 35.0,
) -> TenderSearchRuntime:
    """Build the production tender-search graph without network activity.

    Network requests are made only when ``runner.run(...)`` is called.
    """

    data_path = Path(data_directory).expanduser()
    data_path.mkdir(parents=True, exist_ok=True)

    repository = TenderSearchProfileRepository(
        data_path / "search_profiles.json"
    )
    repository.initialize()

    registry = create_default_provider_registry(
        http_transport=http_transport
    )
    engine = TenderSearchEngine(
        registry,
        max_workers=max_workers,
        timeout_seconds=timeout_seconds,
    )
    search_service = CorterisTenderSearchService(engine)
    runner = TenderSearchProfileRunner(repository, search_service)

    return TenderSearchRuntime(
        data_directory=data_path,
        repository=repository,
        registry=registry,
        engine=engine,
        search_service=search_service,
        runner=runner,
    )


__all__ = [
    "TenderSearchRuntime",
    "create_tender_search_runtime",
]
