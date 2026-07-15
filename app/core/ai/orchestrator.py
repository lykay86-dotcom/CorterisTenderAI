"""Single application-service entry point for tender AI execution."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Iterator

from app.core.ai.analyzer import TenderDocumentAiAnalysisService
from app.core.ai.recheck import TenderAiRecheckResult, compare_ai_analyses
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


@dataclass(slots=True)
class _ExecutionLockEntry:
    lock: Lock
    users: int = 0


class _PerRegistryExecutionCoordinator:
    """Serialize one registry key while retaining cross-key parallelism."""

    def __init__(self) -> None:
        self._registry_lock = Lock()
        self._entries: dict[str, _ExecutionLockEntry] = {}

    @contextmanager
    def acquire(self, registry_key: str) -> Iterator[None]:
        with self._registry_lock:
            entry = self._entries.get(registry_key)
            if entry is None:
                entry = _ExecutionLockEntry(Lock())
                self._entries[registry_key] = entry
            entry.users += 1
        entry.lock.acquire()
        try:
            yield
        finally:
            entry.lock.release()
            with self._registry_lock:
                entry.users -= 1
                if entry.users == 0 and self._entries.get(registry_key) is entry:
                    del self._entries[registry_key]

    @property
    def active_key_count(self) -> int:
        with self._registry_lock:
            return len(self._entries)


class TenderAiOrchestrator:
    """Run the existing task-service and isolate unexpected boundary failures."""

    def __init__(
        self,
        document_analysis_service: TenderDocumentAiAnalysisService,
    ) -> None:
        self.document_analysis_service = document_analysis_service
        self._execution_coordinator = _PerRegistryExecutionCoordinator()

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
        with self._execution_coordinator.acquire(key):
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

    def recheck(self, registry_key: str) -> TenderAiRecheckResult:
        key = registry_key.strip()
        if not key:
            raise ValueError("registry_key must not be empty")

        started_at = _now()
        with self._execution_coordinator.acquire(key):
            try:
                return self.document_analysis_service.recheck(key)
            except Exception:
                current = AiDocumentAnalysis(
                    key,
                    "AI analysis is temporarily unavailable.",
                    status=AiAnalysisStatus.PROVIDER_ERROR,
                )
                assessment = compare_ai_analyses(None, current)
                return TenderAiRecheckResult(
                    registry_key=key,
                    current_analysis=current,
                    assessment=assessment,
                    started_at=started_at,
                    completed_at=_now(),
                    warnings=("Повторная проверка AI временно недоступна.",),
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
