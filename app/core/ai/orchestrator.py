"""Single application-service entry point for tender AI execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.ai.analyzer import TenderDocumentAiAnalysisService
from app.core.ai.schemas import AiAnalysisStatus, AiDocumentAnalysis


@dataclass(frozen=True, slots=True)
class TenderAiOrchestrationResult:
    """Safe envelope for the document analysis produced by the current run."""

    registry_key: str
    document_analysis: AiDocumentAnalysis
    started_at: str
    completed_at: str
    warnings: tuple[str, ...]

    @property
    def degraded(self) -> bool:
        return self.document_analysis.status != AiAnalysisStatus.COMPLETE


class TenderAiOrchestrator:
    """Run the existing task-service and isolate unexpected boundary failures."""

    def __init__(
        self,
        document_analysis_service: TenderDocumentAiAnalysisService,
    ) -> None:
        self.document_analysis_service = document_analysis_service

    def run(
        self,
        registry_key: str,
        *,
        force: bool = False,
    ) -> TenderAiOrchestrationResult:
        key = registry_key.strip()
        if not key:
            raise ValueError("registry_key must not be empty")

        started_at = _now()
        try:
            analysis = self.document_analysis_service.analyze(key, force=force)
        except Exception:
            analysis = AiDocumentAnalysis(
                key,
                "AI analysis is temporarily unavailable.",
                status=AiAnalysisStatus.PROVIDER_ERROR,
            )

        warnings = _ordered_unique(
            (
                _warning_for_status(analysis.status),
                *analysis.warnings,
            )
        )
        return TenderAiOrchestrationResult(
            registry_key=key,
            document_analysis=analysis,
            started_at=started_at,
            completed_at=_now(),
            warnings=warnings,
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _warning_for_status(status: AiAnalysisStatus | str) -> str:
    messages = {
        AiAnalysisStatus.PARTIAL: "AI-анализ выполнен частично.",
        AiAnalysisStatus.NO_DOCUMENTS: ("AI-анализ не выполнен: подходящие документы отсутствуют."),
        AiAnalysisStatus.PROVIDER_DISABLED: (
            "AI-провайдер отключён; использован локальный анализ."
        ),
        AiAnalysisStatus.PROVIDER_ERROR: (
            "AI-провайдер временно недоступен; локальный анализ продолжен."
        ),
        AiAnalysisStatus.INVALID_RESPONSE: (
            "Ответ AI отклонён защитной проверкой; локальный анализ продолжен."
        ),
        AiAnalysisStatus.CACHE_INCOMPATIBLE: (
            "Сохранённый AI-анализ несовместим; локальный анализ продолжен."
        ),
    }
    try:
        return messages.get(AiAnalysisStatus(status), "")
    except (TypeError, ValueError):
        return "Ответ AI отклонён защитной проверкой; локальный анализ продолжен."


def _ordered_unique(values: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        rendered = str(value).strip()
        key = rendered.casefold()
        if not rendered or key in seen:
            continue
        seen.add(key)
        result.append(rendered)
    return tuple(result)


__all__ = ["TenderAiOrchestrationResult", "TenderAiOrchestrator"]
