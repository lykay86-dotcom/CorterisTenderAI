"""Single deterministic semantic classifier for tender documents."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
import re


class DocumentKind(StrEnum):
    TECHNICAL_SPECIFICATION = "technical_specification"
    DRAFT_CONTRACT = "draft_contract"
    PROCUREMENT_NOTICE = "procurement_notice"
    APPLICATION_REQUIREMENTS = "application_requirements"
    ESTIMATE = "estimate"
    APPLICATION_FORM = "application_form"
    INSTRUCTIONS = "instructions"
    OTHER = "other"


_DOCUMENT_KIND_RULES: tuple[tuple[DocumentKind, tuple[str, ...]], ...] = (
    (
        DocumentKind.TECHNICAL_SPECIFICATION,
        ("техническое задание", "техническая часть", "описание объекта закупки", "тз"),
    ),
    (DocumentKind.DRAFT_CONTRACT, ("проект контракта", "проект договора", "контракт", "договор")),
    (DocumentKind.PROCUREMENT_NOTICE, ("извещение", "информационная карта")),
    (DocumentKind.APPLICATION_REQUIREMENTS, ("требования к составу заявки", "требования к заявке")),
    (
        DocumentKind.ESTIMATE,
        ("смета", "локальный сметный расчет", "расчет нмцк", "обоснование нмцк"),
    ),
    (DocumentKind.APPLICATION_FORM, ("форма заявки", "форма предложения")),
    (DocumentKind.INSTRUCTIONS, ("инструкция участникам", "инструкция по заполнению")),
)


def classify_document_kind(source_name: str, text: str) -> DocumentKind:
    """Classify a document by safe display name and the first 3000 text characters."""
    name = _normalize(Path(source_name).stem)
    head = _normalize(text[:3000])
    best_kind = DocumentKind.OTHER
    best_score = 0
    for kind, terms in _DOCUMENT_KIND_RULES:
        score = 0
        for term in terms:
            normalized_term = _normalize(term)
            if _contains_phrase(name, normalized_term):
                score += 4
            elif _contains_phrase(head, normalized_term):
                score += 1
        if score > best_score:
            best_kind = kind
            best_score = score
    return best_kind


def _normalize(value: str) -> str:
    return " ".join(str(value or "").casefold().replace("ё", "е").split())


def _contains_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    return (
        re.search(
            rf"(?<![а-яa-z0-9]){re.escape(phrase)}(?![а-яa-z0-9])",
            text,
        )
        is not None
    )


__all__ = ["DocumentKind", "classify_document_kind"]
