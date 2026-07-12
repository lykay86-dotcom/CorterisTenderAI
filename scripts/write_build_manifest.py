"""Create a reproducible hash manifest for Windows release artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import sys
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.version import APP_NAME, APP_VERSION


DISTRIBUTIONS = (
    "PySide6",
    "httpx",
    "httpcore",
    "certifi",
    "SQLAlchemy",
    "pydantic",
    "keyring",
    "cryptography",
    "py7zr",
    "rarfile",
    "pyinstaller",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--installer", type=Path, default=None)
    parser.add_argument("--self-test", type=Path, default=None)
    args = parser.parse_args(argv)

    artifacts = [_artifact(args.exe, "application")]
    if args.installer is not None and args.installer.is_file():
        artifacts.append(_artifact(args.installer, "installer"))
    if args.self_test is not None and args.self_test.is_file():
        artifacts.append(_artifact(args.self_test, "self_test_report"))

    manifest = {
        "application": APP_NAME,
        "version": APP_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": _versions(DISTRIBUTIONS),
        "artifacts": artifacts,
    }
    target = args.output.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(target)
    return 0


def _artifact(path: Path, kind: str) -> dict[str, object]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    digest = hashlib.sha256()
    with resolved.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "kind": kind,
        "path": str(resolved),
        "filename": resolved.name,
        "size_bytes": resolved.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def _versions(names: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in names:
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = "not installed"
    return result


if __name__ == "__main__":
    raise SystemExit(main())
