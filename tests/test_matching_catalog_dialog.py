from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.matching_catalog import MatchingCatalogRepository
from app.ui.matching_catalog_dialog import MatchingCatalogDialog


def _app():
    return QApplication.instance() or QApplication([])


def test_dialog_loads_catalog_and_can_add_remove_row(tmp_path) -> None:
    app = _app()
    dialog = MatchingCatalogDialog(MatchingCatalogRepository(tmp_path / "registry.sqlite3"))
    dialog.load_catalog()
    original = dialog.table.rowCount()

    dialog.add_empty_row()
    dialog.table.selectRow(dialog.table.rowCount() - 1)
    dialog.remove_selected_rows()

    assert original > 0
    assert dialog.table.rowCount() == original
    app.processEvents()
