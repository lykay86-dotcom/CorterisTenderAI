"""JSON and HTML export of the RM-109 documentation analysis section."""

from __future__ import annotations

from html import escape
import json
from pathlib import Path

from app.core.ai.schemas import AiDocumentAnalysis


class TenderAiAnalysisExporter:
    def export(self, analysis: AiDocumentAnalysis, destination: str | Path) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".json":
            path.write_text(
                json.dumps(analysis.to_payload(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        elif path.suffix.lower() in {".html", ".htm"}:
            path.write_text(self._html(analysis), encoding="utf-8")
        else:
            raise ValueError("AI analysis export supports only JSON and HTML")
        return path

    @staticmethod
    def _html(analysis: AiDocumentAnalysis) -> str:
        def findings(items) -> str:
            rows = []
            for item in items:
                proof = item.evidence
                citation = (
                    f"{escape(proof.document_id)}: {escape(proof.quote)} ({proof.confidence:.0%})"
                    if proof
                    else "unverified"
                )
                rows.append(
                    f"<tr><td>{escape(item.category)}</td><td>{escape(item.statement)}</td><td>{citation}</td></tr>"
                )
            return "".join(rows)

        all_requirements = tuple(
            item
            for name in analysis.requirements.__dataclass_fields__
            for item in getattr(analysis.requirements, name)
        )
        warnings = (
            "".join(f"<li>{escape(item)}</li>" for item in analysis.warnings) or "<li>Нет.</li>"
        )
        context_note = (
            "<p><strong>Контекст сокращён по безопасному лимиту.</strong></p>"
            if analysis.context_truncated
            else ""
        )
        return (
            "<!doctype html><meta charset='utf-8'><title>AI analysis</title>"
            f"<h1>AI-анализ документации</h1>"
            f"<p>Статус: {escape(analysis.status.value)}</p>"
            f"<p>Контекст: {analysis.context_document_count} документов, "
            f"{analysis.context_character_count} символов.</p>{context_note}"
            f"<p>{escape(analysis.summary)}</p>"
            f"<h2>Требования</h2><table><tr><th>Категория</th><th>Вывод</th><th>Источник</th></tr>{findings(all_requirements)}</table>"
            f"<h2>Риски</h2><table>{findings(analysis.risks)}</table>"
            f"<h2>Предупреждения</h2><ul>{warnings}</ul>"
            f"<h2>Итог AI</h2><p>{escape(analysis.final_ai_conclusion)}</p>"
        )
