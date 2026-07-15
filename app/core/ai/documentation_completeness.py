"""Pure deterministic assessment of the locally known documentation package."""

from __future__ import annotations

import hashlib
import json

from app.core.ai.schemas import (
    AiDocumentAnalysis,
    AiDocumentationCompletenessAssessment,
    AiDocumentationCompletenessStatus,
    AiDocumentationDocumentSnapshot,
    AiDocumentationIssue,
    AiDocumentationIssueCode,
    AiDocumentationScope,
)
from app.core.document_classification import (
    APPLICATION_REQUIREMENTS_SOURCE_KINDS,
    DocumentKind,
)


AI_DOCUMENTATION_COMPLETENESS_POLICY_VERSION = "1"
AI_DOCUMENTATION_COMPLETENESS_DISCLAIMER = (
    "Оценка отражает полноту локально известного комплекта и его пригодность для текущего "
    "анализа CorterisTenderAI. Она не подтверждает юридическую полноту документации закупки и "
    "не гарантирует, что площадка опубликовала все обязательные материалы."
)

_INFORMATIONAL_CODES = frozenset(
    {
        AiDocumentationIssueCode.DUPLICATE_CONTENT,
        AiDocumentationIssueCode.UNCLASSIFIED_DOCUMENT,
    }
)

_PRESENTATION = {
    AiDocumentationIssueCode.DOWNLOAD_FAILED: (
        "Документ недоступен локально",
        "Повторить загрузку документа и проверить его наличие в локальном хранилище.",
    ),
    AiDocumentationIssueCode.EXTRACTION_FAILED: (
        "Не удалось извлечь текст документа",
        "Повторить извлечение текста или проверить документ вручную.",
    ),
    AiDocumentationIssueCode.EXTRACTION_PARTIAL: (
        "Текст документа извлечён частично",
        "Проверить предупреждения извлечения и недостающие фрагменты документа вручную.",
    ),
    AiDocumentationIssueCode.UNSUPPORTED_FORMAT: (
        "Формат документа не поддерживается",
        "Преобразовать документ в поддерживаемый формат или проверить его вручную.",
    ),
    AiDocumentationIssueCode.EMPTY_TEXT: (
        "Извлечённый текст документа отсутствует",
        "Проверить наличие текстового слоя и при необходимости подготовить читаемую копию.",
    ),
    AiDocumentationIssueCode.CONTEXT_TRUNCATED: (
        "Документ усечён в текущем контексте",
        "Проверить не включённую в контекст часть документа вручную.",
    ),
    AiDocumentationIssueCode.CONTEXT_OMITTED: (
        "Документ не включён в текущий контекст",
        "Увеличить доступный безопасный лимит или проверить документ отдельно.",
    ),
    AiDocumentationIssueCode.REQUIRED_ANALYSIS_SCOPE_NOT_FOUND: (
        "Область текущего анализа не представлена",
        "Добавить локально доступный документ соответствующей области или подтвердить её вручную.",
    ),
    AiDocumentationIssueCode.INVENTORY_MISMATCH: (
        "Локальный состав документов не согласован с контекстом",
        "Повторно сформировать контекст из текущего локального хранилища.",
    ),
    AiDocumentationIssueCode.DUPLICATE_CONTENT: (
        "Обнаружены документы с одинаковым содержимым",
        "Проверить, что в анализ включена актуальная рабочая копия документа.",
    ),
    AiDocumentationIssueCode.UNCLASSIFIED_DOCUMENT: (
        "Тип документа не определён",
        "Проверить назначение документа вручную; это не означает отсутствие обязательного файла.",
    ),
}


