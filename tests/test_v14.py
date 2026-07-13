from pathlib import Path

from app.ai.structured_analysis import _extract_json, validate_citations
from app.connectors.eis import parse_eis_reference
from app.equipment.catalog import EquipmentCatalog, EquipmentItem
from app.equipment.matcher import match_equipment
from app.services.backup import BackupService
from app.services.application_check import check_package


def test_eis_number_and_url():
    number = "0123456789012345678"
    assert parse_eis_reference(number).purchase_number == number
    url = f"https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber={number}"
    assert parse_eis_reference(url).purchase_number == number


def test_structured_json_and_citations():
    payload = _extract_json(
        '```json\n{"risks":[{"source":{"source_document":"ТЗ.pdf","quote":"срок 1 день"}}]}\n```'
    )
    assert validate_citations(payload) == []
    payload["risks"][0]["source"]["quote"] = ""
    assert validate_citations(payload)


def test_equipment_catalog_and_match(tmp_path: Path):
    catalog = EquipmentCatalog(tmp_path / "equipment.json")
    catalog.upsert(
        EquipmentItem(
            category="Камеры",
            brand="Test",
            model="Cam-4MP",
            purchase_price=10000,
            characteristics={"resolution": "4 MP"},
        )
    )
    reloaded = EquipmentCatalog(tmp_path / "equipment.json")
    assert len(reloaded.items) == 1
    matches = match_equipment(
        {"name": "Test Cam-4MP", "characteristics": {"resolution": "4 MP"}}, reloaded.items
    )
    assert matches[0].compliant is True


def test_backup(tmp_path: Path):
    source = tmp_path / "data"
    source.mkdir()
    (source / "a.txt").write_text("ok", encoding="utf-8")
    service = BackupService()
    output = service.create(tmp_path / "backup", [source], {"version": "1.4"})
    assert output.exists() and service.verify(output)


def test_package_check(tmp_path: Path):
    from docx import Document

    path = tmp_path / "КП.docx"
    doc = Document()
    doc.add_paragraph("Коммерческое предложение")
    doc.save(path)
    result = check_package([path])
    assert result["ready"] is True
