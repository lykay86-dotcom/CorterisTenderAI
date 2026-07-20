"""Static regression guards for RM-151 feedback and owner boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.check_rm151_operation_boundaries import ROOT, check_repository


def test_operation_core_is_qt_free_and_uses_immutable_contract_modules() -> None:
    operations = ROOT / "app" / "operations"
    sources = tuple(sorted(operations.glob("*.py")))

    assert sources
    assert all("PySide6" not in path.read_text(encoding="utf-8") for path in sources)
    for path in sources:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_bounded_operation_boundary_guard_is_clean() -> None:
    assert check_repository() == []


def test_notification_repository_has_one_existing_production_owner() -> None:
    construction_sites = []
    for path in (ROOT / "app").rglob("*.py"):
        if "CollectorNotificationRepository(" in path.read_text(encoding="utf-8"):
            construction_sites.append(path.relative_to(ROOT))

    assert construction_sites == [Path("app/ui/tender_collector_scheduler_controller.py")]
