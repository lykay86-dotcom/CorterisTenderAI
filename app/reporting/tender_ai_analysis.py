"""JSON and HTML export of the RM-109 documentation analysis section."""

from __future__ import annotations

from html import escape
import json
from pathlib import Path

from app.core.ai.competition_review import competition_source_findings
from app.core.ai.documentation_completeness import (
    AI_DOCUMENTATION_COMPLETENESS_DISCLAIMER,
)
from app.core.ai.financial_risk import financial_risk_source_findings
from app.core.ai.legal_risk import legal_risk_source_findings
from app.core.ai.recheck import (
    AI_RECHECK_DISCLAIMER,
    AiRecheckAssessment,
    AiRecheckStatus,
)
from app.core.ai.schemas import (
    AiApplicationRequirementsStatus,
    AiCompetitionReviewPriority,
    AiCompetitionStatus,
    AiDocumentAnalysis,
    AiDocumentationCompletenessStatus,
    AiFinancialReviewPriority,
    AiFinancialRiskStatus,
    AiLegalReviewPriority,
    AiLegalRiskStatus,
    _APPLICATION_REQUIREMENTS_FINDING_FIELDS,
)
from app.core.document_classification import DocumentKind


_APPLICATION_REQUIREMENT_LABELS = {
    "application_composition": "Состав заявки",
    "participant_eligibility": "Требования к участнику",
    "declarations_and_consents": "Декларации и согласия",
    "equipment": "Оборудование и ресурсы",
    "certificates": "Сертификаты и качество",
    "licenses": "Лицензии, допуски и СРО",
    "specialists": "Специалисты и квалификация",
    "documents": "Подтверждающие документы",
    "experience": "Опыт исполнения",
    "deadlines": "Сроки подачи и действия заявки",
    "warranty": "Гарантийные обязательства",
    "bid_security": "Обеспечение заявки",
    "contract_security": "Обеспечение исполнения контракта",
    "bank_guarantee": "Банковская или независимая гарантия",
    "submission_format_and_signature": "Формат и подписание",
    "national_regime_and_origin": "Национальный режим и происхождение",
    "price_proposal_and_estimate": "Ценовое предложение и смета",
    "grounds_for_rejection": "Основания отклонения",
    "ambiguities": "Неоднозначности",
    "contradictions": "Противоречия",
    "clarification_points": "Вопросы для уточнения",
}


