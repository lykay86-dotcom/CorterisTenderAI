from __future__ import annotations

from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.participation_score import CorterisParticipationRanker
from app.tenders.document_storage import TenderDocumentDownloadResult
from app.tenders.document_text_extractor import TenderTextExtractionResult
from app.tenders.full_analysis import (
    FullAnalysisStage,
    FullAnalysisStatus,
    TenderFullAnalysisService,
)
from app.tenders.requirement_analysis import TenderRequirementsAnalyzer
from app.tenders.safe_archive import SafeArchiveExtractionResult
from tests.collector_c3_helpers import make_tender


class Registry:
    def __init__(self, tender): self.tender = tender
    def get_tender(self, key): return self.tender if key else None


class DocumentService:
    def __init__(self, folder): self.folder = folder
    def download_for_tender(self, tender, **kwargs):
        callback = kwargs.get("progress_callback")
        if callback:
            pass
        return TenderDocumentDownloadResult(
            tender_registry_key="procurement:test",
            procurement_number=tender.procurement_number,
            folder=self.folder,
            documents=(),
        )


class ArchiveExtractor:
    def extract_many(self, paths, root):
        return SafeArchiveExtractionResult((), (), (), 0)


class TextService:
    def extract_tender(self, key, force=False):
        return TenderTextExtractionResult(key, ())
    def list_results(self, key): return ()
    def extract_path(self, *args, **kwargs): raise AssertionError


class RequirementService:
    def analyze(self, key, **kwargs):
        return TenderRequirementsAnalyzer().analyze(key, ())


class ScoreService:
    def __init__(self, tender): self.tender = tender
    def evaluate(self, key, persist=True):
        return CorterisParticipationRanker().score(self.tender)


class Store:
    pass


def test_runs_all_stages_and_returns_score(tmp_path) -> None:
    tender = make_tender()
    progress = []
    service = TenderFullAnalysisService(
        Registry(tender),
        DocumentService(tmp_path),
        Store(),
        TextService(),
        RequirementService(),
        ScoreService(tender),
        archive_extractor=ArchiveExtractor(),
        legacy_bridge=None,
    )

    result = service.run("procurement:test", progress_callback=progress.append)

    assert result.status == FullAnalysisStatus.PARTIAL
    assert result.score is not None
    assert progress[-1].stage == FullAnalysisStage.COMPLETED


def test_cancelled_before_start_returns_cancelled(tmp_path) -> None:
    tender = make_tender()
    token = CollectorCancellationToken()
    token.cancel("stop")
    service = TenderFullAnalysisService(
        Registry(tender), DocumentService(tmp_path), Store(), TextService(),
        RequirementService(), ScoreService(tender),
        archive_extractor=ArchiveExtractor(), legacy_bridge=None,
    )

    result = service.run("procurement:test", cancellation_token=token)

    assert result.status == FullAnalysisStatus.CANCELLED
    assert "stop" in result.warnings
