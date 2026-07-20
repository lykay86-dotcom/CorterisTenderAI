"""Build a privacy-safe offscreen inventory of the RM-152 Qt shell."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build_runtime_inventory() -> dict[str, int]:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtWidgets import QApplication, QLabel, QWidget

    from app.config.user_settings import UserPreferences
    from app.repositories.business_metrics import BusinessMetricsRepository
    from app.ui.modern_main_window import ModernMainWindow

    class SyntheticTenderRepository:
        def list(self) -> list[object]:
            return []

    class SyntheticSettingsStore:
        def load(self) -> UserPreferences:
            return UserPreferences()

    class SyntheticPriceCatalog:
        def __init__(self, _path: object) -> None:
            pass

        def search(self, _query: str, _limit: int) -> list[object]:
            return []

    class SyntheticPriceOfferRepository:
        def __init__(self, _path: object) -> None:
            self.offers: list[object] = []

        def load(self) -> list[object]:
            return []

    application = QApplication.instance() or QApplication([])
    with TemporaryDirectory(prefix="rm152-runtime-") as temporary:
        temporary_root = Path(temporary)
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            str(temporary_root / "settings"),
        )
        with (
            patch(
                "app.ui.modern_main_window.BusinessMetricsRepository",
                return_value=BusinessMetricsRepository(temporary_root / "business.json"),
            ),
            patch(
                "app.ui.pages.business_workflow_page.SystemHealthMonitor.request_refresh",
                return_value=False,
            ),
            patch(
                "app.ui.pages.business_workflow_page.BusinessWorkflowPage._initialize_database_safety"
            ),
            patch(
                "app.ui.pages.business_workflow_page.BusinessWorkflowPage._check_automatic_backup"
            ),
            patch(
                "app.ui.pages.tender_workspace_page.TenderRepository",
                SyntheticTenderRepository,
            ),
            patch(
                "app.ui.pages.tender_workspace_page.UserSettingsStore",
                SyntheticSettingsStore,
            ),
            patch(
                "app.ui.pages.tender_workspace_page.PriceCatalog",
                SyntheticPriceCatalog,
            ),
            patch(
                "app.ui.pages.tender_workspace_page.PriceOfferRepository",
                SyntheticPriceOfferRepository,
            ),
            patch("app.ui.pages.tender_workspace_page.AiProviderSettingsWidget.load"),
            patch("app.ui.modern_main_window.DashboardController.start"),
        ):
            window = ModernMainWindow()
            window.show()
            application.processEvents()
            widgets = (window, *window.findChildren(QWidget))
            focusable = tuple(
                widget for widget in widgets if widget.focusPolicy() != Qt.FocusPolicy.NoFocus
            )
            labels = tuple(widget for widget in widgets if isinstance(widget, QLabel))
            result = {
                "widgets": len(widgets),
                "focusable": len(focusable),
                "focusable_with_object_name": sum(
                    bool(widget.objectName().strip()) for widget in focusable
                ),
                "accessible_names": sum(
                    bool(widget.accessibleName().strip()) for widget in widgets
                ),
                "accessible_descriptions": sum(
                    bool(widget.accessibleDescription().strip()) for widget in widgets
                ),
                "labels": len(labels),
                "label_buddy_relations": sum(label.buddy() is not None for label in labels),
            }
            window.close()
            window.deleteLater()
            application.processEvents()
    return result


def main() -> int:
    print(json.dumps(build_runtime_inventory(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
