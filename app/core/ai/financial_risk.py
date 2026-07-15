"""Pure local financial-condition policy over current verified specialized findings."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
import hashlib
import json

from app.core.ai.schemas import (
    AiAnalysisStatus,
    AiDocumentAnalysis,
    AiFinancialReviewPriority,
    AiFinancialRiskAssessment,
    AiFinancialRiskCategory,
    AiFinancialRiskItem,
    AiFinancialRiskSourceRef,
    AiFinancialRiskStatus,
    AiFinding,
)
from app.core.document_classification import (
    APPLICATION_REQUIREMENTS_SOURCE_KINDS,
    DocumentKind,
)


AI_FINANCIAL_RISK_POLICY_VERSION = "1"

FINANCIAL_RISK_SOURCE_POLICY: Mapping[tuple[str, str], AiFinancialRiskCategory] = {
    ("requirements", "price_proposal_and_estimate"): AiFinancialRiskCategory.PRICE_AND_ESTIMATE,
    ("requirements", "bid_security"): (AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS),
    ("requirements", "contract_security"): (AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS),
    ("requirements", "bank_guarantee"): (AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS),
    ("requirements", "warranty"): AiFinancialRiskCategory.WARRANTY_AND_DEFECT_COSTS,
    ("requirements", "national_regime_and_origin"): (
        AiFinancialRiskCategory.NATIONAL_REGIME_AND_SUPPLY_RESTRICTIONS
    ),
    ("requirements", "ambiguities"): (AiFinancialRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS),
    ("requirements", "clarification_points"): (
        AiFinancialRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("requirements", "contradictions"): AiFinancialRiskCategory.CONTRADICTIONS,
    ("technical_specification", "scope"): (AiFinancialRiskCategory.SCOPE_AND_VOLUME_UNCERTAINTY),
    ("technical_specification", "deliverables"): (
        AiFinancialRiskCategory.SCOPE_AND_VOLUME_UNCERTAINTY
    ),
    ("technical_specification", "quantities_and_volumes"): (
        AiFinancialRiskCategory.SCOPE_AND_VOLUME_UNCERTAINTY
    ),
    ("technical_specification", "technical_characteristics"): (
        AiFinancialRiskCategory.MATERIALS_AND_EQUIPMENT_COSTS
    ),
    ("technical_specification", "materials_and_equipment"): (
        AiFinancialRiskCategory.MATERIALS_AND_EQUIPMENT_COSTS
    ),
    ("technical_specification", "execution_conditions"): (
        AiFinancialRiskCategory.EXECUTION_SCHEDULE_AND_RESOURCE_LOAD
    ),
    ("technical_specification", "stages_and_deadlines"): (
        AiFinancialRiskCategory.EXECUTION_SCHEDULE_AND_RESOURCE_LOAD
    ),
    ("technical_specification", "acceptance_and_quality"): (
        AiFinancialRiskCategory.ACCEPTANCE_AND_PAYMENT_DEPENDENCY
    ),
    ("technical_specification", "customer_inputs_and_dependencies"): (
        AiFinancialRiskCategory.CUSTOMER_INPUTS_AND_DEPENDENCIES
    ),
    ("technical_specification", "ambiguities"): (
        AiFinancialRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("technical_specification", "clarification_points"): (
        AiFinancialRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("technical_specification", "contradictions"): AiFinancialRiskCategory.CONTRADICTIONS,
    ("draft_contract", "subject_and_scope"): (AiFinancialRiskCategory.SCOPE_AND_VOLUME_UNCERTAINTY),
    ("draft_contract", "term_schedule_and_location"): (
        AiFinancialRiskCategory.EXECUTION_SCHEDULE_AND_RESOURCE_LOAD
    ),
    ("draft_contract", "price_and_price_change"): AiFinancialRiskCategory.PRICE_AND_ESTIMATE,
    ("draft_contract", "payment_terms"): AiFinancialRiskCategory.PAYMENT_AND_CASH_FLOW,
    ("draft_contract", "acceptance_and_closing_documents"): (
        AiFinancialRiskCategory.ACCEPTANCE_AND_PAYMENT_DEPENDENCY
    ),
    ("draft_contract", "performance_security"): (
        AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS
    ),
    ("draft_contract", "warranty_and_defect_remediation"): (
        AiFinancialRiskCategory.WARRANTY_AND_DEFECT_COSTS
    ),
    ("draft_contract", "customer_obligations_and_dependencies"): (
        AiFinancialRiskCategory.CUSTOMER_INPUTS_AND_DEPENDENCIES
    ),
    ("draft_contract", "contractor_obligations_and_subcontracting"): (
        AiFinancialRiskCategory.SUBCONTRACTING_AND_THIRD_PARTY_COSTS
    ),
    ("draft_contract", "liability_penalties_and_damages"): (
        AiFinancialRiskCategory.LIABILITY_PENALTIES_AND_DAMAGES
    ),
    ("draft_contract", "change_suspension_and_termination"): (
        AiFinancialRiskCategory.CHANGE_SUSPENSION_AND_TERMINATION
    ),
    ("draft_contract", "ambiguities"): (AiFinancialRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS),
    ("draft_contract", "clarification_points"): (
        AiFinancialRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("draft_contract", "contradictions"): AiFinancialRiskCategory.CONTRADICTIONS,
}

_ELEVATED_CATEGORIES = frozenset(
    {
        AiFinancialRiskCategory.PRICE_AND_ESTIMATE,
        AiFinancialRiskCategory.PAYMENT_AND_CASH_FLOW,
        AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS,
        AiFinancialRiskCategory.SCOPE_AND_VOLUME_UNCERTAINTY,
        AiFinancialRiskCategory.ACCEPTANCE_AND_PAYMENT_DEPENDENCY,
        AiFinancialRiskCategory.WARRANTY_AND_DEFECT_COSTS,
        AiFinancialRiskCategory.LIABILITY_PENALTIES_AND_DAMAGES,
        AiFinancialRiskCategory.CHANGE_SUSPENSION_AND_TERMINATION,
    }
)
FINANCIAL_RISK_CATEGORY_PRIORITIES: Mapping[AiFinancialRiskCategory, AiFinancialReviewPriority] = {
    category: (
        AiFinancialReviewPriority.URGENT
        if category is AiFinancialRiskCategory.CONTRADICTIONS
        else AiFinancialReviewPriority.ELEVATED
        if category in _ELEVATED_CATEGORIES
        else AiFinancialReviewPriority.ROUTINE
    )
    for category in AiFinancialRiskCategory
}

_PRESENTATION: Mapping[AiFinancialRiskCategory, tuple[str, str]] = {
    AiFinancialRiskCategory.PRICE_AND_ESTIMATE: (
        "Цена и состав сметы",
        "Сверить подтверждённые ценовые условия с коммерческим расчётом; значения не переносить автоматически.",
    ),
    AiFinancialRiskCategory.PAYMENT_AND_CASH_FLOW: (
        "Оплата и денежный поток",
        "Сверить подтверждённые условия аванса и оплаты с коммерческим расчётом; значения не переносить автоматически.",
    ),
    AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS: (
        "Обеспечение и стоимость гарантий",
        "Подтвердить размер и стоимость обеспечения в коммерческом расчёте и проверить доступный лимит компании.",
    ),
    AiFinancialRiskCategory.SCOPE_AND_VOLUME_UNCERTAINTY: (
        "Неопределённость объёма и состава работ",
        "Уточнить объём и включить подтверждённые дополнительные затраты в смету.",
    ),
    AiFinancialRiskCategory.MATERIALS_AND_EQUIPMENT_COSTS: (
        "Материалы и оборудование",
        "Проверить состав, количество и подтверждённые цены материалов и оборудования вручную.",
    ),
    AiFinancialRiskCategory.EXECUTION_SCHEDULE_AND_RESOURCE_LOAD: (
        "Сроки и ресурсная нагрузка",
        "Сверить график выполнения с ресурсами и вручную учесть подтверждённые затраты по срокам.",
    ),
    AiFinancialRiskCategory.ACCEPTANCE_AND_PAYMENT_DEPENDENCY: (
        "Приёмка и зависимость оплаты",
        "Проверить условия приёмки, закрывающие документы и их влияние на срок оплаты.",
    ),
    AiFinancialRiskCategory.CUSTOMER_INPUTS_AND_DEPENDENCIES: (
        "Данные и действия заказчика",
        "Уточнить зависимости от заказчика и вручную оценить связанные дополнительные затраты.",
    ),
    AiFinancialRiskCategory.WARRANTY_AND_DEFECT_COSTS: (
        "Гарантийные обязательства и устранение дефектов",
        "Подтвердить гарантийный объём и вручную учесть связанные затраты в смете.",
    ),
    AiFinancialRiskCategory.LIABILITY_PENALTIES_AND_DAMAGES: (
        "Ответственность, штрафы и убытки",
        "Провести ручную оценку потенциальной финансовой нагрузки без автоматического расчёта возможного ущерба.",
    ),
    AiFinancialRiskCategory.CHANGE_SUSPENSION_AND_TERMINATION: (
        "Изменение и прекращение договора",
        "Проверить финансовые последствия изменения, приостановки и прекращения договора вручную.",
    ),
    AiFinancialRiskCategory.SUBCONTRACTING_AND_THIRD_PARTY_COSTS: (
        "Субподряд и расходы третьих лиц",
        "Подтвердить объём субподряда и вручную учесть документально подтверждённые расходы.",
    ),
    AiFinancialRiskCategory.NATIONAL_REGIME_AND_SUPPLY_RESTRICTIONS: (
        "Национальный режим и ограничения поставки",
        "Проверить влияние ограничений поставки на доступность и стоимость без автоматической подстановки цен.",
    ),
    AiFinancialRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS: (
        "Неоднозначности финансовых условий",
        "Сформулировать вопрос и запросить разъяснение до фиксации финансовых допущений.",
    ),
    AiFinancialRiskCategory.CONTRADICTIONS: (
        "Противоречия финансово значимых условий",
        "Срочно сопоставить независимые источники и запросить официальное разъяснение до расчёта.",
    ),
}

_FAILURE_STATUSES = frozenset(
    {
        AiAnalysisStatus.NO_DOCUMENTS,
        AiAnalysisStatus.PROVIDER_DISABLED,
        AiAnalysisStatus.PROVIDER_ERROR,
        AiAnalysisStatus.INVALID_RESPONSE,
        AiAnalysisStatus.CACHE_INCOMPATIBLE,
    }
)
_SECTION_KINDS: Mapping[str, frozenset[DocumentKind]] = {
    "requirements": APPLICATION_REQUIREMENTS_SOURCE_KINDS,
    "technical_specification": frozenset({DocumentKind.TECHNICAL_SPECIFICATION}),
    "draft_contract": frozenset({DocumentKind.DRAFT_CONTRACT}),
}
_PRIORITY_ORDER = {
    AiFinancialReviewPriority.URGENT: 0,
    AiFinancialReviewPriority.ELEVATED: 1,
    AiFinancialReviewPriority.ROUTINE: 2,
}


def assess_financial_risks(analysis: AiDocumentAnalysis) -> AiFinancialRiskAssessment:
    """Build a deterministic financial-condition registry without I/O or heuristics."""
    try:
        analysis_status = AiAnalysisStatus(analysis.status)
    except (TypeError, ValueError):
        analysis_status = AiAnalysisStatus.INVALID_RESPONSE
    if analysis_status in _FAILURE_STATUSES:
        return _unavailable("Оценка финансовых условий недоступна для текущего AI-результата.")
    if analysis.provenance is None:
        return _unavailable("Отсутствует current provenance для оценки финансовых условий.")

    warnings: list[str] = []
    if str(analysis.requirements.status) != "complete":
        warnings.append("Контекст требований к заявке неполон.")
    if str(analysis.draft_contract.status) != "complete":
        warnings.append("Контекст проекта договора/контракта неполон.")
    if (
        analysis.technical_specification.document_ids
        and str(analysis.technical_specification.status) != "complete"
    ):
        warnings.append("Релевантный контекст технического задания неполон.")
    if analysis.context_truncated:
        warnings.append("Контекст AI-анализа был сокращён по безопасному лимиту.")
    warnings.extend(analysis.requirements.warnings)
    warnings.extend(analysis.draft_contract.warnings)
    warnings.extend(analysis.technical_specification.warnings)

    refs_by_item: dict[tuple[AiFinancialRiskCategory, str], set[AiFinancialRiskSourceRef]] = (
        defaultdict(set)
    )
    for (section_name, field_name), category in sorted(
        FINANCIAL_RISK_SOURCE_POLICY.items(), key=lambda item: item[0]
    ):
        section = getattr(analysis, section_name)
        for finding in getattr(section, field_name):
            if not analysis.is_current_verified(finding) or finding.evidence is None:
                warnings.append("Часть финансово значимых условий не имеет current evidence.")
                continue
            evidence = finding.evidence
            sources = tuple(
                source
                for source in analysis.provenance.sources
                if source.document_id == evidence.document_id
            )
            allowed_kinds = {kind.value for kind in _SECTION_KINDS[section_name]}
            if len(sources) != 1 or sources[0].document_kind not in allowed_kinds:
                warnings.append("Источник финансово значимого условия не прошёл scoped проверку.")
                continue
            ref = AiFinancialRiskSourceRef(section_name, field_name, evidence.citation_id)
            refs_by_item[(category, evidence.citation_id)].add(ref)

    items = tuple(
        sorted(
            (
                _item(category, citation_id, tuple(sorted(refs, key=_ref_sort_key)))
                for (category, citation_id), refs in refs_by_item.items()
            ),
            key=_item_sort_key,
        )
    )
    safe_warnings = tuple(dict.fromkeys(item for item in warnings if item.strip()))
    status = (
        AiFinancialRiskStatus.PARTIAL
        if safe_warnings
        else AiFinancialRiskStatus.COMPLETE
        if items
        else AiFinancialRiskStatus.NO_VERIFIED_CONDITIONS
    )
    return AiFinancialRiskAssessment(
        status=status,
        policy_version=AI_FINANCIAL_RISK_POLICY_VERSION,
        items=items,
        warnings=safe_warnings,
    )


def financial_risk_source_findings(
    analysis: AiDocumentAnalysis,
    item: AiFinancialRiskItem,
) -> tuple[AiFinding, ...]:
    """Resolve an item back to current findings without trusting persisted references."""
    result: list[AiFinding] = []
    seen: set[tuple[str, str]] = set()
    for ref in item.source_refs:
        if FINANCIAL_RISK_SOURCE_POLICY.get((ref.section, ref.field)) != item.category:
            continue
        section = getattr(analysis, ref.section, None)
        findings = getattr(section, ref.field, ()) if section is not None else ()
        for finding in findings:
            evidence = finding.evidence
            if (
                evidence is None
                or evidence.citation_id != ref.citation_id
                or not analysis.is_current_verified(finding)
            ):
                continue
            key = (evidence.citation_id, finding.statement)
            if key not in seen:
                seen.add(key)
                result.append(finding)
    return tuple(result)


def _item(
    category: AiFinancialRiskCategory,
    citation_id: str,
    refs: tuple[AiFinancialRiskSourceRef, ...],
) -> AiFinancialRiskItem:
    title, action = _PRESENTATION[category]
    canonical = json.dumps(
        {
            "category": category.value,
            "citation_ids": sorted({citation_id}),
            "policy_version": AI_FINANCIAL_RISK_POLICY_VERSION,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    risk_id = "financial_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return AiFinancialRiskItem(
        risk_id=risk_id,
        category=category,
        review_priority=FINANCIAL_RISK_CATEGORY_PRIORITIES[category],
        title=title,
        source_refs=refs,
        recommended_action=action,
    )


def _unavailable(warning: str) -> AiFinancialRiskAssessment:
    return AiFinancialRiskAssessment(
        status=AiFinancialRiskStatus.UNAVAILABLE,
        policy_version=AI_FINANCIAL_RISK_POLICY_VERSION,
        warnings=(warning,),
    )


def _ref_sort_key(ref: AiFinancialRiskSourceRef) -> tuple[str, str, str]:
    return ref.section, ref.field, ref.citation_id


def _item_sort_key(item: AiFinancialRiskItem) -> tuple[object, ...]:
    return (
        _PRIORITY_ORDER[AiFinancialReviewPriority(item.review_priority)],
        AiFinancialRiskCategory(item.category).value,
        tuple(ref.citation_id for ref in item.source_refs),
        item.risk_id,
    )


__all__ = [
    "AI_FINANCIAL_RISK_POLICY_VERSION",
    "FINANCIAL_RISK_CATEGORY_PRIORITIES",
    "FINANCIAL_RISK_SOURCE_POLICY",
    "assess_financial_risks",
    "financial_risk_source_findings",
]
