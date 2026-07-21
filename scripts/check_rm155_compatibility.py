"""Fail-closed source guard for the accepted RM-155 retirement decisions."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).parents[1]
OLD_MODULE = "app.ui.main_window"
FORBIDDEN_PRODUCTION_TOKENS = (
    "quotes_page",
    "estimates_page",
    "apply_compatibility_search_text",
)
REQUIRED_CANDIDATES = tuple(f"RM155-COMP-{number:03d}" for number in range(1, 33))


def _python_files(roots: Iterable[Path]) -> tuple[Path, ...]:
    return tuple(
        sorted(
            path for root in roots for path in root.rglob("*.py") if "__pycache__" not in path.parts
        )
    )


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    return imported


def violations(root: Path = ROOT) -> tuple[str, ...]:
    problems: list[str] = []
    retired_path = root / "app" / "ui" / "main_window.py"
    if retired_path.exists():
        problems.append("retired module exists: app/ui/main_window.py")

    scanned = _python_files((root / "app", root / "scripts", root / "tests"))
    for path in scanned:
        relative = path.relative_to(root).as_posix()
        if OLD_MODULE in _imported_modules(path):
            problems.append(f"retired import: {relative}")

    for relative in (
        "app/bootstrap.py",
        "app/ui/modern_main_window.py",
        "app/ui/pages/tender_workspace_page.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        for token in FORBIDDEN_PRODUCTION_TOKENS:
            if token in source:
                problems.append(f"retired production token {token}: {relative}")

    bootstrap = (root / "app" / "bootstrap.py").read_text(encoding="utf-8")
    if 'for attribute in ("workflow_page",):' not in bootstrap:
        problems.append("canonical support-bundle lookup is missing")

    spec = (root / "installer" / "corteris_tender_ai.spec").read_text(encoding="utf-8")
    for token in (OLD_MODULE, "rm154-visual-artifacts", "rm154-v1"):
        if token in spec:
            problems.append(f"forbidden frozen input: {token}")

    inventory = (root / "docs" / "RM-155_COMPATIBILITY_INVENTORY.md").read_text(encoding="utf-8")
    for candidate in REQUIRED_CANDIDATES:
        if inventory.count(candidate) != 1:
            problems.append(f"inventory candidate must occur exactly once: {candidate}")
    return tuple(problems)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    problems = violations(args.root.resolve())
    if problems:
        for problem in problems:
            print(problem)
        return 1
    print("RM-155 compatibility guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
