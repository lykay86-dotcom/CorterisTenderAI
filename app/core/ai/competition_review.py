"""Pure local competition-condition policy over current verified specialized findings."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
import hashlib
import json

from app.core.ai.schemas import (
    AiAnalysisStatus,
    AiDocumentAnalysis,
    AiCompetitionReviewPriority,
    AiCompetitionAssessment,
    AiCompetitionCategory,
    AiCompetitionItem,
    AiCompetitionSourceRef,
    AiCompetitionStatus,
    AiFinding,
)
from app.core.document_classification import (
    APPLICATION_REQUIREMENTS_SOURCE_KINDS,
    DocumentKind,
)


AI_COMPETITION_POLICY_VERSION = "1"

COMPETITION_SOURCE_POLICY: Mapping[tuple[str, str], AiCompetitionCategory] = {
    ("requirements", "application_composition"): (
        AiCompetitionCategory.APPLICATION_AND_SUBMISSION_CONDITIONS
    ),
    ("requirements", "declarations_and_consents"): (
        AiCompetitionCategory.APPLICATION_AND_SUBMISSION_CONDITIONS
    ),
    ("requirements", "documents"): (AiCompetitionCategory.APPLICATION_AND_SUBMISSION_CONDITIONS),
    ("requirements", "submission_format_and_signature"): (
        AiCompetitionCategory.APPLICATION_AND_SUBMISSION_CONDITIONS
    ),
    ("requirements", "deadlines"): (AiCompetitionCategory.APPLICATION_AND_SUBMISSION_CONDITIONS),
    ("requirements", "participant_eligibility"): AiCompetitionCategory.PARTICIPANT_ELIGIBILITY,
    ("requirements", "experience"): AiCompetitionCategory.EXPERIENCE_AND_TRACK_RECORD,
    ("requirements", "licenses"): (AiCompetitionCategory.LICENSES_CERTIFICATES_AND_AUTHORIZATIONS),
    ("requirements", "certificates"): (
        AiCompetitionCategory.LICENSES_CERTIFICATES_AND_AUTHORIZATIONS
    ),
    ("requirements", "specialists"): AiCompetitionCategory.PERSONNEL_AND_EQUIPMENT,
    ("requirements", "equipment"): AiCompetitionCategory.PERSONNEL_AND_EQUIPMENT,
    ("requirements", "bid_security"): AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS,
    ("requirements", "contract_security"): AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS,
    ("requirements", "bank_guarantee"): AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS,
    ("requirements", "national_regime_and_origin"): (
        AiCompetitionCategory.NATIONAL_REGIME_AND_ORIGIN
    ),
    ("requirements", "grounds_for_rejection"): AiCompetitionCategory.GROUNDS_FOR_REJECTION,
    ("requirements", "ambiguities"): AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS,
    ("requirements", "clarification_points"): (
        AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("requirements", "contradictions"): AiCompetitionCategory.CONTRADICTIONS,
    ("technical_specification", "technical_characteristics"): (
        AiCompetitionCategory.TECHNICAL_SPECIFICITY_AND_EQUIVALENCE
    ),
    ("technical_specification", "materials_and_equipment"): (
        AiCompetitionCategory.TECHNICAL_SPECIFICITY_AND_EQUIVALENCE
    ),
    ("technical_specification", "standards_and_regulations"): (
        AiCompetitionCategory.STANDARDS_AND_COMPATIBILITY
    ),
    ("technical_specification", "acceptance_and_quality"): (
        AiCompetitionCategory.STANDARDS_AND_COMPATIBILITY
    ),
    ("technical_specification", "execution_conditions"): (
        AiCompetitionCategory.GEOGRAPHY_SITE_AND_EXECUTION_CONSTRAINTS
    ),
    ("technical_specification", "stages_and_deadlines"): (
        AiCompetitionCategory.GEOGRAPHY_SITE_AND_EXECUTION_CONSTRAINTS
    ),
    ("technical_specification", "customer_inputs_and_dependencies"): (
        AiCompetitionCategory.GEOGRAPHY_SITE_AND_EXECUTION_CONSTRAINTS
    ),
    ("technical_specification", "ambiguities"): (
        AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("technical_specification", "clarification_points"): (
        AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("technical_specification", "contradictions"): AiCompetitionCategory.CONTRADICTIONS,
    ("draft_contract", "term_schedule_and_location"): (
        AiCompetitionCategory.GEOGRAPHY_SITE_AND_EXECUTION_CONSTRAINTS
    ),
    ("draft_contract", "performance_security"): (
        AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS
    ),
    ("draft_contract", "contractor_obligations_and_subcontracting"): (
        AiCompetitionCategory.SUBCONTRACTING_AND_THIRD_PARTIES
    ),
    ("draft_contract", "ambiguities"): (AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS),
    ("draft_contract", "clarification_points"): (
        AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS
    ),
    ("draft_contract", "contradictions"): AiCompetitionCategory.CONTRADICTIONS,
}

_ELEVATED_CATEGORIES = frozenset(
    {
        AiCompetitionCategory.PARTICIPANT_ELIGIBILITY,
        AiCompetitionCategory.EXPERIENCE_AND_TRACK_RECORD,
        AiCompetitionCategory.LICENSES_CERTIFICATES_AND_AUTHORIZATIONS,
        AiCompetitionCategory.PERSONNEL_AND_EQUIPMENT,
        AiCompetitionCategory.TECHNICAL_SPECIFICITY_AND_EQUIVALENCE,
        AiCompetitionCategory.NATIONAL_REGIME_AND_ORIGIN,
        AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS,
        AiCompetitionCategory.GEOGRAPHY_SITE_AND_EXECUTION_CONSTRAINTS,
    }
)
COMPETITION_CATEGORY_PRIORITIES: Mapping[AiCompetitionCategory, AiCompetitionReviewPriority] = {
    category: (
        AiCompetitionReviewPriority.URGENT
        if category
        in {AiCompetitionCategory.GROUNDS_FOR_REJECTION, AiCompetitionCategory.CONTRADICTIONS}
        else AiCompetitionReviewPriority.ELEVATED
        if category in _ELEVATED_CATEGORIES
        else AiCompetitionReviewPriority.ROUTINE
    )
    for category in AiCompetitionCategory
}

_PRESENTATION: Mapping[AiCompetitionCategory, tuple[str, str]] = {
    AiCompetitionCategory.APPLICATION_AND_SUBMISSION_CONDITIONS: (
        "Состав и процедура подачи заявки",
        "Оценить административную нагрузку и однозначность выполнения требований к подаче; "
        "не трактовать их как ограничение конкуренции автоматически.",
    ),
    AiCompetitionCategory.PARTICIPANT_ELIGIBILITY: (
        "Требования к допуску участника",
        "Проверить обязательность и соразмерность требований к участнику и их возможное "
        "влияние на круг допустимых участников.",
    ),
    AiCompetitionCategory.EXPERIENCE_AND_TRACK_RECORD: (
        "Опыт и подтверждённая квалификация",
        "Проверить соразмерность требуемого опыта предмету закупки и допустимые способы его "
        "подтверждения.",
    ),
    AiCompetitionCategory.LICENSES_CERTIFICATES_AND_AUTHORIZATIONS: (
        "Лицензии, сертификаты и авторизации",
        "Проверить обязательность документов, допустимые аналоги и доступность подтверждения "
        "без автоматического вывода об ограничении.",
    ),
    AiCompetitionCategory.PERSONNEL_AND_EQUIPMENT: (
        "Персонал и оборудование участника",
        "Проверить требования к собственным ресурсам, возможность аренды, привлечения партнёров "
        "или эквивалентного подтверждения.",
    ),
    AiCompetitionCategory.TECHNICAL_SPECIFICITY_AND_EQUIVALENCE: (
        "Техническая специфика и эквивалентность",
        "Проверить функциональность характеристик, допустимость эквивалентов и нейтральность "
        "технического описания; не делать автоматический вывод о заточке.",
    ),
    AiCompetitionCategory.STANDARDS_AND_COMPATIBILITY: (
        "Стандарты, качество и совместимость",
        "Проверить применимость стандартов, методы подтверждения качества и доступность "
        "совместимых решений.",
    ),
    AiCompetitionCategory.NATIONAL_REGIME_AND_ORIGIN: (
        "Национальный режим и происхождение",
        "Проверить применимые ограничения, допустимые товары и документы о происхождении.",
    ),
    AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS: (
        "Обеспечение и финансовый порог участия",
        "Проверить форму и условия обеспечения и их влияние на доступность участия без расчёта "
        "уровня конкуренции.",
    ),
    AiCompetitionCategory.GEOGRAPHY_SITE_AND_EXECUTION_CONSTRAINTS: (
        "География, объект и сроки исполнения",
        "Проверить обязательность присутствия или осмотра, территориальные условия и "
        "реалистичность сроков для потенциальных участников.",
    ),
    AiCompetitionCategory.SUBCONTRACTING_AND_THIRD_PARTIES: (
        "Субподряд, партнёры и третьи лица",
        "Проверить ограничения на субподряд и партнёрскую модель исполнения и их влияние на "
        "допустимый круг участников.",
    ),
    AiCompetitionCategory.GROUNDS_FOR_REJECTION: (
        "Основания отклонения заявки",
        "Срочно проверить однозначность основания отклонения и возможность полного выполнения "
        "требования до подачи заявки.",
    ),
    AiCompetitionCategory.AMBIGUITIES_AND_CLARIFICATIONS: (
        "Неоднозначности условий участия",
        "Сформулировать запрос на разъяснение; не делать вывод о состоянии конкуренции до "
        "получения официального ответа.",
    ),
    AiCompetitionCategory.CONTRADICTIONS: (
        "Противоречия условий участия",
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
    AiCompetitionReviewPriority.URGENT: 0,
    AiCompetitionReviewPriority.ELEVATED: 1,
    AiCompetitionReviewPriority.ROUTINE: 2,
}


def assess_competition_conditions(analysis: AiDocumentAnalysis) -> AiCompetitionAssessment:
    """Build a deterministic competition-condition registry without I/O or heuristics."""
    try:
        analysis_status = AiAnalysisStatus(analysis.status)
    except (TypeError, ValueError):
        analysis_status = AiAnalysisStatus.INVALID_RESPONSE
    if analysis_status in _FAILURE_STATUSES:
        return _unavailable("Оценка условий конкуренции недоступна для текущего AI-результата.")
    if analysis.provenance is None:
        return _unavailable("Отсутствует current provenance для оценки условий конкуренции.")

    warnings: list[str] = []
    if not analysis.requirements.document_ids or str(analysis.requirements.status) != "complete":
        warnings.append("Контекст требований к заявке неполон.")
    if analysis.draft_contract.document_ids and str(analysis.draft_contract.status) != "complete":
        warnings.append("Контекст проекта договора/контракта неполон.")
    if (
        not analysis.technical_specification.document_ids
        or str(analysis.technical_specification.status) != "complete"
    ):
        warnings.append("Релевантный контекст технического задания неполон.")
    if analysis.context_truncated:
        warnings.append("Контекст AI-анализа был сокращён по безопасному лимиту.")
    warnings.extend(analysis.requirements.warnings)
    warnings.extend(analysis.draft_contract.warnings)
    warnings.extend(analysis.technical_specification.warnings)

    refs_by_item: dict[tuple[AiCompetitionCategory, str], set[AiCompetitionSourceRef]] = (
        defaultdict(set)
    )
    for (section_name, field_name), category in sorted(
        COMPETITION_SOURCE_POLICY.items(), key=lambda item: item[0]
    ):
        section = getattr(analysis, section_name)
        for finding in getattr(section, field_name):
            if not analysis.is_current_verified(finding) or finding.evidence is None:
                warnings.append(
                    "Часть значимых для конкурентной проверки условий не имеет current evidence."
                )
                continue
            evidence = finding.evidence
            sources = tuple(
                source
                for source in analysis.provenance.sources
                if source.document_id == evidence.document_id
            )
            allowed_kinds = {kind.value for kind in _SECTION_KINDS[section_name]}
            if len(sources) != 1 or sources[0].document_kind not in allowed_kinds:
                warnings.append(
                    "Источник значимого для конкурентной проверки условия не прошёл scoped проверку."
                )
                continue
            ref = AiCompetitionSourceRef(section_name, field_name, evidence.citation_id)
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
        AiCompetitionStatus.PARTIAL
        if safe_warnings
        else AiCompetitionStatus.COMPLETE
        if items
        else AiCompetitionStatus.NO_VERIFIED_CONDITIONS
    )
    return AiCompetitionAssessment(
        status=status,
        policy_version=AI_COMPETITION_POLICY_VERSION,
        items=items,
        warnings=safe_warnings,
    )


def competition_source_findings(
    analysis: AiDocumentAnalysis,
    item: AiCompetitionItem,
) -> tuple[AiFinding, ...]:
    """Resolve an item back to current findings without trusting persisted references."""
    result: list[AiFinding] = []
    seen: set[tuple[str, str]] = set()
    for ref in item.source_refs:
        if COMPETITION_SOURCE_POLICY.get((ref.section, ref.field)) != item.category:
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
    category: AiCompetitionCategory,
    citation_id: str,
    refs: tuple[AiCompetitionSourceRef, ...],
) -> AiCompetitionItem:
    title, action = _PRESENTATION[category]
    canonical = json.dumps(
        {
            "category": category.value,
            "citation_ids": sorted({citation_id}),
            "policy_version": AI_COMPETITION_POLICY_VERSION,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    condition_id = "competition_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return AiCompetitionItem(
        condition_id=condition_id,
        category=category,
        review_priority=COMPETITION_CATEGORY_PRIORITIES[category],
        title=title,
        source_refs=refs,
        recommended_action=action,
    )


def _unavailable(warning: str) -> AiCompetitionAssessment:
    return AiCompetitionAssessment(
        status=AiCompetitionStatus.UNAVAILABLE,
        policy_version=AI_COMPETITION_POLICY_VERSION,
        warnings=(warning,),
    )


def _ref_sort_key(ref: AiCompetitionSourceRef) -> tuple[str, str, str]:
    return ref.section, ref.field, ref.citation_id


def _item_sort_key(item: AiCompetitionItem) -> tuple[object, ...]:
    return (
        _PRIORITY_ORDER[AiCompetitionReviewPriority(item.review_priority)],
        AiCompetitionCategory(item.category).value,
        tuple(ref.citation_id for ref in item.source_refs),
        item.condition_id,
    )


__all__ = [
    "AI_COMPETITION_POLICY_VERSION",
    "COMPETITION_CATEGORY_PRIORITIES",
    "COMPETITION_SOURCE_POLICY",
    "assess_competition_conditions",
    "competition_source_findings",
]
