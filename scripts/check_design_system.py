"""Deterministic RM-143 design-system ownership and literal-style audit."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Iterable


MATRIX_VERSION = "rm143-style-matrix-v1"
_MATRIX_ROW = re.compile(
    r"^\| (DS-143-\d{3}) \| `([^`]+)` \|.*?\| "
    r"(MIGRATE_RM143|TOKEN_BACKED_KEEP|DEFER_RM\d+|LEGACY_COMPATIBILITY|REMOVE_DUPLICATE)(?: / [^|]+)? \|"
)
_HEX_LITERAL = re.compile(r"#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?")
_CANONICAL_NEW_SITES = frozenset(
    {
        "component_gallery.py::ComponentGallery.set_theme",
        "widgets/feedback.py::StatusBadge.apply_theme",
        "widgets/feedback.py::InlineMessage.apply_theme",
        "widgets/form.py::FormField.apply_theme",
        "widgets/form.py::FormSection.apply_theme",
    }
)


@dataclass(frozen=True, slots=True)
class MatrixEntry:
    entry_id: str
    site: str
    decision: str


@dataclass(frozen=True, slots=True)
class DesignSystemAuditReport:
    matrix_version: str
    matrix_entry_count: int
    stylesheet_site_count: int
    unregistered_stylesheet_sites: tuple[str, ...]
    raw_color_literals: tuple[str, ...]
    broad_exceptions: tuple[str, ...]

    @property
    def violations(self) -> tuple[str, ...]:
        return (
            *self.unregistered_stylesheet_sites,
            *self.raw_color_literals,
            *self.broad_exceptions,
        )

    @property
    def ok(self) -> bool:
        return not self.violations

    def to_payload(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "matrix_version": self.matrix_version,
            "matrix_entry_count": self.matrix_entry_count,
            "stylesheet_site_count": self.stylesheet_site_count,
            "unregistered_stylesheet_sites": self.unregistered_stylesheet_sites,
            "raw_color_literals": self.raw_color_literals,
            "broad_exceptions": self.broad_exceptions,
        }


def _matrix_entries(path: Path) -> tuple[MatrixEntry, ...]:
    entries: list[MatrixEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _MATRIX_ROW.match(line)
        if match:
            entries.append(MatrixEntry(*match.groups()))
    return tuple(entries)


def _stylesheet_sites(ui_root: Path) -> tuple[str, ...]:
    sites: set[str] = set()
    for path in sorted(ui_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        stack: list[str] = []

        class Visitor(ast.NodeVisitor):
            def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
                stack.append(node.name)
                self.generic_visit(node)
                stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
                stack.append(node.name)
                self.generic_visit(node)
                stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
                if isinstance(node.func, ast.Attribute) and node.func.attr == "setStyleSheet":
                    relative = path.relative_to(ui_root).as_posix()
                    sites.add(f"{relative}::{'.'.join(stack)}")
                self.generic_visit(node)

        Visitor().visit(tree)
    return tuple(sorted(sites))


def _raw_colours(ui_root: Path) -> tuple[str, ...]:
    findings: list[str] = []
    allowlist = {"theme/colors.py"}
    for path in sorted(ui_root.rglob("*.py")):
        relative = path.relative_to(ui_root).as_posix()
        if relative in allowlist:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for value in _HEX_LITERAL.findall(line):
                findings.append(f"{relative}:{line_number}:{value}")
    return tuple(findings)


def audit_design_system(root: Path) -> DesignSystemAuditReport:
    root = root.resolve()
    matrix_path = root / "docs" / "RM-143_COMPONENT_MIGRATION_MATRIX.md"
    source = matrix_path.read_text(encoding="utf-8")
    version_match = re.search(r"Matrix version: `([^`]+)`", source)
    matrix_version = version_match.group(1) if version_match else ""
    entries = _matrix_entries(matrix_path)
    registered = {entry.site for entry in entries}
    sites = _stylesheet_sites(root / "app" / "ui")
    unregistered = tuple(
        f"unregistered stylesheet site: {site}"
        for site in sites
        if site not in registered and site not in _CANONICAL_NEW_SITES
    )
    broad = tuple(
        f"broad matrix exception: {entry.site}"
        for entry in entries
        if "*" in entry.site or entry.site.endswith("/")
    )
    if matrix_version != MATRIX_VERSION:
        broad += (f"unexpected matrix version: {matrix_version or 'missing'}",)
    return DesignSystemAuditReport(
        matrix_version=matrix_version,
        matrix_entry_count=len(entries),
        stylesheet_site_count=len(sites),
        unregistered_stylesheet_sites=unregistered,
        raw_color_literals=_raw_colours(root / "app" / "ui"),
        broad_exceptions=broad,
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = audit_design_system(args.root)
    if args.format == "json":
        print(json.dumps(report.to_payload(), ensure_ascii=False, indent=2))
    else:
        print(
            f"design-system: {'OK' if report.ok else 'FAIL'}; "
            f"matrix={report.matrix_entry_count}; styles={report.stylesheet_site_count}; "
            f"violations={len(report.violations)}"
        )
        for violation in report.violations:
            print(f"- {violation}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DesignSystemAuditReport", "audit_design_system", "main"]
