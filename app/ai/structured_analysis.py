from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import re
from typing import Any

from app.ai.provider import AIProvider

SYSTEM_PROMPT = """Ты — тендерный аналитик ООО «КОРТЕРИС».
Работай только по предоставленным документам. Не придумывай факты.
Каждый существенный вывод должен содержать source_document, page, section и quote.
Если данных недостаточно, используй точную формулировку: «В документации недостаточно информации. Требуется уточнение».
Не называй закупку договорной или незаконной. Допустима формулировка: «Обнаружены признаки возможного ограничения конкуренции, требующие дополнительной проверки».
Верни только валидный JSON без markdown с ключами: summary, extracted_conditions, equipment, risks, competition_flags, contradictions, missing_information, clarification_questions, score, recommendation.
"""

@dataclass(slots=True)
class SourceRef:
    source_document: str
    page: int | None
    section: str
    quote: str

@dataclass(slots=True)
class AnalysisResult:
    summary: str
    extracted_conditions: dict[str, Any]
    equipment: list[dict[str, Any]]
    risks: list[dict[str, Any]]
    competition_flags: list[dict[str, Any]]
    contradictions: list[dict[str, Any]]
    missing_information: list[str]
    clarification_questions: list[str]
    score: int
    recommendation: str
    raw_text: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def validate_citations(payload: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for bucket in ("risks", "competition_flags", "contradictions"):
        for i, item in enumerate(payload.get(bucket, []) or []):
            source = item.get("source") or {}
            if not source.get("source_document"):
                problems.append(f"{bucket}[{i}]: отсутствует source_document")
            if not source.get("quote"):
                problems.append(f"{bucket}[{i}]: отсутствует quote")
    return problems


class TenderAIService:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    def analyze(self, documents: list[str], task: str = "Полный анализ тендера") -> AnalysisResult:
        response = self.provider.analyze(SYSTEM_PROMPT + "\nЗадача: " + task, documents)
        if response.get("status") != "ok":
            raise RuntimeError(response.get("message", "Ошибка ИИ-провайдера"))
        raw = response.get("text", "")
        payload = _extract_json(raw)
        citation_problems = validate_citations(payload)
        if citation_problems:
            payload.setdefault("missing_information", []).extend(citation_problems)
        return AnalysisResult(
            summary=str(payload.get("summary", "")),
            extracted_conditions=dict(payload.get("extracted_conditions", {}) or {}),
            equipment=list(payload.get("equipment", []) or []),
            risks=list(payload.get("risks", []) or []),
            competition_flags=list(payload.get("competition_flags", []) or []),
            contradictions=list(payload.get("contradictions", []) or []),
            missing_information=list(payload.get("missing_information", []) or []),
            clarification_questions=list(payload.get("clarification_questions", []) or []),
            score=max(0, min(100, int(payload.get("score", 0) or 0))),
            recommendation=str(payload.get("recommendation", "Участвовать только после уточнений")),
            raw_text=raw,
        )
