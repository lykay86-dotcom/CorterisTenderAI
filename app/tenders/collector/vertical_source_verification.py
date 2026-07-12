"""C19 live-smoke evidence and WORKING status gate for vertical sources."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import json
from pathlib import Path
import sqlite3
from threading import RLock
from time import perf_counter
from uuid import uuid4


class VerticalSourceStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    UNVERIFIED = "unverified"
    FAILED = "failed"
    WORKING = "working"


class VerticalSmokeStage(StrEnum):
    SEARCH = "search"
    CARD = "card"
    DOCUMENTS = "documents"
    PROVENANCE = "provenance"
    VERIFICATION = "verification"
    DATABASE = "database"
    UI = "ui"
    FULL_ANALYSIS = "full_analysis"


REQUIRED_VERTICAL_STAGES = tuple(VerticalSmokeStage)


@dataclass(frozen=True, slots=True)
class VerticalSmokeStep:
    stage: VerticalSmokeStage
    passed: bool
    details: str
    artifact_count: int = 0
    elapsed_ms: int = 0

    def __post_init__(self) -> None:
        if not self.details.strip():
            raise ValueError("smoke step details must not be empty")
        if self.artifact_count < 0 or self.elapsed_ms < 0:
            raise ValueError("smoke counters must be non-negative")


@dataclass(frozen=True, slots=True)
class VerticalSourceVerification:
    verification_id: str
    provider_id: str
    connection_mode: str
    status: VerticalSourceStatus
    started_at: str
    completed_at: str
    live: bool
    steps: tuple[VerticalSmokeStep, ...]
    error_message: str = ""

    def __post_init__(self) -> None:
        if not self.verification_id.strip() or not self.provider_id.strip():
            raise ValueError("verification_id and provider_id must not be empty")
        if self.status == VerticalSourceStatus.WORKING and not self.qualifies_as_working:
            raise ValueError("WORKING requires a live pass of every C19 stage")

    @property
    def qualifies_as_working(self) -> bool:
        by_stage = {item.stage: item for item in self.steps}
        return bool(
            self.live
            and all(
                stage in by_stage and by_stage[stage].passed
                for stage in REQUIRED_VERTICAL_STAGES
            )
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "verification_id": self.verification_id,
            "provider_id": self.provider_id,
            "connection_mode": self.connection_mode,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "live": self.live,
            "steps": [
                {
                    "stage": item.stage.value,
                    "passed": item.passed,
                    "details": item.details,
                    "artifact_count": item.artifact_count,
                    "elapsed_ms": item.elapsed_ms,
                }
                for item in self.steps
            ],
            "error_message": self.error_message,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "VerticalSourceVerification":
        raw_steps = payload.get("steps", ())
        return cls(
            verification_id=str(payload.get("verification_id", "")),
            provider_id=str(payload.get("provider_id", "")),
            connection_mode=str(payload.get("connection_mode", "")),
            status=VerticalSourceStatus(str(payload.get("status", "unverified"))),
            started_at=str(payload.get("started_at", "")),
            completed_at=str(payload.get("completed_at", "")),
            live=bool(payload.get("live", False)),
            steps=tuple(
                VerticalSmokeStep(
                    stage=VerticalSmokeStage(str(item["stage"])),
                    passed=bool(item["passed"]),
                    details=str(item["details"]),
                    artifact_count=int(item.get("artifact_count", 0)),
                    elapsed_ms=int(item.get("elapsed_ms", 0)),
                )
                for item in raw_steps
                if isinstance(item, Mapping)
            ) if isinstance(raw_steps, (list, tuple)) else (),
            error_message=str(payload.get("error_message", "")),
        )


class VerticalSourceVerificationRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS collector_vertical_source_verifications (
                    verification_id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    connection_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    live INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_vertical_verification_provider
                    ON collector_vertical_source_verifications(
                        provider_id,
                        completed_at DESC
                    );
            """)

    def save(self, verification: VerticalSourceVerification) -> VerticalSourceVerification:
        self.initialize()
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO collector_vertical_source_verifications(
                    verification_id, provider_id, connection_mode, status,
                    started_at, completed_at, live, error_message, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(verification_id) DO UPDATE SET
                    status=excluded.status, completed_at=excluded.completed_at,
                    live=excluded.live, error_message=excluded.error_message,
                    payload_json=excluded.payload_json""",
                (
                    verification.verification_id,
                    verification.provider_id.casefold(),
                    verification.connection_mode,
                    verification.status.value,
                    verification.started_at,
                    verification.completed_at,
                    int(verification.live),
                    verification.error_message,
                    json.dumps(verification.to_payload(), ensure_ascii=False, sort_keys=True),
                ),
            )
        return verification

    def latest(self, provider_id: str) -> VerticalSourceVerification | None:
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """SELECT payload_json
                FROM collector_vertical_source_verifications
                WHERE provider_id = ?
                ORDER BY completed_at DESC, rowid DESC
                LIMIT 1""",
                (provider_id.strip().casefold(),),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"]))
        return VerticalSourceVerification.from_payload(payload)

    def is_working(self, provider_id: str) -> bool:
        latest = self.latest(provider_id)
        return bool(
            latest is not None
            and latest.status == VerticalSourceStatus.WORKING
            and latest.qualifies_as_working
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        return connection


SmokeCallback = Callable[[], tuple[str, int] | str | None]


class VerifiedVerticalSourceSmokeService:
    """Run injected real stages in order and persist auditable evidence."""

    def __init__(self, repository: VerticalSourceVerificationRepository) -> None:
        self.repository = repository

    def run(
        self,
        provider_id: str,
        connection_mode: str,
        callbacks: Mapping[VerticalSmokeStage, SmokeCallback],
        *,
        live: bool,
    ) -> VerticalSourceVerification:
        started_at = _now()
        steps: list[VerticalSmokeStep] = []
        error_message = ""
        for stage in REQUIRED_VERTICAL_STAGES:
            callback = callbacks.get(stage)
            if callback is None:
                steps.append(VerticalSmokeStep(stage, False, "Этап не настроен."))
                error_message = f"Не настроен этап {stage.value}."
                break
            started = perf_counter()
            try:
                output = callback()
                if isinstance(output, tuple):
                    details, artifact_count = str(output[0]), int(output[1])
                else:
                    details, artifact_count = str(output or "Этап завершён."), 0
                steps.append(VerticalSmokeStep(
                    stage, True, details, artifact_count,
                    max(0, int((perf_counter() - started) * 1000)),
                ))
            except Exception as exc:
                error_message = f"{type(exc).__name__}: {exc}"
                steps.append(VerticalSmokeStep(
                    stage, False, error_message, 0,
                    max(0, int((perf_counter() - started) * 1000)),
                ))
                break
        all_stages_passed = len(steps) == len(REQUIRED_VERTICAL_STAGES) and all(
            item.passed for item in steps
        )
        qualifies = live and all_stages_passed
        status = (
            VerticalSourceStatus.WORKING
            if qualifies
            else (
                VerticalSourceStatus.UNVERIFIED
                if all_stages_passed
                else VerticalSourceStatus.FAILED
            )
        )
        verification = VerticalSourceVerification(
            verification_id=uuid4().hex,
            provider_id=provider_id.strip().casefold(),
            connection_mode=connection_mode,
            status=status,
            started_at=started_at,
            completed_at=_now(),
            live=live,
            steps=tuple(steps),
            error_message=error_message,
        )
        return self.repository.save(verification)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "REQUIRED_VERTICAL_STAGES", "VerifiedVerticalSourceSmokeService",
    "VerticalSmokeStage", "VerticalSmokeStep", "VerticalSourceStatus",
    "VerticalSourceVerification", "VerticalSourceVerificationRepository",
]
