"""Tests for tender requirement analysis rules."""

from __future__ import annotations

import pytest

from app.core.document_classification import classify_document_kind
from app.tenders.requirement_analysis import (
    AnalysisRiskLevel,
    DocumentKind,
    FindingSeverity,
    RequirementCategory,
    TenderAnalysisSource,
    TenderRequirementsAnalyzer,
)


@pytest.mark.parametrize(
    ("source_name", "text"),
    [
        ("Проект договора.pdf", ""),
        ("Проект контракта.docx", ""),
        ("Проект государственного контракта.pdf", ""),
        ("Приложение.pdf", "ПРОЕКТ ДОГОВОРА"),
        (
            "Документ.pdf",
            "Предмет договора. Права и обязанности сторон. Порядок расчётов. "
            "Ответственность сторон. Реквизиты сторон.",
        ),
    ],
)
def test_draft_contract_classifier_positive_cases(source_name: str, text: str) -> None:
    assert classify_document_kind(source_name, text) is DocumentKind.DRAFT_CONTRACT


@pytest.mark.parametrize(
    ("source_name", "text", "expected"),
    [
        ("Требования к опыту.pdf", "Не менее двух исполненных договоров.", DocumentKind.OTHER),
        ("Извещение.pdf", "Порядок заключения контракта.", DocumentKind.PROCUREMENT_NOTICE),
        (
            "Инструкция участникам.pdf",
            "Обеспечение исполнения контракта предоставляется победителем.",
            DocumentKind.INSTRUCTIONS,
        ),
        (
            "Техническое задание.pdf",
            "Работы выполняются по договору.",
            DocumentKind.TECHNICAL_SPECIFICATION,
        ),
        ("Форма заявки.pdf", "Согласие заключить будущий контракт.", DocumentKind.APPLICATION_FORM),
        (
            "Расчёт НМЦК.pdf",
            "Расчёт выполнен по договорам-аналогам.",
            DocumentKind.ESTIMATE,
        ),
        (
            "Приложение к договору — Техническое задание.pdf",
            "Предмет договора указан в техническом задании.",
            DocumentKind.TECHNICAL_SPECIFICATION,
        ),
        (
            "Справка.pdf",
            "Предмет договора упомянут без структуры проекта договора.",
            DocumentKind.OTHER,
        ),
    ],
)
def test_draft_contract_classifier_rejects_false_positives_and_preserves_ts_priority(
    source_name: str,
    text: str,
    expected: DocumentKind,
) -> None:
    assert classify_document_kind(source_name, text) is expected


def source(name: str, text: str, key: str = "doc") -> TenderAnalysisSource:
    return TenderAnalysisSource(
        document_key=key,
        source_name=name,
        text=text,
    )


def test_analyzer_detects_core_requirements() -> None:
    analysis = TenderRequirementsAnalyzer().analyze(
        "procurement:001",
        (
            source(
                "Техническое задание.docx",
                """
                Техническое задание.
                Для выполнения работ требуется лицензия МЧС.
                Участник подтверждает опыт исполнения не менее
                2 контрактов за последние 3 года.
                Обеспечение исполнения контракта составляет 10%.
                Срок выполнения работ — 30 календарных дней.
                Гарантийный срок — 24 месяца.
                """,
                "tz",
            ),
            source(
                "Проект контракта.docx",
                """
                Проект контракта.
                Оплата производится в течение 7 рабочих дней.
                За нарушение сроков начисляется пеня и штраф.
                Заказчик вправе принять решение об одностороннем
                отказе от исполнения контракта.
                """,
                "contract",
            ),
        ),
    )

    assert {item.kind for item in analysis.documents} == {
        DocumentKind.TECHNICAL_SPECIFICATION,
        DocumentKind.DRAFT_CONTRACT,
    }
    assert analysis.missing_documents == ()
    assert analysis.license_requirements
    assert analysis.experience_requirements
    assert analysis.security_requirements
    assert analysis.deadlines
    assert analysis.contract_risks
    assert analysis.risk_level in {
        AnalysisRiskLevel.MEDIUM,
        AnalysisRiskLevel.HIGH,
    }


def test_analyzer_reports_missing_core_documents() -> None:
    analysis = TenderRequirementsAnalyzer().analyze(
        "procurement:002",
        (
            source(
                "Извещение.txt",
                "Извещение о проведении электронного аукциона.",
            ),
        ),
    )

    assert len(analysis.missing_documents) == 2
    assert any("Техническое задание" in item for item in analysis.missing_documents)
    assert any("Проект контракта" in item for item in analysis.missing_documents)


def test_analyzer_marks_state_secret_as_critical_stop_factor() -> None:
    analysis = TenderRequirementsAnalyzer().analyze(
        "procurement:003",
        (
            source(
                "ТЗ.txt",
                ("Работы связаны со сведениями, составляющими государственную тайну."),
            ),
        ),
    )

    assert len(analysis.stop_factors) == 1
    assert analysis.stop_factors[0].severity == (FindingSeverity.CRITICAL)
    assert analysis.risk_level == AnalysisRiskLevel.HIGH


def test_analyzer_detects_mandatory_sro_as_stop_factor() -> None:
    analysis = TenderRequirementsAnalyzer().analyze(
        "procurement:004",
        (
            source(
                "Требования к заявке.txt",
                (
                    "Участник должен иметь обязательное членство "
                    "в СРО и предоставить выписку из реестра СРО."
                ),
            ),
        ),
    )

    assert analysis.findings_for(RequirementCategory.LICENSE)
    assert analysis.stop_factors
    assert any(item.pattern_key == "mandatory_sro" for item in analysis.stop_factors)


def test_duplicate_requirement_is_collapsed_per_source() -> None:
    analysis = TenderRequirementsAnalyzer().analyze(
        "procurement:005",
        (
            source(
                "Контракт.txt",
                ("Обеспечение исполнения контракта 10%. Обеспечение исполнения контракта 10%."),
            ),
        ),
    )

    requirements = analysis.security_requirements
    assert len(requirements) == 1
    assert requirements[0].value == "10%"
