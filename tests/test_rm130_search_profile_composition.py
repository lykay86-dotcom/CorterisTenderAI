"""RM-130 composition guards for the single saved-profile owner."""

from __future__ import annotations

from pathlib import Path
import re

from app.tenders.search_profile_repository import SearchProfileCatalogLoadStatus
from app.tenders.search_runtime import create_tender_search_runtime


def test_production_composes_one_repository_and_one_json_path(tmp_path) -> None:
    runtime = create_tender_search_runtime(tmp_path / "data")

    assert runtime.repository.path == tmp_path / "data" / "search_profiles.json"
    assert runtime.runner is None
    assert runtime.repository.load_result().status is SearchProfileCatalogLoadStatus.CURRENT

    source = Path("app/tenders/search_runtime.py").read_text(encoding="utf-8")
    assert source.count("TenderSearchProfileRepository(") == 1
    assert source.count('data_path / "search_profiles.json"') == 1


def test_no_second_profile_store_or_sqlite_owner_exists() -> None:
    production = Path("app")
    owners: list[Path] = []
    sqlite_mentions: list[Path] = []
    for path in production.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "TenderSearchProfileRepository(" in text:
            owners.append(path)
        if "search_profiles.sqlite" in text or re.search(
            r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+search_profiles?\b",
            text,
            flags=re.IGNORECASE,
        ):
            sqlite_mentions.append(path)

    assert owners == [Path("app/tenders/search_runtime.py")]
    assert sqlite_mentions == []


def test_existing_controller_shares_repository_with_scheduler_and_worker_seam() -> None:
    source = Path("app/ui/tender_search_ui_controller.py").read_text(encoding="utf-8")

    assert "profile_repository=self.runtime.repository" in source
    assert source.count("worker = _CollectorRunWorker(") == 1
    assert "self.runtime.runner" not in source
    assert "try_start_collector" in source
    assert "resolve_unified_tender_search(" in source
