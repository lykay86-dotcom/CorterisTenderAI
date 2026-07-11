"""Regression tests for Excel header range normalization."""

from __future__ import annotations

from openpyxl import Workbook

from app.reporting.workflow_excel import WorkflowExcelExporter


def test_style_header_accepts_entire_worksheet_row() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["A", "B", "C"])

    exporter = WorkflowExcelExporter()
    exporter._style_header(sheet["1:1"])

    assert sheet["A1"].font.bold
    assert sheet["B1"].font.bold
    assert sheet["C1"].font.bold


def test_style_header_accepts_rectangular_cell_range() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "A"
    sheet["B1"] = "B"

    exporter = WorkflowExcelExporter()
    exporter._style_header(sheet["A1:B1"])

    assert sheet["A1"].font.bold
    assert sheet["B1"].font.bold
    assert sheet["A1"].fill.fill_type == "solid"
    assert sheet["B1"].fill.fill_type == "solid"
