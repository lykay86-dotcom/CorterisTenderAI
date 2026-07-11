"""Tests for the requirement-analysis dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.requirement_analysis import (
    FindingSeverity,
    TenderAnalysisSource,
    TenderRequirementsAnalyzer,
)
from app.ui.tender_requirement_analysis_dialog import (
    TenderRequirementAnalysisDialog,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _analysis():
    return TenderRequirementsAnalyzer().analyze(
        "procurement:001",
        (
            TenderAnalysisSource(
                document_key="tz",
                source_name="Техническое задание.docx",
                text=(
                    "Техническое задание. Требуется лицензия МЧС. "
                    "Обеспечение исполнения контракта 10%. "
                    "Срок выполнения работ 30 календарных дней."
                ),
            ),
            TenderAnalysisSource(
                document_key="contract",
                source_name="Проект контракта.docx",
                text=(
                    "Проект контракта. Оплата в течение 7 рабочих дней. "
                    "За просрочку начисляется пеня."
                ),
            ),
        ),
    )


def test_dialog_displays_analysis_metrics_and_findings() -> None:
    app = _app()
    analysis = _analysis()
    dialog = TenderRequirementAnalysisDialog(
        analysis.registry_key,
        analysis=analysis,
    )

    assert dialog.analysis is analysis
    assert dialog.documents_metric.text() == "2"
    assert dialog.findings_metric.text() == str(len(analysis.findings))
    assert dialog.findings_table.rowCount() == len(analysis.findings)
    assert dialog.selected_finding() is not None
    assert "Фрагмент документа" in dialog.finding_details.toHtml()
    app.processEvents()


def test_dialog_filters_critical_findings() -> None:
    app = _app()
    analysis = TenderRequirementsAnalyzer().analyze(
        "procurement:002",
        (
            TenderAnalysisSource(
                document_key="tz",
                source_name="ТЗ.txt",
                text="Работы связаны с государственной тайной.",
            ),
        ),
    )
    dialog = TenderRequirementAnalysisDialog(
        analysis.registry_key,
        analysis=analysis,
    )
    index = dialog.severity_combo.findData(
        FindingSeverity.CRITICAL.value
    )
    dialog.severity_combo.setCurrentIndex(index)

    assert dialog.visible_findings
    assert all(
        item.severity == FindingSeverity.CRITICAL
        for item in dialog.visible_findings
    )
    app.processEvents()


def test_dialog_emits_normal_and_force_analysis_requests() -> None:
    app = _app()
    dialog = TenderRequirementAnalysisDialog("procurement:003")
    requests: list[tuple[str, bool]] = []
    dialog.analysis_requested.connect(
        lambda key, force: requests.append((key, force))
    )

    dialog.run_button.click()
    dialog.force_button.click()

    assert requests == [
        ("procurement:003", False),
        ("procurement:003", True),
    ]
    app.processEvents()


def test_busy_state_disables_analysis_actions() -> None:
    app = _app()
    dialog = TenderRequirementAnalysisDialog("procurement:004")

    dialog.set_analysis_busy(True)

    assert dialog.analysis_busy
    assert not dialog.run_button.isEnabled()
    assert not dialog.force_button.isEnabled()
    app.processEvents()
