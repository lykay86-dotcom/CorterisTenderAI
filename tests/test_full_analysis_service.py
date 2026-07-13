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
from app.core.ai.schemas import AiDocumentAnalysis
from app.core.ai.orchestrator import TenderAiOrchestrator


class Registry:
    def __init__(self, tender):
        self.tender = tender

    def get_tender(self, key):
        return self.tender if key else None


class DocumentService:
    def __init__(self, folder):
        self.folder = folder

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

    def list_results(self, key):
        return ()

    def extract_path(self, *args, **kwargs):
        raise AssertionError


class RequirementService:
    def analyze(self, key, **kwargs):
        return TenderRequirementsAnalyzer().analyze(key, ())


class ScoreService:
    def __init__(self, tender):
        self.tender = tender

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
        Registry(tender),
        DocumentService(tmp_path),
        Store(),
        TextService(),
        RequirementService(),
        ScoreService(tender),
        archive_extractor=ArchiveExtractor(),
        legacy_bridge=None,
    )

    result = service.run("procurement:test", cancellation_token=token)

    assert result.status == FullAnalysisStatus.CANCELLED
    assert "stop" in result.warnings


class ExplodingAiService:
    def analyze(self, _key, *, force=False):
        del force
        raise TimeoutError("Authorization: Bearer SECRET\nTraceback: hidden")


class StaticAiService:
    def __init__(self, status: str, warnings=()):
        self.status = status
        self.warnings = warnings

    def analyze(self, key, *, force=False):
        del force
        return AiDocumentAnalysis(
            key,
            "Safe AI state",
            status=self.status,
            warnings=tuple(self.warnings),
        )


class DecisionRecorder:
    def __init__(self):
        self.ai_analysis = None

    def evaluate(self, _key, *, ai_document_analysis=None):
        self.ai_analysis = ai_document_analysis
        return None


def _analysis_service(tmp_path, *, ai_service=None, decision_service=None):
    tender = make_tender()
    return TenderFullAnalysisService(
        Registry(tender),
        DocumentService(tmp_path),
        Store(),
        TextService(),
        RequirementService(),
        ScoreService(tender),
        archive_extractor=ArchiveExtractor(),
        legacy_bridge=None,
        ai_orchestrator=(TenderAiOrchestrator(ai_service) if ai_service is not None else None),
        participation_decision_service=decision_service,
    )


def test_ai_exception_degrades_full_analysis_without_secret_or_traceback(tmp_path) -> None:
    result = _analysis_service(
        tmp_path,
        ai_service=ExplodingAiService(),
    ).run("procurement:test")

    rendered_warnings = " ".join(result.warnings)
    assert result.status == FullAnalysisStatus.PARTIAL
    assert result.score is not None
    assert result.summary is not None
    assert result.ai_document_analysis is not None
    assert result.ai_document_analysis.status == "provider_error"
    assert "SECRET" not in rendered_warnings
    assert "Traceback" not in rendered_warnings


def test_current_safe_ai_result_is_passed_to_rm107_instead_of_stale_cache(tmp_path) -> None:
    decision = DecisionRecorder()
    result = _analysis_service(
        tmp_path,
        ai_service=StaticAiService("provider_disabled"),
        decision_service=decision,
    ).run("procurement:test")

    assert result.status == FullAnalysisStatus.PARTIAL
    assert decision.ai_analysis is result.ai_document_analysis
    assert decision.ai_analysis.status == "provider_disabled"


def test_full_analysis_reports_dedicated_ai_stage(tmp_path) -> None:
    progress = []

    result = _analysis_service(
        tmp_path,
        ai_service=StaticAiService("provider_disabled"),
    ).run("procurement:test", progress_callback=progress.append)

    assert result.ai_document_analysis is not None
    assert FullAnalysisStage.RUNNING_AI in {event.stage for event in progress}
    assert progress[-1].total_steps == 9
    assert progress[-1].percent == 100


def test_truncated_or_invalid_ai_result_keeps_exportable_result(tmp_path) -> None:
    result = _analysis_service(
        tmp_path,
        ai_service=StaticAiService(
            "partial",
            ("Контекст AI-анализа был сокращён по безопасному лимиту.",),
        ),
    ).run("procurement:test")

    assert result.status == FullAnalysisStatus.PARTIAL
    assert result.ai_document_analysis is not None
    assert "сокращён" in " ".join(result.warnings)
