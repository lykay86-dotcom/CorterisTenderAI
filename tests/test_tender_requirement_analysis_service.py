"""Tests for requirement-analysis orchestration."""

from __future__ import annotations

from pathlib import Path

from app.tenders.document_text_extractor import (
    StoredDocumentText,
    TenderTextExtractionResult,
    TextExtractionStatus,
)
from app.tenders.requirement_analysis import (
    TenderAnalysisRepository,
    TenderRequirementAnalysisService,
)


class FakeTextService:
    def __init__(self, text_path: Path) -> None:
        self.text_path = text_path
        self.extract_calls: list[tuple[str, bool]] = []
        self.results: tuple[StoredDocumentText, ...] = ()

    def list_results(self, registry_key: str):
        del registry_key
        return self.results

    def extract_tender(self, registry_key: str, *, force: bool = False):
        self.extract_calls.append((registry_key, force))
        self.results = (
            StoredDocumentText(
                extraction_key="extract-1",
                document_key="doc-1",
                registry_key=registry_key,
                source_path=self.text_path,
                text_path=self.text_path,
                document_format="txt",
                status=TextExtractionStatus.EXTRACTED,
                checksum_sha256="abc",
                character_count=self.text_path.stat().st_size,
                section_count=1,
                extracted_at="2026-07-12T12:00:00+00:00",
            ),
        )
        return TenderTextExtractionResult(
            registry_key=registry_key,
            documents=self.results,
        )

    def read_text(self, result: StoredDocumentText) -> str:
        return result.text_path.read_text(encoding="utf-8")


def test_service_extracts_then_analyzes_and_persists(tmp_path) -> None:
    text_path = tmp_path / "Техническое задание.txt"
    text_path.write_text(
        ("Техническое задание. Требуется лицензия МЧС. Срок выполнения работ 30 календарных дней."),
        encoding="utf-8",
    )
    text_service = FakeTextService(text_path)
    repository = TenderAnalysisRepository(tmp_path / "analysis.sqlite3")
    service = TenderRequirementAnalysisService(
        text_service,
        repository,
    )

    analysis = service.analyze("procurement:001")

    assert text_service.extract_calls == [("procurement:001", False)]
    assert analysis.license_requirements
    assert analysis.deadlines
    assert service.latest("procurement:001") is not None


def test_force_extraction_is_forwarded(tmp_path) -> None:
    text_path = tmp_path / "Проект контракта.txt"
    text_path.write_text(
        "Проект контракта. Оплата в течение 7 рабочих дней.",
        encoding="utf-8",
    )
    text_service = FakeTextService(text_path)
    service = TenderRequirementAnalysisService(
        text_service,
        TenderAnalysisRepository(tmp_path / "analysis.sqlite3"),
    )

    service.analyze(
        "procurement:002",
        force_extraction=True,
        persist=False,
    )

    assert text_service.extract_calls == [("procurement:002", True)]
