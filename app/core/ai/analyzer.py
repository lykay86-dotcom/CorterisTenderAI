"""Safe adapter from an AI provider to evidence-first Tender Intelligence."""

from __future__ import annotations

from dataclasses import replace
import json
import math
from typing import Mapping

from app.ai.provider import AIProvider
from app.core.ai.document_context import TenderDocumentContextBuilder
from app.core.ai.prompts import SYSTEM_PROMPT
from app.core.ai.repository import (
    AI_ANALYZER_VERSION,
    AiDocumentAnalysisRepository,
    context_fingerprint,
)
from app.core.ai.schemas import (
    AiAnalysisStatus,
    AiDocument,
    AiDocumentAnalysis,
    AiEvidence,
    AiFinding,
    AiFindingStatus,
    TenderRequirements,
)


MAX_SUMMARY_LENGTH = 12_000
MAX_STATEMENT_LENGTH = 4_000
MAX_QUOTE_LENGTH = 8_000
MAX_SECTION_LENGTH = 1_000


class TenderDocumentAiAnalyzer:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def analyze(
        self,
        registry_key: str,
        documents: tuple[AiDocument, ...],
    ) -> AiDocumentAnalysis:
        if not documents:
            return AiDocumentAnalysis(
                registry_key,
                "No documents available.",
                missing_documents=("Tender documentation",),
                status=AiAnalysisStatus.NO_DOCUMENTS,
            )
        try:
            response = self.provider.analyze(
                SYSTEM_PROMPT,
                [self._render(item) for item in documents],
            )
        except Exception:
            return _safe_failure(registry_key, AiAnalysisStatus.PROVIDER_ERROR)
        if not isinstance(response, Mapping):
            return _safe_failure(registry_key, AiAnalysisStatus.INVALID_RESPONSE)
        provider_status = response.get("status")
        if provider_status == "disabled":
            return _safe_failure(registry_key, AiAnalysisStatus.PROVIDER_DISABLED)
        if provider_status != "ok":
            return _safe_failure(registry_key, AiAnalysisStatus.PROVIDER_ERROR)

        payload = self._decode(response.get("text"))
        if payload is None:
            return _safe_failure(registry_key, AiAnalysisStatus.INVALID_RESPONSE)
        return self._normalize(registry_key, payload, documents)

    @staticmethod
    def _decode(value: object) -> Mapping[str, object] | None:
        if not isinstance(value, (str, bytes, bytearray)):
            return None
        try:
            payload = json.loads(value)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
            return None
        return payload if isinstance(payload, Mapping) else None

    def _normalize(
        self,
        registry_key: str,
        payload: Mapping[str, object],
        documents: tuple[AiDocument, ...],
    ) -> AiDocumentAnalysis:
        issues: list[str] = []
        known = {item.document_id: item for item in documents}
        raw_requirements = payload.get("requirements", {})
        if not isinstance(raw_requirements, Mapping):
            issues.append("requirements")
            raw_requirements = {}

        requirements = TenderRequirements(
            **{
                name: self._findings(
                    raw_requirements.get(name, ()),
                    known,
                    name,
                    issues,
                )
                for name in TenderRequirements.__dataclass_fields__
            }
        )
        missing_documents = self._strings(
            payload.get("missing_documents", ()),
            issues,
        )
        summary = _bounded_text(
            payload.get("summary", ""),
            MAX_SUMMARY_LENGTH,
            issues,
            "summary",
        )
        final_conclusion = _bounded_text(
            payload.get("final_ai_conclusion", ""),
            MAX_SUMMARY_LENGTH,
            issues,
            "final_ai_conclusion",
        )
        return AiDocumentAnalysis(
            registry_key=registry_key,
            summary=summary,
            requirements=requirements,
            risks=self._findings(payload.get("risks", ()), known, "risk", issues),
            suspicious_conditions=self._findings(
                payload.get("suspicious_conditions", ()),
                known,
                "suspicious",
                issues,
            ),
            contradictions=self._findings(
                payload.get("contradictions", ()),
                known,
                "contradiction",
                issues,
            ),
            missing_documents=missing_documents,
            final_ai_conclusion=final_conclusion,
            status=(AiAnalysisStatus.PARTIAL if issues else AiAnalysisStatus.COMPLETE),
            warnings=(
                ("Часть ответа AI отклонена защитной проверкой.",)
                if issues
                else ()
            ),
        )

    @staticmethod
    def _render(document: AiDocument) -> str:
        marker = (
            f"\n[CONTEXT TRUNCATED: {len(document.text)} of "
            f"{document.original_character_count} characters]"
            if document.truncated
            else ""
        )
        return f"DOCUMENT {document.document_id} | {document.name}\n{document.text}{marker}"

    @staticmethod
    def _findings(
        raw: object,
        known: Mapping[str, AiDocument],
        category: str,
        issues: list[str],
    ) -> tuple[AiFinding, ...]:
        if not isinstance(raw, (list, tuple)):
            if raw not in (None, ()):
                issues.append(category)
            return ()
        result: list[AiFinding] = []
        for index, item in enumerate(raw):
            if not isinstance(item, Mapping):
                issues.append(f"{category}[{index}]")
                continue
            statement = _bounded_text(
                item.get("statement"),
                MAX_STATEMENT_LENGTH,
                issues,
                f"{category}.statement",
            )
            if not statement:
                issues.append(f"{category}.statement")
                continue
            document_id = _bounded_text(
                item.get("document_id"),
                500,
                issues,
                f"{category}.document_id",
            )
            quote = _bounded_text(
                item.get("quote"),
                MAX_QUOTE_LENGTH,
                issues,
                f"{category}.quote",
            )
            section = _bounded_text(
                item.get("section", ""),
                MAX_SECTION_LENGTH,
                issues,
                f"{category}.section",
            )
            confidence = _confidence(item.get("confidence"))
            if confidence is None:
                issues.append(f"{category}.confidence")
            page, page_valid = _page(item.get("page"))
            if not page_valid:
                issues.append(f"{category}.page")
            exact_quote = bool(
                document_id in known
                and quote
                and quote in known[document_id].text
            )
            verified = exact_quote and confidence is not None
            if not verified:
                issues.append(f"{category}.evidence")
            evidence = (
                AiEvidence(
                    document_id=document_id,
                    quote=quote,
                    section=section,
                    page=page,
                    confidence=confidence,
                )
                if verified and confidence is not None
                else None
            )
            result.append(
                AiFinding(
                    category,
                    statement,
                    evidence,
                    (
                        AiFindingStatus.VERIFIED
                        if verified
                        else AiFindingStatus.UNVERIFIED
                    ),
                )
            )
        return tuple(result)

    @staticmethod
    def _strings(raw: object, issues: list[str]) -> tuple[str, ...]:
        if not isinstance(raw, (list, tuple)):
            if raw not in (None, ()):
                issues.append("missing_documents")
            return ()
        result: list[str] = []
        for value in raw:
            text = _bounded_text(value, 1_000, issues, "missing_documents")
            if text:
                result.append(text)
        return tuple(dict.fromkeys(result))