def _documentation_completeness_html(analysis: AiDocumentAnalysis) -> str:
    assessment = analysis.documentation_completeness_assessment
    status = {
        AiDocumentationCompletenessStatus.COMPLETE: (
            "Локально известный комплект готов для текущего анализа"
        ),
        AiDocumentationCompletenessStatus.PARTIAL: (
            "Комплект обработан частично; требуется устранить проблемы"
        ),
        AiDocumentationCompletenessStatus.NO_DOCUMENTS: "Документы для проверки не найдены",
        AiDocumentationCompletenessStatus.UNAVAILABLE: ("Оценка полноты документации недоступна"),
    }.get(
        assessment.status,
        "Оценка полноты документации недоступна",
    )
    coverage = "".join(
        f"<li>{escape(kind.value)}: "
        f"{sum(item.document_kind is kind for item in analysis.documentation_inventory)}</li>"
        for kind in DocumentKind
    )
    inventory_rows = (
        "".join(
            "<tr>"
            f"<td>{escape(item.display_name or item.document_id)}</td>"
            f"<td>{escape(item.document_kind.value)}</td>"
            f"<td>{escape(item.download_status)}</td>"
            f"<td>{escape(item.extraction_status)}</td>"
            f"<td>{'да' if item.included_in_context else 'нет'}</td>"
            f"<td>{'да' if item.context_truncated else 'нет'}</td>"
            "</tr>"
            for item in analysis.documentation_inventory
        )
        or "<tr><td colspan='6'>Локальные документы не найдены.</td></tr>"
    )
    issue_rows = (
        "".join(
            "<tr>"
            f"<td>{escape(item.scope.value)}</td>"
            f"<td>{escape(item.title)}</td>"
            f"<td>{escape(', '.join(item.document_ids) or '—')}</td>"
            f"<td>{escape(item.recommended_action)}</td>"
            "</tr>"
            for item in assessment.issues
        )
        or "<tr><td colspan='4'>Локальные проблемы не выявлены.</td></tr>"
    )
    warnings = (
        "".join(f"<li>{escape(item)}</li>" for item in assessment.warnings) or "<li>Нет.</li>"
    )
    return (
        "<h2>Полнота документации</h2>"
        f"<p><strong>{escape(AI_DOCUMENTATION_COMPLETENESS_DISCLAIMER)}</strong></p>"
        f"<p>Статус: {escape(status)}; policy version: "
        f"{escape(assessment.policy_version)}.</p>"
        f"<p>Известно: {assessment.known_document_count}; доступно локально: "
        f"{assessment.locally_available_count}; доступен текст: "
        f"{assessment.text_available_count}; включено в контекст: "
        f"{assessment.included_document_count}.</p>"
        f"<h3>Покрытие областей</h3><ul>{coverage}</ul>"
        "<table><tr><th>Документ</th><th>Область</th><th>Загрузка</th>"
        f"<th>Извлечение</th><th>В контексте</th><th>Усечён</th></tr>{inventory_rows}</table>"
        "<h3>Проблемы и действия</h3><table><tr><th>Область</th><th>Проблема</th>"
        f"<th>Документы</th><th>Действие</th></tr>{issue_rows}</table>"
        f"<h3>Предупреждения оценки полноты</h3><ul>{warnings}</ul>"
    )


def _ai_recheck_html(assessment: AiRecheckAssessment | None) -> str:
    if assessment is None:
        return ""
    status = {
        AiRecheckStatus.CONSISTENT: "Совпадает",
        AiRecheckStatus.CHANGED: "Изменён",
        AiRecheckStatus.BASELINE_MISSING: "Предыдущий результат не найден",
        AiRecheckStatus.CURRENT_UNAVAILABLE: "Текущий результат недоступен",
        AiRecheckStatus.NOT_COMPARABLE: "Результаты несопоставимы",
    }.get(assessment.status, "Результаты несопоставимы")
    deltas = (
        "".join(
            "<tr>"
            f"<td>{escape(item.change_type.value)}</td>"
            f"<td>{escape(item.scope)}</td>"
            f"<td>{escape(item.category)}</td>"
            f"<td>{escape(item.citation_id)}</td>"
            f"<td>{escape(item.previous_statement)}</td>"
            f"<td>{escape(item.current_statement)}</td>"
            "</tr>"
            for item in assessment.deltas
        )
        or "<tr><td colspan='6'>Изменения подтверждённых выводов не выявлены.</td></tr>"
    )
    warnings = (
        "".join(f"<li>{escape(item)}</li>" for item in assessment.warnings) or "<li>Нет.</li>"
    )
    return (
        "<section id='ai-recheck'><h2>Повторная проверка AI</h2>"
        f"<p><strong>Статус:</strong> {escape(status)} · policy version: "
        f"{escape(assessment.policy_version)}</p>"
        f"<p>{escape(AI_RECHECK_DISCLAIMER)}</p>"
        f"<p><strong>Baseline:</strong> {escape(assessment.baseline_created_at or '—')} · "
        f"<strong>current:</strong> {escape(assessment.current_created_at or '—')} · "
        f"provider/model: {escape(assessment.provider_id or '—')}/"
        f"{escape(assessment.provider_model or '—')}</p>"
        f"<p>Без изменений: {assessment.unchanged_count}; добавлено: "
        f"{assessment.added_count}; удалено: {assessment.removed_count}; изменено: "
        f"{assessment.modified_count}.</p>"
        "<table><tr><th>Тип</th><th>Область</th><th>Категория</th><th>Citation</th>"
        f"<th>Было</th><th>Стало</th></tr>{deltas}</table>"
        f"<h3>Предупреждения повторной проверки</h3><ul>{warnings}</ul></section>"
    )


