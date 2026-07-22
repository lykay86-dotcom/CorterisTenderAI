"""Content-addressed raw artifact ownership for the existing Collector lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from app.tenders.collector.codec import stable_hash


MAX_RAW_ARTIFACT_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class RawArtifactReference:
    reference_id: str
    content_sha256: str
    byte_length: int
    storage_path: str
    media_type: str
    encoding: str
    provider_id: str
    request_method: str
    request_url: str
    status_code: int | None
    retrieved_at: str
    query_fingerprint: str
    page_identity: str
    contract_version: str
    parser_version: str
    parse_outcome: str = "pending"
    retention_class: str = "collector_evidence"

    def __post_init__(self) -> None:
        if not self.reference_id.strip() or not self.provider_id.strip():
            raise ValueError("artifact reference identity is required")
        if len(self.content_sha256) != 64 or self.byte_length < 0:
            raise ValueError("artifact content identity is invalid")
        if self.status_code is not None and not 100 <= self.status_code <= 599:
            raise ValueError("artifact HTTP status is invalid")
        retrieved = datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00"))
        if retrieved.tzinfo is None or retrieved.utcoffset() is None:
            raise ValueError("artifact retrieval time must be timezone-aware")


class RawArtifactStore:
    """Publish bounded raw bytes once and return immutable sanitized metadata."""

    def __init__(self, root: str | Path, *, max_bytes: int = MAX_RAW_ARTIFACT_BYTES) -> None:
        self.root = Path(root).expanduser().resolve()
        if max_bytes < 1 or max_bytes > MAX_RAW_ARTIFACT_BYTES:
            raise ValueError("raw artifact byte limit is invalid")
        self.max_bytes = int(max_bytes)

    def put(
        self,
        content: bytes,
        *,
        provider_id: str,
        request_method: str,
        request_url: str,
        status_code: int | None,
        media_type: str,
        encoding: str,
        query_fingerprint: str,
        page_identity: str,
        contract_version: str,
        parser_version: str,
        retrieved_at: str | None = None,
        parse_outcome: str = "pending",
        retention_class: str = "collector_evidence",
    ) -> RawArtifactReference:
        payload = bytes(content)
        if len(payload) > self.max_bytes:
            raise ValueError("raw artifact exceeds the configured byte limit")
        digest = hashlib.sha256(payload).hexdigest()
        target = self.root / digest[:2] / f"{digest}.artifact"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.stat().st_size != len(payload) or _file_digest(target) != digest:
                raise RuntimeError("raw artifact digest collision")
        else:
            # Keep the staging name short enough for supported Windows data paths.
            temporary = target.parent / f".{uuid4().hex}.tmp"
            try:
                temporary.write_bytes(payload)
                if temporary.stat().st_size != len(payload) or _file_digest(temporary) != digest:
                    raise RuntimeError("raw artifact write verification failed")
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)

        moment = retrieved_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        safe_url = sanitize_artifact_url(request_url)
        safe_method = request_method.strip().upper()[:16]
        reference_payload = {
            "content_sha256": digest,
            "provider_id": provider_id.strip().casefold(),
            "request_method": safe_method,
            "request_url": safe_url,
            "status_code": status_code,
            "retrieved_at": moment,
            "query_fingerprint": query_fingerprint,
            "page_identity": page_identity,
            "contract_version": contract_version,
            "parser_version": parser_version,
        }
        return RawArtifactReference(
            reference_id=stable_hash(reference_payload),
            content_sha256=digest,
            byte_length=len(payload),
            storage_path=str(target),
            media_type=media_type.strip().casefold()[:120],
            encoding=encoding.strip().casefold()[:40],
            provider_id=provider_id.strip().casefold(),
            request_method=safe_method,
            request_url=safe_url,
            status_code=status_code,
            retrieved_at=moment,
            query_fingerprint=query_fingerprint,
            page_identity=page_identity,
            contract_version=contract_version,
            parser_version=parser_version,
            parse_outcome=parse_outcome.strip().casefold()[:40],
            retention_class=retention_class.strip().casefold()[:80],
        )


def sanitize_artifact_url(value: str) -> str:
    """Keep only scheme, host, optional port and path."""

    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            return ""
        host = parsed.hostname.casefold()
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        return urlunsplit((parsed.scheme.casefold(), host, parsed.path or "/", "", ""))
    except (TypeError, ValueError):
        return ""


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "MAX_RAW_ARTIFACT_BYTES",
    "RawArtifactReference",
    "RawArtifactStore",
    "sanitize_artifact_url",
]
