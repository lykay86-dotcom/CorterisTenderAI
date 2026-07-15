"""Versioned SQLite persistence and deterministic Tender Intelligence cache."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Mapping
from uuid import uuid4

from app.core.ai.citations import CITATION_RESOLVER_VERSION
from app.core.ai.document_context import AI_CONTEXT_VERSION
from app.core.ai.execution_contract import (
    AI_ANALYZER_VERSION,
    AiExecutionContract,
    execution_contract_matches,
)
from app.core.ai.output_schema import AI_PROVIDER_OUTPUT_SCHEMA_VERSION
from app.core.ai.prompts import AI_PROMPT_VERSION
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiAnalysisStatus,
    AiDocument,
    AiDocumentAnalysis,
)


_CACHE_CORRUPT_WARNING = "Повреждённая запись AI-анализа пропущена."
_CACHE_INCOMPATIBLE_WARNING = "Кеш AI-анализа имеет несовместимую версию."
_CACHE_SKIPPED_WARNING = "Повреждённая или несовместимая запись AI-анализа пропущена."


def context_fingerprint(
    documents: tuple[AiDocument, ...],
    *,
    prompt_version: str | None = None,
    schema_version: int | None = None,
    analyzer_version: str | None = None,
    provider_output_schema_version: str | None = None,
    context_version: str | None = None,
    citation_resolver_version: str | None = None,
    context_parameters: Mapping[str, object] | None = None,
) -> str:
    """Hash logical context independently of input ordering."""
    ordered = sorted(
        (
            {
                "document_id": item.document_id,
                "checksum": item.checksum_sha256,
                "verification_status": item.verification_status,
                "truncated": item.truncated,
                "original_character_count": item.original_character_count,
                "document_kind": item.document_kind,
            }
            for item in documents
        ),
        key=lambda item: (
            str(item["document_id"]),
            str(item["checksum"]),
            str(item["verification_status"]),
        ),
    )
    payload = {
        "documents": ordered,
        "versions": {
            "prompt": prompt_version or AI_PROMPT_VERSION,
            "schema": (AI_ANALYSIS_SCHEMA_VERSION if schema_version is None else schema_version),
            "analyzer": analyzer_version or AI_ANALYZER_VERSION,
            "provider_output_schema": (
                provider_output_schema_version or AI_PROVIDER_OUTPUT_SCHEMA_VERSION
            ),
            "context": context_version or AI_CONTEXT_VERSION,
            "citation_resolver": citation_resolver_version or CITATION_RESOLVER_VERSION,
        },
        "context_parameters": _canonical_context_parameters(context_parameters),
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _canonical_context_parameters(
    context_parameters: Mapping[str, object] | None,
) -> dict[str, object]:
    parameters = dict(context_parameters or {})
    inventory = parameters.get("documentation_inventory")
    if isinstance(inventory, (list, tuple)):
        parameters["documentation_inventory"] = sorted(
            inventory,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    return parameters


@dataclass(frozen=True, slots=True)
class AiCacheLookupResult:
    """Analysis and warnings owned by one immutable repository lookup."""

    analysis: AiDocumentAnalysis | None
    warnings: tuple[str, ...] = ()
    skipped_rows: int = 0


class AiDocumentAnalysisRepository:
    """Append-only analysis history with recovery from bad rows."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tender_ai_document_analyses (
                    analysis_id TEXT PRIMARY KEY,
                    registry_key TEXT NOT NULL,
                    context_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_version INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(tender_ai_document_analyses)")
            }
            if "payload_version" not in columns:
                connection.execute(
                    "ALTER TABLE tender_ai_document_analyses "
                    "ADD COLUMN payload_version INTEGER NOT NULL DEFAULT 1"
                )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tender_ai_analysis_reuse
                ON tender_ai_document_analyses(
                    registry_key,
                    context_fingerprint,
                    created_at DESC
                )
                """
            )

    def save(self, analysis: AiDocumentAnalysis, fingerprint: str) -> None:
        self.initialize()
        created_at = _timezone_aware(analysis.created_at)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO tender_ai_document_analyses (
                    analysis_id,
                    registry_key,
                    context_fingerprint,
                    status,
                    payload_json,
                    created_at,
                    payload_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    analysis.registry_key,
                    fingerprint,
                    AiAnalysisStatus(analysis.status).value,
                    json.dumps(
                        analysis.to_payload(),
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    created_at,
                    analysis.payload_version,
                ),
            )

    def reusable(
        self,
        registry_key: str,
        fingerprint: str,
        expected_execution_contract: AiExecutionContract,
    ) -> AiCacheLookupResult:
        rows = self._rows(
            "registry_key=? AND context_fingerprint=?",
            (registry_key.strip(), fingerprint),
        )
        return self._latest_valid(
            rows,
            expected_registry_key=registry_key.strip(),
            return_incompatible=False,
            reusable_fingerprint=fingerprint,
            expected_execution_contract=expected_execution_contract,
        )

    def latest(self, registry_key: str) -> AiDocumentAnalysis | None:
        rows = self._rows("registry_key=?", (registry_key.strip(),))
        return self._latest_valid(
            rows,
            expected_registry_key=registry_key.strip(),
            return_incompatible=True,
            reusable_fingerprint=None,
            expected_execution_contract=None,
        ).analysis

    def _rows(
        self,
        where: str,
        parameters: tuple[object, ...],
    ) -> list[tuple[str, object]]:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            return list(
                connection.execute(
                    "SELECT payload_json, payload_version "
                    "FROM tender_ai_document_analyses "
                    f"WHERE {where} ORDER BY created_at DESC, rowid DESC",
                    parameters,
                )
            )

    def _latest_valid(
        self,
        rows: list[tuple[str, object]],
        *,
        expected_registry_key: str,
        return_incompatible: bool,
        reusable_fingerprint: str | None,
        expected_execution_contract: AiExecutionContract | None,
    ) -> AiCacheLookupResult:
        incompatible: AiDocumentAnalysis | None = None
        saw_corruption = False
        skipped_rows = 0
        for payload_json, stored_version in rows:
            if type(stored_version) is not int:
                saw_corruption = True
                skipped_rows += 1
                continue
            if stored_version > AI_ANALYSIS_SCHEMA_VERSION or stored_version < 1:
                incompatible = AiDocumentAnalysis(
                    expected_registry_key,
                    "",
                    status=AiAnalysisStatus.CACHE_INCOMPATIBLE,
                    payload_version=stored_version,
                )
                skipped_rows += 1
                continue
            try:
                payload = json.loads(payload_json, object_pairs_hook=_unique_json_object)
            except (TypeError, UnicodeDecodeError, ValueError):
                saw_corruption = True
                skipped_rows += 1
                continue
            analysis = AiDocumentAnalysis.from_payload(payload)
            if analysis.payload_version != stored_version:
                saw_corruption = True
                skipped_rows += 1
                continue
            if analysis.status == AiAnalysisStatus.CACHE_INCOMPATIBLE:
                incompatible = analysis
                skipped_rows += 1
                continue
            if analysis.status == AiAnalysisStatus.INVALID_RESPONSE:
                saw_corruption = True
                skipped_rows += 1
                continue
            if analysis.registry_key != expected_registry_key:
                saw_corruption = True
                skipped_rows += 1
                continue
            if reusable_fingerprint is not None and (
                analysis.payload_version != AI_ANALYSIS_SCHEMA_VERSION
                or analysis.provenance is None
                or analysis.provenance.context_fingerprint != reusable_fingerprint
            ):
                saw_corruption = True
                skipped_rows += 1
                continue
            if expected_execution_contract is not None and not execution_contract_matches(
                analysis.provenance,
                expected_execution_contract,
            ):
                skipped_rows += 1
                continue
            warnings = (
                (_CACHE_SKIPPED_WARNING,) if saw_corruption or incompatible is not None else ()
            )
            return AiCacheLookupResult(
                analysis=analysis,
                warnings=warnings,
                skipped_rows=skipped_rows,
            )
        if saw_corruption:
            warnings = (_CACHE_CORRUPT_WARNING,)
        elif incompatible is not None:
            warnings = (_CACHE_INCOMPATIBLE_WARNING,)
        else:
            warnings = ()
        return AiCacheLookupResult(
            analysis=incompatible if return_incompatible else None,
            warnings=warnings,
            skipped_rows=skipped_rows,
        )


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _timezone_aware(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat(timespec="seconds")


__all__ = [
    "AI_ANALYZER_VERSION",
    "AI_CONTEXT_VERSION",
    "AI_PROMPT_VERSION",
    "AiCacheLookupResult",
    "AiDocumentAnalysisRepository",
    "context_fingerprint",
]
