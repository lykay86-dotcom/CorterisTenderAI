"""Tests for the packaged workflow Excel template service."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from app.reporting.workflow_excel_template import (
    WorkflowExcelTemplateService,
)


def _sheet_names(path: Path) -> list[str]:
    namespace = {
        "main": (
            "http://schemas.openxmlformats.org/"
            "spreadsheetml/2006/main"
        )
    }
    with ZipFile(path) as archive:
        root = ET.fromstring(
            archive.read("xl/workbook.xml")
        )
    return [
        item.attrib["name"]
        for item in root.findall(
            "main:sheets/main:sheet",
            namespace,
        )
    ]


def test_template_service_copies_packaged_xlsx(tmp_path) -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "workflow"
        / WorkflowExcelTemplateService.DEFAULT_FILENAME
    )
    service = WorkflowExcelTemplateService(source)
    target = tmp_path / "mass-import"

    result = service.copy_to(target)

    assert result.path.suffix == ".xlsx"
    assert result.path.exists()
    assert result.size_bytes > 5000
    assert _sheet_names(result.path) == [
        "Импорт",
        "Инструкция",
        "Пример",
        "Справочники",
    ]


def test_template_contains_dropdown_validations() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "workflow"
        / WorkflowExcelTemplateService.DEFAULT_FILENAME
    )

    with ZipFile(source) as archive:
        import_sheet = archive.read(
            "xl/worksheets/sheet1.xml"
        ).decode("utf-8")

    assert "dataValidations" in import_sheet
    assert "B2:B501" in import_sheet
    assert "E2:E501" in import_sheet
    assert "K2:K501" in import_sheet
    assert "Справочники" in import_sheet


def test_template_has_validation_formula_column() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "workflow"
        / WorkflowExcelTemplateService.DEFAULT_FILENAME
    )

    with ZipFile(source) as archive:
        import_sheet = archive.read(
            "xl/worksheets/sheet1.xml"
        ).decode("utf-8")

    assert "COUNTIFS" in import_sheet
    assert 'r="L2"' in import_sheet
