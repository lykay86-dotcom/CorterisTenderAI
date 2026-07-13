"""SQLite persistence and deterministic reuse for RM-109 AI analysis."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from app.core.ai.schemas import AiDocument, AiDocumentAnalysis


def context_fingerprint(documents: tuple[AiDocument, ...]) -> str:
    payload = [(item.document_id, item.checksum_sha256, item.verification_status) for item in documents]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class AiDocumentAnalysisRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS tender_ai_document_analyses (
                    analysis_id TEXT PRIMARY KEY,
                    registry_key TEXT NOT NULL,
                    context_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_tender_ai_analysis_reuse
                    ON tender_ai_document_analyses(registry_key, context_fingerprint, created_at DESC);
            """)

    def save(self, analysis: AiDocumentAnalysis, fingerprint: str) -> None:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO tender_ai_document_analyses VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (uuid4().hex, analysis.registry_key, fingerprint, analysis.status, json.dumps(analysis.to_payload(), ensure_ascii=False, sort_keys=True)),
            )

    def reusable(self, registry_key: str, fingerprint: str) -> AiDocumentAnalysis | None:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT payload_json FROM tender_ai_document_analyses WHERE registry_key=? AND context_fingerprint=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (registry_key.strip(), fingerprint),
            ).fetchone()
        return AiDocumentAnalysis.from_payload(json.loads(row[0])) if row else None
