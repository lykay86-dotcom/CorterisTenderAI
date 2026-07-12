"""Optional bridge from collected tenders to the existing AnalysisEngine."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from app.parsers.documents import classify_document
from app.repositories.tenders import TenderRepository
from app.tender_analysis.engine import AnalysisEngine
from app.tenders.document_text_extractor import StoredDocumentText, TenderDocumentTextService
from app.tenders.models import UnifiedTender


@dataclass(frozen=True, slots=True)
class LegacyAnalysisBridgeResult:
    tender_id: str
    imported_documents: int
    reused_documents: int
    report: dict[str, object]


class LegacyAnalysisBridge:
    """Populate the legacy analysis repository without duplicating documents."""

    def __init__(
        self,
        repository: TenderRepository | None = None,
        engine_factory=AnalysisEngine,
    ) -> None:
        self.repository = repository or TenderRepository()
        self.engine_factory = engine_factory

    def sync_and_analyze(
        self,
        tender: UnifiedTender,
        text_service: TenderDocumentTextService,
        texts: Iterable[StoredDocumentText],
    ) -> LegacyAnalysisBridgeResult:
        legacy = self._find_or_create_tender(tender)
        existing = self.repository.documents(legacy.id)
        existing_paths = {str(item.path).casefold() for item in existing}
        existing_names = {str(item.name).casefold() for item in existing}
        imported = 0
        reused = 0

        for result in texts:
            if not result.available_locally:
                continue
            source = result.source_path or result.text_path
            if source is None:
                continue
            path_key = str(source).casefold()
            name_key = source.name.casefold()
            if path_key in existing_paths or name_key in existing_names:
                reused += 1
                continue
            extracted_text = text_service.read_text(result)
            self.repository.add_document(
                legacy.id,
                name=source.name,
                path=str(source),
                kind=classify_document(source.name, extracted_text),
                text=extracted_text,
                page_count=max(1, result.section_count),
            )
            existing_paths.add(path_key)
            existing_names.add(name_key)
            imported += 1

        report = self.engine_factory().analyze(
            legacy.id,
            estimate_total=0,
            cost_total=0,
            estimate={
                "source": "collector_full_analysis",
                "status": "estimate_not_calculated",
            },
        )
        return LegacyAnalysisBridgeResult(
            tender_id=str(legacy.id),
            imported_documents=imported,
            reused_documents=reused,
            report=report,
        )

    def _find_or_create_tender(self, tender: UnifiedTender):
        number = tender.procurement_number.strip().casefold()
        source_url = tender.source_url.strip().casefold()
        for existing in self.repository.list():
            if number and str(existing.number).strip().casefold() == number:
                return existing
            if source_url and str(existing.source_url).strip().casefold() == source_url:
                return existing
        amount = tender.price.amount if tender.price is not None else Decimal("0")
        return self.repository.create(
            number=tender.procurement_number,
            title=tender.title,
            source_url=tender.source_url,
            platform=tender.source.value,
            customer=tender.customer.name,
            region=tender.region or tender.customer.region,
            law=tender.law or "Не определён",
            nmck=amount,
            deadline=(
                tender.application_deadline.isoformat()
                if tender.application_deadline is not None
                else ""
            ),
            source_dir="",
            status="Документы загружены",
        )


__all__ = ["LegacyAnalysisBridge", "LegacyAnalysisBridgeResult"]
