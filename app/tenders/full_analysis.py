"""End-to-end tender workflow: download, unpack, extract, analyze and score."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import hashlib
from typing import Callable

from app.tenders.collector.cancellation import (
    CollectorCancelledError,
    CollectorCancellationToken,
)
from app.tenders.collector.participation_score import CorterisParticipationScore
from app.tenders.collector.participation_score_service import (
    CorterisParticipationScoreService,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.document_storage import (
    TenderDocumentDownloadResult,
    TenderDocumentDownloadService,
    TenderDocumentStore,
)
from app.tenders.document_text_extractor import (
    StoredDocumentText,
    TenderDocumentTextService,
    TenderTextExtractionResult,
)
from app.tenders.legacy_analysis_bridge import (
    LegacyAnalysisBridge,
    LegacyAnalysisBridgeResult,
)
from app.tenders.requirement_analysis import (
    TenderRequirementAnalysis,
    TenderRequirementAnalysisService,
)
from app.tenders.safe_archive import (
    SafeArchiveExtractionResult,
    SafeArchiveExtractor,
    UnsafeArchiveError,
)
from app.tenders.tender_registry import TenderRegistryRepository
from app.tenders.commercial_estimator import (
    CommercialEstimateRepository,
    CommercialEstimateResult,
)
from app.tenders.participation_decision_service import ParticipationDecisionService
from app.tenders.collector.company_capability import CompanyCapabilityProfileRepository
from app.tenders.tender_summary import (
    DeterministicTenderSummaryGenerator,
    TenderSummary,
)


class FullAnalysisStage(StrEnum):
    LOADING = "loading"
    DOWNLOADING = "downloading"
    EXTRACTING_ARCHIVES = "extracting_archives"
    EXTRACTING_TEXT = "extracting_text"
    ANALYZING_REQUIREMENTS = "analyzing_requirements"
    RUNNING_LEGACY_ANALYSIS = "running_legacy_analysis"
    SCORING = "scoring"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FullAnalysisStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class FullAnalysisProgress:
    stage: FullAnalysisStage
    message: str
    completed_steps: int
    total_steps: int = 8
    current_item: int = 0
    total_items: int = 0

    @property
    def percent(self) -> int:
        if self.total_steps <= 0:
            return 0
        return max(0, min(100, round(self.completed_steps / self.total_steps * 100)))


@dataclass(frozen=True, slots=True)
class TenderFullAnalysisResult:
    registry_key: str
    procurement_number: str
    status: FullAnalysisStatus
    started_at: str
    completed_at: str
    download: TenderDocumentDownloadResult | None
    archives: SafeArchiveExtractionResult | None
    text: TenderTextExtractionResult | None
    requirements: TenderRequirementAnalysis | None
    score: CorterisParticipationScore | None
    legacy: LegacyAnalysisBridgeResult | None
    warnings: tuple[str, ...] = ()
    commercial_estimate: CommercialEstimateResult | None = None
    summary: TenderSummary | None = None

    @property
    def successful(self) -> bool:
        return self.status in {FullAnalysisStatus.COMPLETED, FullAnalysisStatus.PARTIAL}


ProgressCallback = Callable[[FullAnalysisProgress], None]


class TenderFullAnalysisService:
    """Run all local and network stages in a deterministic order."""

    def __init__(
        self,
        tender_registry: TenderRegistryRepository,
        document_service: TenderDocumentDownloadService,
        document_store: TenderDocumentStore,
        text_service: TenderDocumentTextService,
        requirement_service: TenderRequirementAnalysisService,
        score_service: CorterisParticipationScoreService,
        *,
        archive_extractor: SafeArchiveExtractor | None = None,
        legacy_bridge: LegacyAnalysisBridge | None = None,
        commercial_estimate_repository: CommercialEstimateRepository | None = None,
        summary_generator: DeterministicTenderSummaryGenerator | None = None,
        summary_repository: CollectorStateRepository | None = None,
        participation_decision_service: ParticipationDecisionService | None = None,
        capability_repository: CompanyCapabilityProfileRepository | None = None,
    ) -> None:
        self.tender_registry = tender_registry
        self.document_service = document_service
        self.document_store = document_store
        self.text_service = text_service
        self.requirement_service = requirement_service
        self.score_service = score_service
        self.archive_extractor = archive_extractor or SafeArchiveExtractor()
        self.legacy_bridge = legacy_bridge
        self.commercial_estimate_repository = commercial_estimate_repository
        self.summary_generator = summary_generator or DeterministicTenderSummaryGenerator()
        self.summary_repository = summary_repository
        self.participation_decision_service = participation_decision_service
        self.capability_repository = capability_repository

    def run(
        self,
        registry_key: str,
        *,
        force_download: bool = False,
        force_extraction: bool = False,
        cancellation_token: CollectorCancellationToken | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> TenderFullAnalysisResult:
        token = cancellation_token or CollectorCancellationToken()
        key = registry_key.strip()
        if not key:
            raise ValueError("registry_key must not be empty")
        started = _now()
        warnings: list[str] = []
        download = None
        archives = None
        text_result = None
        requirements = None
        score = None
        legacy = None

        def emit(stage, message, completed, current=0, total=0):
            if progress_callback is not None:
                progress_callback(
                    FullAnalysisProgress(
                        stage=stage,
                        message=message,
                        completed_steps=completed,
                        current_item=current,
                        total_items=total,
                    )
                )

        try:
            emit(FullAnalysisStage.LOADING, "Загрузка карточки закупки…", 0)
            token.throw_if_cancelled()
            tender = self.tender_registry.get_tender(key)
            if tender is None:
                raise KeyError(f"Тендер не найден в реестре: {key}")

            emit(FullAnalysisStage.DOWNLOADING, "Скачивание всей доступной документации…", 1)
            download = self.document_service.download_for_tender(
                tender,
                force=force_download,
                refresh_catalog=True,
                should_cancel=lambda: token.is_cancelled,
                progress_callback=lambda current, total, _item: emit(
                    FullAnalysisStage.DOWNLOADING,
                    f"Скачивание документов: {current} из {total}",
                    2,
                    current,
                    total,
                ),
            )
            if download.catalog_warning:
                warnings.append(download.catalog_warning)
            if download.failed_count:
                warnings.append(f"Не удалось скачать файлов: {download.failed_count}")
            if download.cancelled:
                token.throw_if_cancelled()
            token.throw_if_cancelled()

            emit(FullAnalysisStage.EXTRACTING_ARCHIVES, "Безопасная распаковка архивов…", 3)
            archive_paths = tuple(
                item.local_path
                for item in download.documents
                if item.available_locally
                and item.local_path is not None
                and item.local_path.suffix.casefold() in {".zip", ".rar", ".7z"}
            )
            extraction_root = download.folder / "extracted"
            try:
                archives = self.archive_extractor.extract_many(archive_paths, extraction_root)
            except UnsafeArchiveError as exc:
                warnings.append(f"Распаковка остановлена защитой: {exc}")
                archives = SafeArchiveExtractionResult((), (), (), 0, (str(exc),))
            warnings.extend(archives.warnings)
            if archives.blocked_count:
                warnings.append(f"Заблокировано файлов архива: {archives.blocked_count}")
            token.throw_if_cancelled()

            emit(FullAnalysisStage.EXTRACTING_TEXT, "Извлечение текста из документов…", 4)
            original_text = self.text_service.extract_tender(key, force=force_extraction)
            extra_texts: list[StoredDocumentText] = []
            for index, path in enumerate(archives.extracted_files, start=1):
                token.throw_if_cancelled()
                if path.suffix.casefold() in {".zip", ".rar", ".7z"}:
                    continue
                try:
                    result = self.text_service.extract_path(
                        key,
                        tender.procurement_number,
                        path,
                        document_key=(
                            "archive-member:"
                            + hashlib.sha256(
                                f"{key}|{path.resolve()}".encode("utf-8")
                            ).hexdigest()
                        ),
                        force=force_extraction,
                    )
                    extra_texts.append(result)
                except (OSError, ValueError) as exc:
                    warnings.append(f"Не удалось извлечь текст {path.name}: {exc}")
                emit(
                    FullAnalysisStage.EXTRACTING_TEXT,
                    f"Обработка распакованных файлов: {index} из {len(archives.extracted_files)}",
                    5,
                    index,
                    len(archives.extracted_files),
                )
            text_result = TenderTextExtractionResult(
                registry_key=key,
                documents=tuple((*original_text.documents, *extra_texts)),
            )
            if text_result.failed_count:
                warnings.append(f"Ошибок извлечения текста: {text_result.failed_count}")
            token.throw_if_cancelled()

            emit(FullAnalysisStage.ANALYZING_REQUIREMENTS, "Анализ требований, лицензий и договора…", 6)
            requirements = self.requirement_service.analyze(
                key,
                force_extraction=False,
                persist=True,
            )
            warnings.extend(requirements.warnings)
            token.throw_if_cancelled()

            if self.legacy_bridge is not None:
                emit(FullAnalysisStage.RUNNING_LEGACY_ANALYSIS, "Передача данных в существующий AnalysisEngine…", 6)
                try:
                    latest = self.text_service.list_results(key)
                    legacy = self.legacy_bridge.sync_and_analyze(
                        tender,
                        self.text_service,
                        latest,
                    )
                except Exception as exc:
                    warnings.append(
                        "Существующий AnalysisEngine не завершил дополнительный анализ: "
                        f"{type(exc).__name__}: {exc}"
                    )
            token.throw_if_cancelled()

            emit(FullAnalysisStage.SCORING, "Пересчёт итоговой рекомендации Кортерис…", 7)
            score = self.score_service.evaluate(key, persist=True)
            latest_commercial = (
                self.commercial_estimate_repository.latest(key)
                if self.commercial_estimate_repository is not None
                else None
            )
            commercial_estimate = latest_commercial[1] if latest_commercial else None
            decision = (
                self.participation_decision_service.evaluate(key)
                if self.participation_decision_service is not None
                else None
            )
            if decision is not None and self.summary_repository is not None:
                self.summary_repository.save_participation_decision(decision)
            verification = (
                self.summary_repository.get_verification_state(key)
                if self.summary_repository is not None
                else None
            )
            stop_assessment = (
                self.summary_repository.get_latest_stop_factor_assessment(key)
                if self.summary_repository is not None
                else None
            )
            summary = self.summary_generator.generate(
                key,
                tender,
                requirements,
                decision=decision,
                verification=verification,
                stop_assessment=stop_assessment,
                commercial_estimate=commercial_estimate,
                company_profile=(self.capability_repository.load() if self.capability_repository else None),
            )
            if self.summary_repository is not None:
                self.summary_repository.save_tender_summary(summary)
            status = FullAnalysisStatus.PARTIAL if warnings else FullAnalysisStatus.COMPLETED
            emit(FullAnalysisStage.COMPLETED, "Полный анализ завершён.", 8)
            return TenderFullAnalysisResult(
                registry_key=key,
                procurement_number=tender.procurement_number,
                status=status,
                started_at=started,
                completed_at=_now(),
                download=download,
                archives=archives,
                text=text_result,
                requirements=requirements,
                score=score,
                legacy=legacy,
                warnings=_ordered_unique(warnings),
                commercial_estimate=commercial_estimate,
                summary=summary,
            )
        except CollectorCancelledError:
            emit(FullAnalysisStage.CANCELLED, token.reason or "Операция остановлена.", 0)
            procurement_number = ""
            tender = self.tender_registry.get_tender(key)
            if tender is not None:
                procurement_number = tender.procurement_number
            return TenderFullAnalysisResult(
                registry_key=key,
                procurement_number=procurement_number,
                status=FullAnalysisStatus.CANCELLED,
                started_at=started,
                completed_at=_now(),
                download=download,
                archives=archives,
                text=text_result,
                requirements=requirements,
                score=score,
                legacy=legacy,
                warnings=_ordered_unique((*warnings, token.reason or "Операция отменена")),
                commercial_estimate=None,
                summary=None,
            )


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _ordered_unique(values) -> tuple[str, ...]:
    result = []
    seen = set()
    for value in values:
        rendered = str(value).strip()
        key = rendered.casefold()
        if not rendered or key in seen:
            continue
        seen.add(key)
        result.append(rendered)
    return tuple(result)


__all__ = [
    "FullAnalysisProgress",
    "FullAnalysisStage",
    "FullAnalysisStatus",
    "TenderFullAnalysisResult",
    "TenderFullAnalysisService",
]
