"""Build traceable RM-109 AI context from locally extracted tender text."""

from __future__ import annotations

from pathlib import Path

from app.core.ai.schemas import AiDocument


class TenderDocumentContextBuilder:
    """Never reads original files or downloads data; uses extraction results only."""

    def __init__(self, text_service: object) -> None:
        self.text_service = text_service

    def build(self, registry_key: str) -> tuple[AiDocument, ...]:
        records = self.text_service.list_results(registry_key)
        documents: list[AiDocument] = []
        for record in records:
            if not record.available_locally:
                continue
            text = self.text_service.read_text(record).strip()
            if not text:
                continue
            name = record.source_path.name if record.source_path else record.document_key
            documents.append(
                AiDocument(
                    document_id=record.document_key,
                    name=name,
                    source=str(record.source_path or "local_document_store"),
                    document_type=Path(name).suffix.lower().lstrip(".") or "unknown",
                    received_at=record.extracted_at,
                    verification_status=record.status.value,
                    text=text,
                    checksum_sha256=record.checksum_sha256,
                )
            )
        return tuple(documents)
