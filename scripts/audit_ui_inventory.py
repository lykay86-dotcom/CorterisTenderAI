"""Produce a deterministic, read-only inventory of the current Qt UI surface."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Final


ROOT: Final[Path] = Path(__file__).resolve().parents[1]
UI_ROOT: Final[Path] = ROOT / "app" / "ui"
TEST_ROOT: Final[Path] = ROOT / "tests"
HEX_COLOR: Final[re.Pattern[str]] = re.compile(r"#[0-9A-Fa-f]{3,8}\b")


@dataclass(frozen=True, slots=True)
class ModuleInventory:
    module: str
    path: str
    lines: int
    classification: str
    classes: tuple[str, ...]
    app_imports: tuple[str, ...]
    tests: tuple[str, ...]
    stylesheet_calls: int
    literal_colors: tuple[str, ...]
    accessible_name_calls: int
    accessible_description_calls: int
    label_buddy_calls: int
    fixed_dimension_calls: int
    minimum_dimension_calls: int
    maximum_dimension_calls: int
    table_widget_calls: int
    table_view_calls: int
    timer_calls: int
    thread_calls: int


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to(ROOT).with_suffix("").parts)


def _call_name(node: ast.Call) -> str:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return ""


def _classify(module: str) -> str:
    if module.endswith(".__init__"):
        return "COMPATIBILITY_ONLY"
    if module == "app.ui.modern_main_window":
        return "PRODUCTION_ROOT"
    if module == "app.ui.main_window":
        return "EMBEDDED_LEGACY"
    if module == "app.ui.pages.tender_workspace_page":
        return "COMPATIBILITY_ONLY"
    if module in {
        "app.ui.pages.dashboard_page",
        "app.ui.pages.business_workflow_page",
    }:
        return "PRODUCTION_PAGE"
    if module in {
        "app.ui.ai_provider_settings",
        "app.ui.business_workflow.system_health_badge",
        "app.ui.tender_search_profile_editor",
        "app.ui.tender_unified_search_panel",
    }:
        return "PRESENTATION_COMPONENT"
    if ".controllers." in module or module.endswith("_controller"):
        return "CONTROLLER"
    if ".viewmodels." in module:
        return "VIEWMODEL"
    if ".theme." in module:
        return "THEME_RESOURCE"
    if ".widgets." in module or ".dashboard." in module:
        return "PRESENTATION_COMPONENT"
    if module.endswith("_dialog") or ".dialogs" in module:
        return "PRODUCTION_DIALOG"
    if ".business_workflow.model" in module:
        return "UI_MODEL"
    return "UNKNOWN"


def _test_consumers(module: str, test_sources: dict[str, str]) -> tuple[str, ...]:
    return tuple(path for path, source in test_sources.items() if module in source)


def inspect_module(path: Path, test_sources: dict[str, str]) -> ModuleInventory:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    module = _module_name(path)
    classes: list[str] = []
    imports: set[str] = set()
    calls: Counter[str] = Counter()

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names if alias.name.startswith("app."))
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app."):
            imports.add(node.module)
        elif isinstance(node, ast.Call):
            calls[_call_name(node)] += 1

    relative_path = path.relative_to(ROOT).as_posix()
    literal_colors = ()
    if module not in {"app.ui.theme.colors", "app.ui.theme.stylesheet"}:
        literal_colors = tuple(sorted(set(HEX_COLOR.findall(source))))

    return ModuleInventory(
        module=module,
        path=relative_path,
        lines=len(source.splitlines()),
        classification=_classify(module),
        classes=tuple(classes),
        app_imports=tuple(sorted(imports)),
        tests=_test_consumers(module, test_sources),
        stylesheet_calls=calls["setStyleSheet"],
        literal_colors=literal_colors,
        accessible_name_calls=calls["setAccessibleName"],
        accessible_description_calls=calls["setAccessibleDescription"],
        label_buddy_calls=calls["setBuddy"],
        fixed_dimension_calls=(
            calls["setFixedWidth"] + calls["setFixedHeight"] + calls["setFixedSize"]
        ),
        minimum_dimension_calls=(
            calls["setMinimumWidth"] + calls["setMinimumHeight"] + calls["setMinimumSize"]
        ),
        maximum_dimension_calls=(
            calls["setMaximumWidth"] + calls["setMaximumHeight"] + calls["setMaximumSize"]
        ),
        table_widget_calls=calls["QTableWidget"],
        table_view_calls=calls["QTableView"],
        timer_calls=calls["QTimer"],
        thread_calls=calls["QThread"],
    )


def build_inventory() -> tuple[ModuleInventory, ...]:
    test_sources = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(TEST_ROOT.glob("test_*.py"))
        if "app.ui" in path.read_text(encoding="utf-8")
        or "PySide6" in path.read_text(encoding="utf-8")
    }
    return tuple(inspect_module(path, test_sources) for path in sorted(UI_ROOT.rglob("*.py")))


def summary(inventory: tuple[ModuleInventory, ...]) -> dict[str, object]:
    return {
        "module_count": len(inventory),
        "line_count": sum(item.lines for item in inventory),
        "classification_counts": dict(
            sorted(Counter(item.classification for item in inventory).items())
        ),
        "ui_test_module_count": len({test for item in inventory for test in item.tests}),
        "stylesheet_calls": sum(item.stylesheet_calls for item in inventory),
        "literal_colors_outside_theme": sorted(
            {color for item in inventory for color in item.literal_colors}
        ),
        "accessible_name_calls": sum(item.accessible_name_calls for item in inventory),
        "accessible_description_calls": sum(
            item.accessible_description_calls for item in inventory
        ),
        "label_buddy_calls": sum(item.label_buddy_calls for item in inventory),
        "fixed_dimension_calls": sum(item.fixed_dimension_calls for item in inventory),
        "minimum_dimension_calls": sum(item.minimum_dimension_calls for item in inventory),
        "maximum_dimension_calls": sum(item.maximum_dimension_calls for item in inventory),
        "table_widget_calls": sum(item.table_widget_calls for item in inventory),
        "table_view_calls": sum(item.table_view_calls for item in inventory),
        "timer_calls": sum(item.timer_calls for item in inventory),
        "thread_calls": sum(item.thread_calls for item in inventory),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    arguments = parser.parse_args()
    inventory = build_inventory()
    payload = {
        "baseline": "working-tree",
        "summary": summary(inventory),
        "modules": [asdict(item) for item in inventory],
    }
    if arguments.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
