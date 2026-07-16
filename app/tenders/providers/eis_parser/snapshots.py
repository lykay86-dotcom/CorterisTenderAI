"""Opt-in, body-only snapshots for diagnosing EIS parser drift."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

from app.core.json_serialization import json_dumps


class EisSnapshotWriter:
    def __init__(self, data_directory: Path | None) -> None:
        self.data_directory = data_directory

    @property
    def enabled(self) -> bool:
        return self.data_directory is not None

    def save_html(self, page_kind: str, html: str) -> Path | None:
        if not self.enabled:
            return None
        rendered = html.encode("utf-8")
        return self._write(page_kind, "html", rendered)

    def save_metadata(self, page_kind: str, metadata: dict[str, object]) -> Path | None:
        if not self.enabled:
            return None
        allowed = {
            key: value
            for key, value in metadata.items()
            if key in {"url", "status_code", "page_type", "parser_version", "error_type"}
        }
        rendered = json_dumps(allowed, ensure_ascii=False, indent=2).encode("utf-8")
        return self._write(f"metadata_{page_kind}", "json", rendered)

    def save_error(self, page_kind: str, error: BaseException) -> Path | None:
        if not self.enabled:
            return None
        rendered = f"{type(error).__name__}: {error}".encode("utf-8")
        return self._write(f"error_{page_kind}", "txt", rendered)

    def _write(self, page_kind: str, suffix: str, content: bytes) -> Path:
        assert self.data_directory is not None
        now = datetime.now(timezone.utc)
        directory = self.data_directory / "collector" / "debug" / "eis" / now.date().isoformat()
        directory.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(content).hexdigest()[:12]
        safe_kind = "".join(char for char in page_kind if char.isalnum() or char in "_-")
        filename = f"{safe_kind}_{now.strftime('%H%M%S_%f')}_{digest}.{suffix}"
        target = directory / filename
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        return target


__all__ = ["EisSnapshotWriter"]