class TenderDocumentAiAnalysisService:
    """Build context, reuse identical results, analyze and persist safely."""

    def __init__(
        self,
        context_builder: TenderDocumentContextBuilder,
        analyzer: TenderDocumentAiAnalyzer,
        repository: AiDocumentAnalysisRepository,
    ) -> None:
        self.context_builder = context_builder
        self.analyzer = analyzer
        self.repository = repository

    def analyze(self, registry_key: str, *, force: bool = False) -> AiDocumentAnalysis:
        try:
            build_context = getattr(self.context_builder, "build_context", None)
            context = build_context(registry_key) if callable(build_context) else None
            documents = (
                context.documents
                if context is not None
                else self.context_builder.build(registry_key)
            )
        except Exception:
            return _add_warning(
                _safe_failure(registry_key, AiAnalysisStatus.INVALID_RESPONSE),
                "Не удалось подготовить локальный контекст AI-анализа.",
            )
        parameters = getattr(self.context_builder, "fingerprint_parameters", {})
        fingerprint = context_fingerprint(documents, context_parameters=parameters)
        repository_warning = ""
        if not force:
            try:
                reused = self.repository.reusable(registry_key, fingerprint)
            except Exception:
                reused = None
                repository_warning = "Кеш AI-анализа временно недоступен."
            if reused is not None:
                return reused
            repository_warning = repository_warning or getattr(
                self.repository,
                "last_warning",
                "",
            )
        result = self.analyzer.analyze(registry_key, documents)
        statistics = getattr(context, "statistics", None)
        if statistics is not None:
            result = replace(
                result,
                context_document_count=statistics.included_document_count,
                context_character_count=statistics.character_count,
                context_truncated=statistics.truncated,
            )
            if statistics.truncated:
                result = _add_warning(
                    result,
                    "Контекст AI-анализа был сокращён по безопасному лимиту.",
                )
        if repository_warning:
            result = _add_warning(result, repository_warning)
        if result.status in {
            AiAnalysisStatus.COMPLETE,
            AiAnalysisStatus.PARTIAL,
            AiAnalysisStatus.NO_DOCUMENTS,
        }:
            try:
                self.repository.save(result, fingerprint)
            except Exception:
                result = _add_warning(
                    result,
                    "Не удалось сохранить историю AI-анализа.",
                )
        return result


def _safe_failure(
    registry_key: str,
    status: AiAnalysisStatus,
) -> AiDocumentAnalysis:
    messages = {
        AiAnalysisStatus.PROVIDER_DISABLED: "AI provider is disabled.",
        AiAnalysisStatus.PROVIDER_ERROR: "AI analysis is temporarily unavailable.",
        AiAnalysisStatus.INVALID_RESPONSE: "AI response is invalid.",
    }
    return AiDocumentAnalysis(registry_key, messages[status], status=status)


def _bounded_text(
    value: object,
    limit: int,
    issues: list[str],
    field_name: str,
) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        issues.append(field_name)
        return ""
    try:
        rendered = str(value).strip()
    except Exception:
        issues.append(field_name)
        return ""
    if len(rendered) > limit:
        issues.append(field_name)
        return rendered[:limit]
    return rendered


def _confidence(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    rendered = float(value)
    return rendered if math.isfinite(rendered) and 0.0 <= rendered <= 1.0 else None


def _page(value: object) -> tuple[int | None, bool]:
    if value is None:
        return None, True
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None, False
    return value, True


def _add_warning(
    analysis: AiDocumentAnalysis,
    warning: str,
) -> AiDocumentAnalysis:
    warnings = tuple(dict.fromkeys((*analysis.warnings, warning)))
    status = (
        AiAnalysisStatus.PARTIAL
        if analysis.status == AiAnalysisStatus.COMPLETE
        else analysis.status
    )
    return replace(analysis, warnings=warnings, status=status)


__all__ = [
    "AI_ANALYZER_VERSION",
    "TenderDocumentAiAnalyzer",
    "TenderDocumentAiAnalysisService",
]
