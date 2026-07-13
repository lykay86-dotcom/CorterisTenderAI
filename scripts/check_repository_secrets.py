"""Fail the quality gate on common high-confidence credential formats."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_FILE_BYTES = 5 * 1024 * 1024
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
)


def scan_text(text: str) -> tuple[str, ...]:
    """Return labels for high-confidence secret formats without exposing values."""

    return tuple(label for label, pattern in SECRET_PATTERNS if pattern.search(text))


def tracked_files(root: Path = ROOT) -> tuple[Path, ...]:
    """Return only files in the Git index; ignored local data is out of scope."""

    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return tuple(
        root / item.decode("utf-8", errors="surrogateescape")
        for item in completed.stdout.split(b"\0")
        if item
    )


def scan_repository(paths: Iterable[Path] | None = None) -> tuple[tuple[str, str], ...]:
    """Scan tracked text files and return relative path plus finding label."""

    findings: list[tuple[str, str]] = []
    for path in paths if paths is not None else tracked_files():
        try:
            if not path.is_file() or path.stat().st_size > MAX_TEXT_FILE_BYTES:
                continue
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\0" in raw:
            continue
        text = raw.decode("utf-8", errors="replace")
        for label in scan_text(text):
            findings.append((path.relative_to(ROOT).as_posix(), label))
    return tuple(findings)


def main() -> int:
    findings = scan_repository()
    if not findings:
        print("Repository secret scan passed.")
        return 0
    for path, label in findings:
        print(f"Potential {label} in tracked file: {path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
