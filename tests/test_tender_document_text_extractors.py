"""Tests for DOCX, XLSX, TXT, ZIP and PDF text extraction."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from app.tenders.document_text_extractor import (
    TenderDocumentTextExtractor,
    TextExtractionStatus,
)


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def test_extracts_cp1251_txt() -> None:
    extractor = TenderDocumentTextExtractor()

    result = extractor.extract_bytes(
        "Техническое задание\nМонтаж СКУД".encode("cp1251"),
        source_name="ТЗ.txt",
    )

    assert result.status == TextExtractionStatus.EXTRACTED
    assert "Монтаж СКУД" in result.text


def test_extracts_docx_paragraphs() -> None:
    document_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>Техническое задание</w:t></w:r></w:p>
        <w:p><w:r><w:t>Поставка 12 камер</w:t></w:r></w:p>
      </w:body>
    </w:document>""".encode("utf-8")
    payload = _zip_bytes({"word/document.xml": document_xml})

    result = TenderDocumentTextExtractor().extract_bytes(
        payload,
        source_name="ТЗ.docx",
    )

    assert result.status == TextExtractionStatus.EXTRACTED
    assert "Техническое задание" in result.text
    assert "Поставка 12 камер" in result.text


def test_extracts_xlsx_shared_strings_and_numbers() -> None:
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
    <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
      xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
      <sheets><sheet name="Смета" sheetId="1" r:id="rId1"/></sheets>
    </workbook>""".encode("utf-8")
    rels = """<?xml version="1.0" encoding="UTF-8"?>
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
      <Relationship Id="rId1" Target="worksheets/sheet1.xml"
        Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>
    </Relationships>""".encode("utf-8")
    shared = """<?xml version="1.0" encoding="UTF-8"?>
    <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <si><t>Камера</t></si><si><t>Количество</t></si>
    </sst>""".encode("utf-8")
    sheet = """<?xml version="1.0" encoding="UTF-8"?>
    <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <sheetData>
        <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>
        <row r="2"><c r="A2" t="inlineStr"><is><t>TRASSIR</t></is></c><c r="B2"><v>12</v></c></row>
      </sheetData>
    </worksheet>""".encode("utf-8")
    payload = _zip_bytes(
        {
            "xl/workbook.xml": workbook,
            "xl/_rels/workbook.xml.rels": rels,
            "xl/sharedStrings.xml": shared,
            "xl/worksheets/sheet1.xml": sheet,
        }
    )

    result = TenderDocumentTextExtractor().extract_bytes(
        payload,
        source_name="Смета.xlsx",
    )

    assert result.status == TextExtractionStatus.EXTRACTED
    assert "Лист: Смета" in result.text
    assert "Камера\tКоличество" in result.text
    assert "TRASSIR\t12" in result.text


def test_extracts_supported_files_from_zip_and_blocks_traversal() -> None:
    payload = _zip_bytes(
        {
            "docs/readme.txt": "Проект договора".encode("utf-8"),
            "../outside.txt": "Нельзя".encode("utf-8"),
            "image.jpg": b"binary",
        }
    )

    result = TenderDocumentTextExtractor().extract_bytes(
        payload,
        source_name="Документы.zip",
    )

    assert result.status == TextExtractionStatus.PARTIAL
    assert "Проект договора" in result.text
    assert "Нельзя" not in result.text
    assert any("небезопасный путь" in item for item in result.warnings)


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakeReader:
    is_encrypted = False

    def __init__(self, stream) -> None:
        del stream
        self.pages = (
            _FakePage("Первая страница"),
            _FakePage("Вторая страница"),
        )


def test_pdf_reader_can_be_injected_without_real_dependency() -> None:
    extractor = TenderDocumentTextExtractor(pdf_reader_factory=_FakeReader)

    result = extractor.extract_bytes(
        b"%PDF-1.4 fake",
        source_name="contract.pdf",
    )

    assert result.status == TextExtractionStatus.EXTRACTED
    assert "Первая страница" in result.text
    assert "Вторая страница" in result.text