class TenderAiAnalysisExporter:
    def export(
        self,
        analysis: AiDocumentAnalysis,
        destination: str | Path,
        *,
        recheck: AiRecheckAssessment | None = None,
    ) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".json":
            payload = analysis.to_payload()
            if recheck is not None:
                payload["ai_recheck"] = recheck.to_payload()
            serialized = (
                json.dumps(payload, ensure_ascii=False, indent=2)
                .replace("&", "\\u0026")
                .replace("<", "\\u003c")
                .replace(">", "\\u003e")
            )
            path.write_text(
                serialized,
                encoding="utf-8",
            )
        elif path.suffix.lower() in {".html", ".htm"}:
            path.write_text(self._html(analysis, recheck=recheck), encoding="utf-8")
        else:
            raise ValueError("AI analysis export supports only JSON and HTML")
        return path

    @staticmethod
    def _html(
        analysis: AiDocumentAnalysis,
        *,
        recheck: AiRecheckAssessment | None = None,
    ) -> str:
        requirements = analysis.requirements
        requirement_groups = tuple(
            (name, _APPLICATION_REQUIREMENT_LABELS[name], getattr(requirements, name))
            for name in _APPLICATION_REQUIREMENTS_FINDING_FIELDS
        )
        all_requirements = tuple(item for _, _, items in requirement_groups for item in items)
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
        requirement_tables = "".join(
            f"<h3>{escape(label)}</h3><table><tr><th>Категория</th><th>Вывод</th>"
            f"<th>Источник</th></tr>{findings(items)}</table>"
            for _, label, items in requirement_groups
        )
        requirement_warnings = (
            "".join(f"<li>{escape(item)}</li>" for item in requirements.warnings) or "<li>Нет.</li>"
        )
        requirement_context_note = (
            "<p><strong>Контекст требований к заявке неполон.</strong></p>"
            if requirements.status is AiApplicationRequirementsStatus.PARTIAL
            and (
                len(requirements.document_ids) != len(requirements.included_document_ids)
                or requirements.warnings
            )
            else ""
        )
        legal = analysis.legal_risk_assessment
        legal_status = {
            AiLegalRiskStatus.COMPLETE: "Полный реестр подтверждённых условий",
            AiLegalRiskStatus.PARTIAL: "Частичный реестр; требуется проверка полноты",
            AiLegalRiskStatus.NO_VERIFIED_RISKS: (
                "Подтверждённые условия, требующие отдельной юридической проверки, не выявлены"
            ),
            AiLegalRiskStatus.UNAVAILABLE: "Оценка юридических рисков недоступна",
        }.get(legal.status, "Оценка юридических рисков недоступна")
        priority_labels = {
            AiLegalReviewPriority.URGENT: "Срочно",
            AiLegalReviewPriority.ELEVATED: "Повышенный",
            AiLegalReviewPriority.ROUTINE: "Плановый",
        }
        legal_counts = {
            priority: sum(item.review_priority is priority for item in legal.items)
            for priority in AiLegalReviewPriority
        }
        legal_rows = (
            "".join(
                "<tr>"
                f"<td>{escape(item.category.value)}</td>"
                f"<td>{escape(item.title)}</td>"
                f"<td>{escape(priority_labels[item.review_priority])}</td>"
                f"<td><table>{findings(legal_risk_source_findings(analysis, item))}</table></td>"
                f"<td>{escape(item.recommended_action)}</td>"
                "</tr>"
                for item in legal.items
            )
            or "<tr><td colspan='5'>Нет подтверждённых элементов.</td></tr>"
        )
        legal_warnings = (
            "".join(f"<li>{escape(item)}</li>" for item in legal.warnings) or "<li>Нет.</li>"
        )
        financial = analysis.financial_risk_assessment
        financial_status = {
            AiFinancialRiskStatus.COMPLETE: "Полный реестр подтверждённых условий",
            AiFinancialRiskStatus.PARTIAL: "Частичный реестр; требуется проверка полноты",
            AiFinancialRiskStatus.NO_VERIFIED_CONDITIONS: (
                "Подтверждённые финансово значимые условия не выявлены"
            ),
            AiFinancialRiskStatus.UNAVAILABLE: "Оценка финансовых условий недоступна",
        }.get(financial.status, "Оценка финансовых условий недоступна")
        financial_priority_labels = {
            AiFinancialReviewPriority.URGENT: "Срочно",
            AiFinancialReviewPriority.ELEVATED: "Повышенный",
            AiFinancialReviewPriority.ROUTINE: "Плановый",
        }
        financial_counts = {
            priority: sum(item.review_priority is priority for item in financial.items)
            for priority in AiFinancialReviewPriority
        }
        financial_rows = (
            "".join(
                "<tr>"
                f"<td>{escape(item.category.value)}</td>"
                f"<td>{escape(item.title)}</td>"
                f"<td>{escape(financial_priority_labels[item.review_priority])}</td>"
                f"<td><table>{findings(financial_risk_source_findings(analysis, item))}</table></td>"
                f"<td>{escape(item.recommended_action)}</td>"
                "</tr>"
                for item in financial.items
            )
            or "<tr><td colspan='5'>Нет подтверждённых элементов.</td></tr>"
        )
        financial_warnings = (
            "".join(f"<li>{escape(item)}</li>" for item in financial.warnings) or "<li>Нет.</li>"
        )
        competition = analysis.competition_assessment
        competition_status = {
            AiCompetitionStatus.COMPLETE: "Полный реестр подтверждённых условий",
            AiCompetitionStatus.PARTIAL: "Частичный реестр; требуется проверка полноты",
            AiCompetitionStatus.NO_VERIFIED_CONDITIONS: (
                "Документально подтверждённые условия, включённые в текущую политику "
                "конкурентной проверки, не выявлены."
            ),
            AiCompetitionStatus.UNAVAILABLE: "Оценка условий конкуренции недоступна",
        }.get(competition.status, "Оценка условий конкуренции недоступна")
        competition_priority_labels = {
            AiCompetitionReviewPriority.URGENT: "Срочно",
            AiCompetitionReviewPriority.ELEVATED: "Повышенный",
            AiCompetitionReviewPriority.ROUTINE: "Плановый",
        }
        competition_counts = {
            priority: sum(item.review_priority is priority for item in competition.items)
            for priority in AiCompetitionReviewPriority
        }
        competition_rows = (
            "".join(
                "<tr>"
                f"<td>{escape(item.category.value)}</td>"
                f"<td>{escape(item.title)}</td>"
                f"<td>{escape(competition_priority_labels[item.review_priority])}</td>"
                f"<td><table>{findings(competition_source_findings(analysis, item))}</table></td>"
                f"<td>{escape(item.recommended_action)}</td>"
                "</tr>"
                for item in competition.items
            )
            or "<tr><td colspan='5'>Нет подтверждённых элементов.</td></tr>"
        )
        competition_warnings = (
            "".join(f"<li>{escape(item)}</li>" for item in competition.warnings) or "<li>Нет.</li>"
        )
        context_note = (
            "<p><strong>Контекст сокращён по безопасному лимиту.</strong></p>"
            if analysis.context_truncated
            else ""
        )
        return (
            "<!doctype html><meta charset='utf-8'><title>AI analysis</title>"
            f"<h1>AI-анализ документации</h1>"
            f"{_ai_recheck_html(recheck)}"
            f"<p>Статус: {escape(analysis.status.value)}</p>"
            f"<p>Контекст: {analysis.context_document_count} документов, "
            f"{analysis.context_character_count} символов.</p>{context_note}"
            f"<p>{escape(analysis.summary)}</p>"
            f"{_documentation_completeness_html(analysis)}"
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
            f"<h2>Требования к заявке</h2><p>Статус: {escape(requirements.status.value)}; "
            f"найдено документов: {len(requirements.document_ids)}; включено: "
            f"{len(requirements.included_document_ids)}</p>{requirement_context_note}"
            f"{requirement_tables}<h3>Предупреждения по требованиям к заявке</h3>"
            f"<ul>{requirement_warnings}</ul>"
            f"<h2>Юридические риски</h2><p><strong>Информационная оценка; "
            f"не является юридическим заключением.</strong></p>"
            f"<p>Статус: {escape(legal_status)}; policy version: "
            f"{escape(legal.policy_version)}; срочно: "
            f"{legal_counts[AiLegalReviewPriority.URGENT]}; повышенный: "
            f"{legal_counts[AiLegalReviewPriority.ELEVATED]}; плановый: "
            f"{legal_counts[AiLegalReviewPriority.ROUTINE]}.</p>"
            f"<table><tr><th>Группа</th><th>Условие проверки</th><th>Приоритет</th>"
            f"<th>Исходные условия и источники</th><th>Действие</th></tr>{legal_rows}</table>"
            f"<h3>Предупреждения юридической оценки</h3><ul>{legal_warnings}</ul>"
            f"<h2>Финансовые условия</h2><p><strong>Информационная оценка условий "
            f"документации; не является финансовым прогнозом, расчётом убытка или "
            f"рекомендацией об участии.</strong></p>"
            f"<p>Статус: {escape(financial_status)}; policy version: "
            f"{escape(financial.policy_version)}; срочно: "
            f"{financial_counts[AiFinancialReviewPriority.URGENT]}; повышенный: "
            f"{financial_counts[AiFinancialReviewPriority.ELEVATED]}; плановый: "
            f"{financial_counts[AiFinancialReviewPriority.ROUTINE]}.</p>"
            f"<table><tr><th>Группа</th><th>Условие проверки</th><th>Приоритет</th>"
            f"<th>Исходные условия и источники</th><th>Действие</th></tr>"
            f"{financial_rows}</table>"
            f"<h3>Предупреждения финансовой оценки</h3><ul>{financial_warnings}</ul>"
            f"<h2>Анализ конкуренции</h2><p><strong>Информационная оценка документально "
            f"подтверждённых условий участия. Не является оценкой числа конкурентов, "
            f"вероятности победы, законности условий закупки или рекомендацией об "
            f"участии.</strong></p>"
            f"<p>Статус: {escape(competition_status)}; policy version: "
            f"{escape(competition.policy_version)}; срочно: "
            f"{competition_counts[AiCompetitionReviewPriority.URGENT]}; повышенный: "
            f"{competition_counts[AiCompetitionReviewPriority.ELEVATED]}; плановый: "
            f"{competition_counts[AiCompetitionReviewPriority.ROUTINE]}.</p>"
            f"<table><tr><th>Группа</th><th>Условие проверки</th><th>Приоритет</th>"
            f"<th>Исходные условия и источники</th><th>Действие</th></tr>"
            f"{competition_rows}</table>"
            f"<h3>Предупреждения конкурентной оценки</h3><ul>{competition_warnings}</ul>"
            f"<h2>Риски</h2><table>{findings(analysis.risks)}</table>"
            f"<h2>Подозрительные условия</h2><table>{findings(analysis.suspicious_conditions)}</table>"
            f"<h2>Противоречия</h2><table>{findings(analysis.contradictions)}</table>"
            f"<h2>Возможные отсутствующие документы по ответу AI — не подтверждено "
            f"локальной проверкой</h2><ul>"
            f"{''.join(f'<li>{escape(item)}</li>' for item in analysis.missing_documents) or '<li>Не указаны.</li>'}"
            f"</ul>"
            f"<h2>Источники</h2><ol>{sources}</ol>"
            f"<h2>Предупреждения</h2><ul>{warnings}</ul>"
            f"<h2>Итог AI</h2><p>{escape(analysis.final_ai_conclusion)}</p>"
        )
