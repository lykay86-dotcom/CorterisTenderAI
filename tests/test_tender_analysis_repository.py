"""Tests for persistent tender analysis history."""

from __future__ import annotations

from app.tenders.requirement_analysis import (
    TenderAnalysisRepository,
    TenderAnalysisSource,
    TenderRequirementsAnalyzer,
)


def make_analysis(text: str):
    return TenderRequirementsAnalyzer().analyze(
        "procurement:001",
        (
            TenderAnalysisSource(
                document_key="doc-1",
                source_name="ТЗ.txt",
                text=text,
            ),
        ),
    )


def test_repository_roundtrip_and_same_fingerprint_reuse(
    tmp_path,
) -> None:
    repository = TenderAnalysisRepository(tmp_path / "tender_analysis.sqlite3")
    first = repository.save(make_analysis("Срок выполнения работ 30 календарных дней."))
    repeated = repository.save(make_analysis("Срок выполнения работ 30 календарных дней."))

    assert repeated.analysis_id == first.analysis_id
    latest = repository.get_latest("procurement:001")
    assert latest is not None
    assert latest.analysis_id == first.analysis_id
    assert latest.deadlines


def test_repository_keeps_history_after_source_change(tmp_path) -> None:
    repository = TenderAnalysisRepository(tmp_path / "tender_analysis.sqlite3")
    repository.save(make_analysis("Срок выполнения работ 30 календарных дней."))
    repository.save(
        make_analysis("Срок выполнения работ 20 календарных дней. Требуется лицензия МЧС.")
    )

    history = repository.list_history("procurement:001")

    assert len(history) == 2
    assert history[0].source_fingerprint != (history[1].source_fingerprint)
