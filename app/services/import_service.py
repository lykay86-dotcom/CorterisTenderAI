from __future__ import annotations

import shutil
from decimal import Decimal
from pathlib import Path

from app.config.settings import get_settings
from app.parsers.documents import SUPPORTED, classify_document, parse_document
from app.repositories.tenders import TenderRepository
from app.tenders.safe_archive import SafeArchiveExtractor
from app.tenders.models import normalize_money_amount


class ImportService:
    """Manual import with safe archive extraction and legacy compatibility."""

    def __init__(self, archive_extractor: SafeArchiveExtractor | None = None):
        self.repo = TenderRepository()
        self.archive_extractor = archive_extractor or SafeArchiveExtractor()

    def create_tender(
        self,
        title: str,
        number: str = "",
        url: str = "",
        nmck: Decimal | str | int | float = Decimal("0"),
    ) -> int:
        amount = normalize_money_amount(nmck, field_name="nmck")
        return self.repo.create(
            title=title,
            number=number,
            source_url=url,
            nmck=amount,
        ).id

    def import_path(self, tender_id: int, source: Path) -> list[str]:
        source = Path(source).expanduser()
        base = get_settings().data_dir / "projects" / str(tender_id)
        base.mkdir(parents=True, exist_ok=True)

        if source.suffix.casefold() == ".zip":
            self.archive_extractor.extract_many((source,), base)
        elif source.is_dir():
            shutil.copytree(source, base, dirs_exist_ok=True)
        else:
            shutil.copy2(source, base / source.name)

        imported: list[str] = []
        existing_paths = {str(item.path).casefold() for item in self.repo.documents(tender_id)}
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.casefold() not in SUPPORTED:
                continue
            if str(path).casefold() in existing_paths:
                continue
            text, pages = parse_document(path)
            kind = classify_document(path.name, text)
            self.repo.add_document(
                tender_id,
                name=path.name,
                path=str(path),
                kind=kind,
                text=text,
                page_count=pages,
            )
            existing_paths.add(str(path).casefold())
            imported.append(path.name)
        return imported
