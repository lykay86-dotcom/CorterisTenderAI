"""Create and validate a consistent SQLite backup before collector migration."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

PATCH_ROOT = Path(__file__).resolve().parents[1]


def backup_database(
    source: str | Path,
    destination_directory: str | Path,
) -> Path | None:
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        return None
    destination_dir = Path(destination_directory).expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = destination_dir / (f"{source_path.stem}_{timestamp}{source_path.suffix}")

    with sqlite3.connect(source_path) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)
            check = destination_connection.execute("PRAGMA quick_check").fetchone()
            if check is None or str(check[0]).casefold() != "ok":
                raise RuntimeError(f"SQLite backup quick_check failed: {check!r}")
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="",
        help="CorterisTenderAI project root used to resolve user data.",
    )
    parser.add_argument(
        "--source",
        default="",
        help="Explicit tender_registry.sqlite3 path.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for the verified SQLite backup.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.source:
        source = Path(args.source)
    else:
        project_root = Path(args.project_root or PATCH_ROOT).expanduser().resolve()
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from app.core.path_manager import PathManager

        source = PathManager(project_dir=project_root).paths.data_dir / "tender_registry.sqlite3"
    backup = backup_database(source, args.output_dir)
    if backup is None:
        print(f"Collector database not found; backup skipped: {source}")
        return 0
    print(f"Collector database backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
