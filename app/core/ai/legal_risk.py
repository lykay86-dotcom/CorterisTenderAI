"""Pure local legal-review policy over current verified specialized findings."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
import hashlib
import json

from app.core.ai.schemas import (
    AiAnalysisStatus,
    AiDocumentAnalysis,
    AiFinding,
    AiLegalReviewPriority,
    AiLegalRiskAssessment,
    AiLegalRiskCategory,
    AiLegalRiskItem,
    AiLegalRiskSourceRef,
    AiLegalRiskStatus,
)
from app.core.document_classification import (
    APPLICATION_REQUIREMENTS_SOURCE_KINDS,
    DocumentKind,
)


AI_LEGAL_RISK_POLICY_VERSION = "1"

LEGAL_RISK_SOURCE_POLICY: Mapping[tuple[str, str], AiLegalRiskCategory] = {
    ("requirements", "application_composition"): (
        AiLegalRiskCategory.APPLICATION_COMPOSITION_AND_DECLARATIONS
    ),
    ("requirements", "declarations_and_consents"): (
        AiLegalRiskCategory.APPLICATION_COMPOSITION_AND_DECLARATIONS
    ),
    ("requirements", "deadlines"): (AiLegalRiskCategory.APPLICATION_COMPOSITION_AND_DECLARATIONS),
    ("requirements", "submission_format_and_signature"): (
        AiLegalRiskCategory.SUBMISSION_FORMAT_AND_SIGNATURE
    ),
    ("requirements", "grounds_for_rejection"): AiLegalRiskCategory.GROUNDS_FOR_REJECTION,
    ("requirements", "participant_eligibility"): (
        AiLegalRiskCategory.ELIGIBILITY_AND_AUTHORIZATIONS
    ),
    ("requirements", "licenses"): AiLegalRiskCategory.ELIGIBILITY_AND_AUTHORIZATIONS,
    ("requirements", "certificates"): AiLegalRiskCategory.ELIGIBILITY_AND_AUTHORIZATIONS,
    ("requirements", "national_regime_and_origin"): (
        AiLegalRiskCategory.NATIONAL_REGIME_AND_ORIGIN
    ),
    ("requirements", "bid_security"): AiLegalRiskCategory.SECURITY_AND_GUARANTEES,
    ("requirements", "contract_security"): AiLegalRiskCategory.SECURITY_AND_GUARANTEES,
    ("requirements", "bank_guarantee"): AiLegalRiskCategory.SECURITY_AND_GUARANTEES,
    ("requirements", "ambiguities"): AiLegalRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS,
    ("requirements", "clarification_points"): (AiLegalRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS),
    ("requirements", "contradictions"): AiLegalRiskCategory.CONTRADICTIONS,
    ("draft_contract", "subject_and_scope"): (AiLegalRiskCategory.SCOPE_AND_CUSTOMER_DEPENDENCIES),
    ("draft_contract", "term_schedule_and_location"): (
        AiLegalRiskCategory.SCOPE_AND_CUSTOMER_DEPENDENCIES
    ),
    ("draft_contract", "customer_obligations_and_dependencies"): (
        AiLegalRiskCategory.SCOPE_AND_CUSTOMER_DEPENDENCIES
    ),
    ("draft_contract", "price_and_price_change"): (
        AiLegalRiskCategory.PRICE_PAYMENT_AND_CHANGE_MECHANISM
    ),
    ("draft_contract", "payment_terms"): (AiLegalRiskCategory.PRICE_PAYMENT_AND_CHANGE_MECHANISM),
    ("draft_contract", "acceptance_and_closing_documents"): (
        AiLegalRiskCategory.ACCEPTANCE_AND_CLOSING
    ),
    ("draft_contract", "performance_security"): (AiLegalRiskCategory.SECURITY_AND_GUARANTEES),
    ("draft_contract", "warranty_and_defect_remediation"): (
        AiLegalRiskCategory.WARRANTY_AND_REMEDIES
    ),
    ("draft_contract", "contractor_obligations_and_subcontracting"): (
        AiLegalRiskCategory.SUBCONTRACTING_AND_THIRD_PARTIES
    ),
    ("draft_contract", "liability_penalties_and_damages"): (
        AiLegalRiskCategory.LIABILITY_PENALTIES_AND_DAMAGES
    ),
    ("draft_contract", "change_suspension_and_termination"): (
        AiLegalRiskCategory.CHANGE_SUSPENSION_AND_TERMINATION
    ),
    ("draft_contract", "force_majeure_and_notifications"): (
        AiLegalRiskCategory.FORCE_MAJEURE_AND_NOTICES
    ),
    ("draft_contract", "dispute_confidentiality_and_ip"): (
        AiLegalRiskCategory.DISPUTES_CONFIDENTIALITY_AND_IP
    ),
    ("draft_contract", "ambiguities"): AiLegalRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS,
    ("draft_contract", "clarification_points"): (
        AiLegalRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("draft_contract", "contradictions"): AiLegalRiskCategory.CONTRADICTIONS,
    ("technical_specification", "standards_and_regulations"): (
        AiLegalRiskCategory.STANDARDS_AND_REGULATIONS
    ),
    ("technical_specification", "acceptance_and_quality"): (
        AiLegalRiskCategory.ACCEPTANCE_AND_CLOSING
    ),
    ("technical_specification", "customer_inputs_and_dependencies"): (
        AiLegalRiskCategory.SCOPE_AND_CUSTOMER_DEPENDENCIES
    ),
    ("technical_specification", "ambiguities"): (
        AiLegalRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("technical_specification", "clarification_points"): (
        AiLegalRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("technical_specification", "contradictions"): AiLegalRiskCategory.CONTRADICTIONS,
}

_URGENT_CATEGORIES = frozenset(
    {
        AiLegalRiskCategory.GROUNDS_FOR_REJECTION,
        AiLegalRiskCategory.CONTRADICTIONS,
    }
)
_ELEVATED_CATEGORIES = frozenset(
    {
        AiLegalRiskCategory.SUBMISSION_FORMAT_AND_SIGNATURE,
        AiLegalRiskCategory.ELIGIBILITY_AND_AUTHORIZATIONS,
        AiLegalRiskCategory.NATIONAL_REGIME_AND_ORIGIN,
        AiLegalRiskCategory.SECURITY_AND_GUARANTEES,
        AiLegalRiskCategory.PRICE_PAYMENT_AND_CHANGE_MECHANISM,
        AiLegalRiskCategory.LIABILITY_PENALTIES_AND_DAMAGES,
        AiLegalRiskCategory.CHANGE_SUSPENSION_AND_TERMINATION,
        AiLegalRiskCategory.SUBCONTRACTING_AND_THIRD_PARTIES,
        AiLegalRiskCategory.DISPUTES_CONFIDENTIALITY_AND_IP,
    }
)
LEGAL_RISK_CATEGORY_PRIORITIES: Mapping[AiLegalRiskCategory, AiLegalReviewPriority] = {
    category: (
        AiLegalReviewPriority.URGENT
        if category in _URGENT_CATEGORIES
        else AiLegalReviewPriority.ELEVATED
        if category in _ELEVATED_CATEGORIES
        else AiLegalReviewPriority.ROUTINE
    )
    for category in AiLegalRiskCategory
}

_PRESENTATION: Mapping[AiLegalRiskCategory, tuple[str, str]] = {
    AiLegalRiskCategory.APPLICATION_COMPOSITION_AND_DECLARATIONS: (
        "Состав заявки, заявления и сроки",
        "Проверить комплектность заявки, обязательные заявления и применимые сроки.",
    ),
    AiLegalRiskCategory.SUBMISSION_FORMAT_AND_SIGNATURE: (
        "Форма подачи и подписание заявки",
        "Проверить формат подачи, полномочия подписанта и требования к электронной подписи.",
    ),
    AiLegalRiskCategory.GROUNDS_FOR_REJECTION: (
        "Основания отклонения заявки",
        "Срочно проверить основание и подтверждающие документы до подачи заявки.",
    ),
    AiLegalRiskCategory.ELIGIBILITY_AND_AUTHORIZATIONS: (
        "Требования к участнику, лицензиям и допускам",
        "Проверить применимость требования и наличие действующих подтверждающих документов.",
    ),
    AiLegalRiskCategory.NATIONAL_REGIME_AND_ORIGIN: (
        "Национальный режим и происхождение",
        "Проверить применимые ограничения и документы о происхождении.",
    ),
    AiLegalRiskCategory.SECURITY_AND_GUARANTEES: (
        "Обеспечение и гарантии",
        "Проверить форму, срок, размер и условия предоставления обеспечения или гарантии.",
    ),
    AiLegalRiskCategory.SCOPE_AND_CUSTOMER_DEPENDENCIES: (
        "Объём обязательств и зависимости от заказчика",
        "Сверить границы обязательств, исходные данные и действия заказчика.",
    ),
    AiLegalRiskCategory.PRICE_PAYMENT_AND_CHANGE_MECHANISM: (
        "Цена, оплата и механизм изменения условий",
        "Проверить договорный механизм цены, оплаты и изменения условий без финансового расчёта.",
    ),
    AiLegalRiskCategory.ACCEPTANCE_AND_CLOSING: (
        "Приёмка и закрывающие документы",
        "Проверить процедуру приёмки, критерии качества и комплект закрывающих документов.",
    ),
    AiLegalRiskCategory.LIABILITY_PENALTIES_AND_DAMAGES: (
        "Ответственность, штрафы и убытки",
        "Проверить основания, пределы и порядок применения ответственности.",
    ),
    AiLegalRiskCategory.CHANGE_SUSPENSION_AND_TERMINATION: (
        "Изменение, приостановка и прекращение договора",
        "Проверить основания, уведомления и последствия изменения или прекращения договора.",
    ),
    AiLegalRiskCategory.WARRANTY_AND_REMEDIES: (
        "Гарантия и устранение недостатков",
        "Проверить гарантийные процедуры, сроки и порядок устранения недостатков.",
    ),
    AiLegalRiskCategory.SUBCONTRACTING_AND_THIRD_PARTIES: (
        "Субподряд и третьи лица",
        "Проверить ограничения, согласования и ответственность за привлечённых лиц.",
    ),
    AiLegalRiskCategory.FORCE_MAJEURE_AND_NOTICES: (
        "Форс-мажор и уведомления",
        "Проверить порядок уведомления, подтверждения и последствия форс-мажора.",
    ),
    AiLegalRiskCategory.DISPUTES_CONFIDENTIALITY_AND_IP: (
        "Споры, конфиденциальность и интеллектуальные права",
        "Проверить подсудность, конфиденциальность и распределение интеллектуальных прав.",
    ),
    AiLegalRiskCategory.STANDARDS_AND_REGULATIONS: (
        "Стандарты и нормативные требования",
        "Проверить применимость указанных стандартов и нормативных требований.",
    ),
    AiLegalRiskCategory.AMBIGUITIES_AND_CLARIFICATIONS: (
        "Неоднозначности и вопросы для уточнения",
        "Сформулировать вопрос и при необходимости направить запрос на разъяснение.",
    ),
    AiLegalRiskCategory.CONTRADICTIONS: (
        "Подтверждённые противоречия документов",
        "Срочно сопоставить независимые источники и запросить официальное разъяснение.",
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
    AiLegalReviewPriority.URGENT: 0,
    AiLegalReviewPriority.ELEVATED: 1,
    AiLegalReviewPriority.ROUTINE: 2,
}


def assess_legal_risks(analysis: AiDocumentAnalysis) -> AiLegalRiskAssessment:
    """Build a deterministic legal-review registry without I/O or text heuristics."""
    try:
        analysis_status = AiAnalysisStatus(analysis.status)
    except (TypeError, ValueError):
        analysis_status = AiAnalysisStatus.INVALID_RESPONSE
    if analysis_status in _FAILURE_STATUSES:
        return _unavailable("Оценка юридических рисков недоступна для текущего AI-результата.")
    if analysis.provenance is None:
        return _unavailable("Отсутствует current provenance для юридической проверки.")

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

    refs_by_item: dict[tuple[AiLegalRiskCategory, str], set[AiLegalRiskSourceRef]] = defaultdict(
        set
    )
    for (section_name, field_name), category in sorted(
        LEGAL_RISK_SOURCE_POLICY.items(), key=lambda item: item[0]
    ):
        section = getattr(analysis, section_name)
        for finding in getattr(section, field_name):
            if not analysis.is_current_verified(finding) or finding.evidence is None:
                warnings.append("Часть юридически значимых условий не имеет current evidence.")
                continue
            evidence = finding.evidence
            sources = tuple(
                source
                for source in analysis.provenance.sources
                if source.document_id == evidence.document_id
            )
            allowed_kinds = {kind.value for kind in _SECTION_KINDS[section_name]}
            if len(sources) != 1 or sources[0].document_kind not in allowed_kinds:
                warnings.append("Источник юридически значимого условия не прошёл scoped проверку.")
                continue
            ref = AiLegalRiskSourceRef(section_name, field_name, evidence.citation_id)
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
        AiLegalRiskStatus.PARTIAL
        if safe_warnings
        else AiLegalRiskStatus.COMPLETE
        if items
        else AiLegalRiskStatus.NO_VERIFIED_RISKS
    )
    return AiLegalRiskAssessment(
        status=status,
        policy_version=AI_LEGAL_RISK_POLICY_VERSION,
        items=items,
        warnings=safe_warnings,
    )


def legal_risk_source_findings(
    analysis: AiDocumentAnalysis,
    item: AiLegalRiskItem,
) -> tuple[AiFinding, ...]:
    """Resolve an item back to current findings without trusting persisted references."""
    result: list[AiFinding] = []
    seen: set[tuple[str, str]] = set()
    for ref in item.source_refs:
        if LEGAL_RISK_SOURCE_POLICY.get((ref.section, ref.field)) != item.category:
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
    category: AiLegalRiskCategory,
    citation_id: str,
    refs: tuple[AiLegalRiskSourceRef, ...],
) -> AiLegalRiskItem:
    title, action = _PRESENTATION[category]
    canonical = json.dumps(
        {
            "category": category.value,
            "citation_ids": sorted({citation_id}),
            "policy_version": AI_LEGAL_RISK_POLICY_VERSION,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    risk_id = "legal_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return AiLegalRiskItem(
        risk_id=risk_id,
        category=category,
        review_priority=LEGAL_RISK_CATEGORY_PRIORITIES[category],
        title=title,
        source_refs=refs,
        recommended_action=action,
    )


def _unavailable(warning: str) -> AiLegalRiskAssessment:
    return AiLegalRiskAssessment(
        status=AiLegalRiskStatus.UNAVAILABLE,
        policy_version=AI_LEGAL_RISK_POLICY_VERSION,
        warnings=(warning,),
    )


def _ref_sort_key(ref: AiLegalRiskSourceRef) -> tuple[str, str, str]:
    return ref.section, ref.field, ref.citation_id


def _item_sort_key(item: AiLegalRiskItem) -> tuple[object, ...]:
    return (
        _PRIORITY_ORDER[AiLegalReviewPriority(item.review_priority)],
        AiLegalRiskCategory(item.category).value,
        tuple(ref.citation_id for ref in item.source_refs),
        item.risk_id,
    )


__all__ = [
    "AI_LEGAL_RISK_POLICY_VERSION",
    "LEGAL_RISK_CATEGORY_PRIORITIES",
    "LEGAL_RISK_SOURCE_POLICY",
    "assess_legal_risks",
    "legal_risk_source_findings",
]
