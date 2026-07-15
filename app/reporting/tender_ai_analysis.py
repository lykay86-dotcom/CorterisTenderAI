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
            serialized = (
                json.dumps(analysis.to_payload(), ensure_ascii=False, indent=2)
                .replace("&", "\\u0026")
                .replace("<", "\\u003c")
                .replace(">", "\\u003e")
            )
            path.write_text(
                serialized,
                encoding="utf-8",
            )
        elif path.suffix.lower() in {".html", ".htm"}:
            path.write_text(self._html(analysis), encoding="utf-8")
        else:
            raise ValueError("AI analysis export supports only JSON and HTML")
        return path

    @staticmethod
    def _html(analysis: AiDocumentAnalysis) -> str:
        all_requirements = tuple(
            item
            for name in analysis.requirements.__dataclass_fields__
            for item in getattr(analysis.requirements, name)
        )
        all_findings = (
            *all_requirements,
            *analysis.risks,
            *analysis.suspicious_conditions,
            *analysis.contradictions,
        )
        technical = analysis.technical_specification
        technical_groups = tuple(
            (name, getattr(technical, name))
            for name in technical.__dataclass_fields__
            if name not in {"status", "document_ids", "included_document_ids", "warnings"}
        )
        contract = analysis.draft_contract
        contract_groups = tuple(
            (name, getattr(contract, name))
            for name in contract.__dataclass_fields__
            if name not in {"status", "document_ids", "included_document_ids", "warnings"}
        )
        all_findings = (
            *all_findings,
            *(item for _, items in technical_groups for item in items),
            *(item for _, items in contract_groups for item in items),
        )

        def findings(items) -> str:
            rows = []
            for item in items:
                proof = item.evidence
                citation = "unverified"
                if analysis.is_current_verified(item) and proof is not None:
                    citation = (
                        f'<a href="#source-{proof.citation_id}">'
                        f"{escape(proof.citation_id[:12])}…</a>"
                    )
                rows.append(
                    f"<tr><td>{escape(item.category)}</td><td>{escape(item.statement)}</td><td>{citation}</td></tr>"
                )
            return "".join(rows)

        sources_by_document = {
            source.document_id: source
            for source in (analysis.provenance.sources if analysis.provenance is not None else ())
        }
        source_rows: list[str] = []
        seen_citations: set[str] = set()
        for item in all_findings:
            evidence = item.evidence
            if (
                not analysis.is_current_verified(item)
                or evidence is None
                or evidence.citation_id in seen_citations
            ):
                continue
            seen_citations.add(evidence.citation_id)
            source = sources_by_document[evidence.document_id]
            locator = " · ".join(
                part
                for part in (
                    f"страница {evidence.page}" if evidence.page is not None else "",
                    f"раздел {escape(evidence.section)}" if evidence.section else "",
                )
                if part
            )
            locator_html = f" · {locator}" if locator else ""
            truncated = " · контекст сокращён" if source.truncated else ""
            source_rows.append(
                f'<li id="source-{evidence.citation_id}"><strong>'
                f"{escape(source.display_name)}</strong>{locator_html}{truncated}<br>"
                f"checksum {escape(source.checksum_sha256[:12])}… · "
                f"citation {escape(evidence.citation_id)} · уверенность AI "
                f"{evidence.confidence:.0%}<br>Цитата: {escape(evidence.quote)}</li>"
            )
        sources = "".join(source_rows) or "<li>Нет текущих подтверждённых источников.</li>"
        warnings = (
            "".join(f"<li>{escape(item)}</li>" for item in analysis.warnings) or "<li>Нет.</li>"
        )
        technical_tables = "".join(
            f"<h3>{escape(name)}</h3><table><tr><th>Категория</th><th>Вывод</th>"
            f"<th>Источник</th></tr>{findings(items)}</table>"
            for name, items in technical_groups
        )
        technical_warnings = (
            "".join(f"<li>{escape(item)}</li>" for item in technical.warnings) or "<li>Нет.</li>"
        )
        contract_tables = "".join(
            f"<h3>{escape(name)}</h3><table><tr><th>Категория</th><th>Вывод</th>"
            f"<th>Источник</th></tr>{findings(items)}</table>"
            for name, items in contract_groups
        )
        contract_warnings = (
            "".join(f"<li>{escape(item)}</li>" for item in contract.warnings) or "<li>Нет.</li>"
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
            f"<h2>Техническое задание</h2><p>Статус: "
            f"{escape(technical.status.value)}; найдено документов: "
            f"{len(technical.document_ids)}; включено: "
            f"{len(technical.included_document_ids)}</p>"
            f"{technical_tables}<h3>Предупреждения по ТЗ</h3><ul>{technical_warnings}</ul>"
            f"<h2>Проект договора/контракта</h2><p>Статус: "
            f"{escape(contract.status.value)}; найдено документов: "
            f"{len(contract.document_ids)}; включено: {len(contract.included_document_ids)}</p>"
            f"{contract_tables}<h3>Предупреждения по проекту договора</h3>"
            f"<ul>{contract_warnings}</ul>"
            f"<h2>Требования</h2><table><tr><th>Категория</th><th>Вывод</th><th>Источник</th></tr>{findings(all_requirements)}</table>"
            f"<h2>Риски</h2><table>{findings(analysis.risks)}</table>"
            f"<h2>Подозрительные условия</h2><table>{findings(analysis.suspicious_conditions)}</table>"
            f"<h2>Противоречия</h2><table>{findings(analysis.contradictions)}</table>"
            f"<h2>Источники</h2><ol>{sources}</ol>"
            f"<h2>Предупреждения</h2><ul>{warnings}</ul>"
            f"<h2>Итог AI</h2><p>{escape(analysis.final_ai_conclusion)}</p>"
        )
