"""Safe adapter from an AI provider to evidence-first RM-109 schemas."""

from __future__ import annotations

import json
from typing import Mapping

from app.ai.provider import AIProvider
from app.core.ai.prompts import SYSTEM_PROMPT
from app.core.ai.schemas import AiDocument, AiDocumentAnalysis, AiEvidence, AiFinding, AiFindingStatus, TenderRequirements
from app.core.ai.document_context import TenderDocumentContextBuilder
from app.core.ai.repository import AiDocumentAnalysisRepository, context_fingerprint


class TenderDocumentAiAnalyzer:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def analyze(self, registry_key: str, documents: tuple[AiDocument, ...]) -> AiDocumentAnalysis:
        if not documents:
            return AiDocumentAnalysis(registry_key, "No documents available.", missing_documents=("Tender documentation",), status="no_documents")
        response = self.provider.analyze(SYSTEM_PROMPT, [self._render(item) for item in documents])
        if response.get("status") != "ok":
            return AiDocumentAnalysis(registry_key, "AI analysis is unavailable.", status="provider_error")
        try:
            payload = json.loads(str(response.get("text", "{}")))
        except json.JSONDecodeError:
            return AiDocumentAnalysis(registry_key, "AI response is invalid.", status="invalid_response")
        known = {item.document_id: item for item in documents}
        return AiDocumentAnalysis(
            registry_key=registry_key,
            summary=str(payload.get("summary", "")),
            requirements=TenderRequirements(**{name: self._findings(payload.get("requirements", {}).get(name, ()), known, name) for name in TenderRequirements.__dataclass_fields__}),
            risks=self._findings(payload.get("risks", ()), known, "risk"),
            suspicious_conditions=self._findings(payload.get("suspicious_conditions", ()), known, "suspicious"),
            contradictions=self._findings(payload.get("contradictions", ()), known, "contradiction"),
            missing_documents=tuple(str(x) for x in payload.get("missing_documents", ()) if str(x).strip()),
            final_ai_conclusion=str(payload.get("final_ai_conclusion", "")),
            status="complete",
        )

    @staticmethod
    def _render(document: AiDocument) -> str:
        return f"DOCUMENT {document.document_id} | {document.name}\n{document.text}"

    @staticmethod
    def _findings(raw: object, known: Mapping[str, AiDocument], category: str) -> tuple[AiFinding, ...]:
        result = []
        for item in raw if isinstance(raw, list) else ():
            if not isinstance(item, Mapping):
                continue
            document_id, quote = str(item.get("document_id", "")), str(item.get("quote", ""))
            valid = bool(document_id in known and quote and quote in known[document_id].text)
            evidence = AiEvidence(document_id, quote, str(item.get("section", "")), item.get("page"), float(item.get("confidence", 0.0))) if valid else None
            result.append(AiFinding(category, str(item.get("statement", "")), evidence, AiFindingStatus.VERIFIED if valid else AiFindingStatus.UNVERIFIED))
        return tuple(result)


class TenderDocumentAiAnalysisService:
    """Build context, reuse identical results, analyze and persist once."""

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
        documents = self.context_builder.build(registry_key)
        fingerprint = context_fingerprint(documents)
        if not force:
            reused = self.repository.reusable(registry_key, fingerprint)
            if reused is not None:
                return reused
        result = self.analyzer.analyze(registry_key, documents)
        self.repository.save(result, fingerprint)
        return result