def assess_documentation_completeness(
    analysis: AiDocumentAnalysis,
) -> AiDocumentationCompletenessAssessment:
    inventory = tuple(analysis.documentation_inventory)
    if not inventory:
        return AiDocumentationCompletenessAssessment(
            status=AiDocumentationCompletenessStatus.NO_DOCUMENTS,
            policy_version=AI_DOCUMENTATION_COMPLETENESS_POLICY_VERSION,
        )

    issues: dict[tuple[object, ...], AiDocumentationIssue] = {}
    checksum_groups = _checksum_groups(inventory)
    duplicate_checksums = {
        checksum for checksum, documents in checksum_groups.items() if len(documents) > 1
    }
    covered_duplicate_checksums = {
        checksum
        for checksum in duplicate_checksums
        if any(item.included_in_context for item in checksum_groups[checksum])
    }

    for checksum in sorted(duplicate_checksums):
        documents = checksum_groups[checksum]
        _add_issue(
            issues,
            AiDocumentationIssueCode.DUPLICATE_CONTENT,
            AiDocumentationScope.PACKAGE,
            tuple(item.document_id for item in documents),
        )

    unclassified = tuple(
        item.document_id for item in inventory if item.document_kind is DocumentKind.OTHER
    )
    if unclassified:
        _add_issue(
            issues,
            AiDocumentationIssueCode.UNCLASSIFIED_DOCUMENT,
            AiDocumentationScope.OTHER,
            unclassified,
        )

    for document in inventory:
        scope = _scope_for_kind(DocumentKind(document.document_kind))
        download_failed = document.download_status == "failed" or (
            document.origin == "catalog" and not document.available_locally
        )
        if download_failed:
            _add_issue(
                issues,
                AiDocumentationIssueCode.DOWNLOAD_FAILED,
                scope,
                (document.document_id,),
            )
        if document.extraction_status == "failed":
            _add_issue(
                issues,
                AiDocumentationIssueCode.EXTRACTION_FAILED,
                scope,
                (document.document_id,),
            )
        elif document.extraction_status == "unsupported":
            _add_issue(
                issues,
                AiDocumentationIssueCode.UNSUPPORTED_FORMAT,
                scope,
                (document.document_id,),
            )
        elif document.extraction_status == "partial":
            _add_issue(
                issues,
                AiDocumentationIssueCode.EXTRACTION_PARTIAL,
                scope,
                (document.document_id,),
            )

        extraction_can_contain_text = document.extraction_status not in {
            "failed",
            "unsupported",
        }
        if (
            document.available_locally
            and extraction_can_contain_text
            and not document.text_available
        ):
            _add_issue(
                issues,
                AiDocumentationIssueCode.EMPTY_TEXT,
                scope,
                (document.document_id,),
            )
        if document.context_truncated:
            _add_issue(
                issues,
                AiDocumentationIssueCode.CONTEXT_TRUNCATED,
                scope,
                (document.document_id,),
            )
        duplicate_is_covered = (
            bool(document.checksum_sha256)
            and document.checksum_sha256 in covered_duplicate_checksums
        )
        if (
            document.text_available
            and not document.included_in_context
            and not duplicate_is_covered
        ):
            _add_issue(
                issues,
                AiDocumentationIssueCode.CONTEXT_OMITTED,
                scope,
                (document.document_id,),
            )

    kinds = {DocumentKind(item.document_kind) for item in inventory}
    if DocumentKind.TECHNICAL_SPECIFICATION not in kinds:
        _add_issue(
            issues,
            AiDocumentationIssueCode.REQUIRED_ANALYSIS_SCOPE_NOT_FOUND,
            AiDocumentationScope.TECHNICAL_SPECIFICATION,
            (),
        )
    if not kinds.intersection(APPLICATION_REQUIREMENTS_SOURCE_KINDS):
        _add_issue(
            issues,
            AiDocumentationIssueCode.REQUIRED_ANALYSIS_SCOPE_NOT_FOUND,
            AiDocumentationScope.APPLICATION_REQUIREMENTS,
            (),
        )

    if not _scoped_inventory_matches(analysis, inventory):
        _add_issue(
            issues,
            AiDocumentationIssueCode.INVENTORY_MISMATCH,
            AiDocumentationScope.PACKAGE,
            (),
        )

    ordered = tuple(issues.values())
    has_blocking = any(item.code not in _INFORMATIONAL_CODES for item in ordered)
    return AiDocumentationCompletenessAssessment(
        status=(
            AiDocumentationCompletenessStatus.PARTIAL
            if has_blocking
            else AiDocumentationCompletenessStatus.COMPLETE
        ),
        policy_version=AI_DOCUMENTATION_COMPLETENESS_POLICY_VERSION,
        known_document_count=len(inventory),
        locally_available_count=sum(item.available_locally for item in inventory),
        text_available_count=sum(item.text_available for item in inventory),
        included_document_count=sum(item.included_in_context for item in inventory),
        issues=ordered,
    )


