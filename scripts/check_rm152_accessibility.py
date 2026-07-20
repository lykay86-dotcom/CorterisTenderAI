"""Validate RM-152 accessibility ownership and evidence artifacts."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
EVIDENCE_ROOT = ROOT / "docs" / "evidence"
FORBIDDEN_ACCESSIBILITY_IMPORTS = (
    "app.ai",
    "app.repositories",
    "app.tenders",
    "keyring",
    "requests",
    "urllib",
)


def _load_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE_ROOT / name).read_text(encoding="utf-8"))


def _accessibility_owner_errors() -> list[str]:
    errors: list[str] = []
    root = ROOT / "app" / "ui" / "accessibility"
    for path in sorted(root.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "installEventFilter" in source:
            errors.append(f"{path.relative_to(ROOT).as_posix()}: global_event_filter_forbidden")
        tree = ast.parse(source, filename=str(path))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        for module in imported:
            if module.startswith(FORBIDDEN_ACCESSIBILITY_IMPORTS):
                errors.append(f"{path.relative_to(ROOT).as_posix()}: forbidden_import:{module}")
    return errors


def validate(*, require_native_complete: bool = False) -> tuple[str, ...]:
    from app.ui.accessibility.native_matrix import validate_native_matrix
    from app.ui.theme.colors import DARK_PALETTE, LIGHT_PALETTE
    from app.ui.theme.contrast_inventory import build_contrast_inventory
    from scripts.audit_ui_inventory import build_inventory, summary

    errors = _accessibility_owner_errors()

    inventory_summary = summary(build_inventory())
    if inventory_summary["literal_colors_outside_theme"]:
        errors.append("ui: literal_colors_outside_theme")

    contrast = _load_json("RM-152_CONTRAST_PAIRS.json")
    expected_pairs = [
        *build_contrast_inventory(DARK_PALETTE),
        *build_contrast_inventory(LIGHT_PALETTE),
    ]
    if contrast.get("schema") != "rm152-contrast-inventory-v1":
        errors.append("contrast: unsupported_schema")
    if contrast.get("pairs") != expected_pairs:
        errors.append("contrast: artifact_does_not_match_theme_tokens")
    if any(row["result"] == "FAIL" for row in expected_pairs):
        errors.append("contrast: threshold_failure")

    matrix = _load_json("RM-152_NATIVE_MATRIX.json")
    errors.extend(validate_native_matrix(matrix, require_complete=require_native_complete))
    return tuple(errors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-native-complete", action="store_true")
    arguments = parser.parse_args()
    errors = validate(require_native_complete=arguments.require_native_complete)
    if errors:
        print("\n".join(errors))
        return 1
    print("RM-152 accessibility guards passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
