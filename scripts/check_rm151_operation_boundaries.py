"""Bounded static guards for RM-151 operation-feedback ownership boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCOPED_UI_FILES = (
    Path("app/ui/controllers/dashboard_controller.py"),
    Path("app/ui/crash_report_center_dialog.py"),
    Path("app/ui/crash_report_dialog.py"),
    Path("app/ui/pages/business_workflow_page.py"),
    Path("app/ui/tender_collector_notifications_dialog.py"),
    Path("app/ui/tender_collector_scheduler_controller.py"),
    Path("app/ui/tender_search_ui_controller.py"),
)
USER_OUTPUT_CALLS = frozenset(
    {
        "critical",
        "information",
        "setHtml",
        "setText",
        "set_analysis_error",
        "set_download_error",
        "set_error",
        "set_partial_data",
        "set_status",
        "showMessage",
        "show_error",
        "show_status",
        "warning",
    }
)
ERROR_NAMES = frozenset({"exc", "error", "exception"})
SAFE_PROJECTORS = frozenset(
    {
        "_safe_operation_error",
        "_safe_worker_failure",
        "_safe_workflow_error",
        "to_plain_text",
    }
)


def _call_name(node: ast.Call) -> str:
    function = node.func
    if isinstance(function, ast.Attribute):
        return function.attr
    if isinstance(function, ast.Name):
        return function.id
    return ""


def _contains_raw_error(node: ast.AST) -> bool:
    if isinstance(node, ast.Call) and _call_name(node) in SAFE_PROJECTORS:
        return False
    for child in ast.walk(node):
        if isinstance(child, ast.FormattedValue) and isinstance(child.value, ast.Name):
            if child.value.id.casefold() in ERROR_NAMES:
                return True
        if isinstance(child, ast.Call) and _call_name(child) in {"repr", "str"}:
            if child.args and isinstance(child.args[0], ast.Name):
                if child.args[0].id.casefold() in ERROR_NAMES:
                    return True
    return False


def _ui_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name not in USER_OUTPUT_CALLS:
            continue
        values = (*node.args, *(keyword.value for keyword in node.keywords))
        if any(_contains_raw_error(value) for value in values):
            violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: raw exception projection")
        if name == "setHtml" and any(not isinstance(value, ast.Constant) for value in values):
            violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: dynamic setHtml")
    return violations


def _core_violations() -> list[str]:
    violations: list[str] = []
    for path in sorted((ROOT / "app" / "operations").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names = (node.module or "",)
            else:
                continue
            for name in names:
                if name == "PySide6" or name.startswith("PySide6."):
                    violations.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: PySide6 in Qt-free core"
                    )
                if name == "keyring" or name.startswith("keyring."):
                    violations.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: keyring in feedback core"
                    )
    return violations


def check_repository(root: Path = ROOT) -> list[str]:
    if root.resolve() != ROOT.resolve():
        raise ValueError("RM-151 guard must run against its repository root")
    violations = _core_violations()
    for relative in SCOPED_UI_FILES:
        violations.extend(_ui_violations(ROOT / relative))

    repository_sites = 0
    for path in (ROOT / "app").rglob("*.py"):
        if "CollectorNotificationRepository(" in path.read_text(encoding="utf-8"):
            repository_sites += 1
    if repository_sites != 1:
        violations.append(
            "app: CollectorNotificationRepository must have exactly one production construction site"
        )

    shell_source = (ROOT / "app" / "ui" / "modern_main_window.py").read_text(encoding="utf-8")
    if shell_source.count("class ModernMainWindow(") != 1:
        violations.append("app/ui/modern_main_window.py: canonical shell owner count changed")
    return violations


def main() -> int:
    violations = check_repository()
    if violations:
        print("RM-151 operation boundary guard failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("RM-151 operation boundary guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