def _checksum_groups(
    inventory: tuple[AiDocumentationDocumentSnapshot, ...],
) -> dict[str, tuple[AiDocumentationDocumentSnapshot, ...]]:
    grouped: dict[str, list[AiDocumentationDocumentSnapshot]] = {}
    for item in inventory:
        if item.checksum_sha256:
            grouped.setdefault(item.checksum_sha256, []).append(item)
    return {
        checksum: tuple(sorted(items, key=lambda item: item.document_id.casefold()))
        for checksum, items in grouped.items()
    }


def _scope_for_kind(kind: DocumentKind) -> AiDocumentationScope:
    mapping = {
        DocumentKind.TECHNICAL_SPECIFICATION: AiDocumentationScope.TECHNICAL_SPECIFICATION,
        DocumentKind.DRAFT_CONTRACT: AiDocumentationScope.DRAFT_CONTRACT,
        DocumentKind.PROCUREMENT_NOTICE: AiDocumentationScope.PROCUREMENT_NOTICE,
        DocumentKind.APPLICATION_REQUIREMENTS: AiDocumentationScope.APPLICATION_REQUIREMENTS,
        DocumentKind.ESTIMATE: AiDocumentationScope.ESTIMATE,
        DocumentKind.APPLICATION_FORM: AiDocumentationScope.APPLICATION_FORM,
        DocumentKind.INSTRUCTIONS: AiDocumentationScope.INSTRUCTIONS,
        DocumentKind.OTHER: AiDocumentationScope.OTHER,
    }
    return mapping[kind]


def _scoped_inventory_matches(
    analysis: AiDocumentAnalysis,
    inventory: tuple[AiDocumentationDocumentSnapshot, ...],
) -> bool:
    scoped = (
        (
            analysis.technical_specification,
            frozenset({DocumentKind.TECHNICAL_SPECIFICATION}),
        ),
        (analysis.requirements, APPLICATION_REQUIREMENTS_SOURCE_KINDS),
        (analysis.draft_contract, frozenset({DocumentKind.DRAFT_CONTRACT})),
    )
    for section, allowed_kinds in scoped:
        found = tuple(
            sorted(
                (
                    item.document_id
                    for item in inventory
                    if DocumentKind(item.document_kind) in allowed_kinds
                ),
                key=str.casefold,
            )
        )
        included = tuple(
            item.document_id
            for item in inventory
            if DocumentKind(item.document_kind) in allowed_kinds and item.included_in_context
        )
        if tuple(section.document_ids) != found or tuple(section.included_document_ids) != included:
            return False
    return True


def _add_issue(
    issues: dict[tuple[object, ...], AiDocumentationIssue],
    code: AiDocumentationIssueCode,
    scope: AiDocumentationScope,
    document_ids: tuple[str, ...],
) -> None:
    normalized_ids = tuple(sorted(set(document_ids), key=str.casefold))
    key = (code.value, scope.value, normalized_ids)
    if key in issues:
        return
    canonical = json.dumps(
        {
            "document_ids": normalized_ids,
            "issue_code": code.value,
            "policy_version": AI_DOCUMENTATION_COMPLETENESS_POLICY_VERSION,
            "scope": scope.value,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    issue_id = "documentation_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    title, action = _PRESENTATION[code]
    issues[key] = AiDocumentationIssue(
        issue_id=issue_id,
        code=code,
        scope=scope,
        document_ids=normalized_ids,
        title=title,
        recommended_action=action,
    )


__all__ = [
    "AI_DOCUMENTATION_COMPLETENESS_DISCLAIMER",
    "AI_DOCUMENTATION_COMPLETENESS_POLICY_VERSION",
    "assess_documentation_completeness",
]
