"""Legacy public window boundary backed by the canonical tender page."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMainWindow

from app.ui.pages.tender_workspace_page import (
    LEGACY_PLATFORM_COMPATIBILITY_NOTICE,
    LEGACY_PLATFORM_CREDENTIAL_NOTICE,
    LEGACY_PLATFORM_PROVIDER_ACTION_TEXT,
    TenderWorkspacePage,
)

if TYPE_CHECKING:
    from app.core.ai.provider_selection import AiProviderSelectionService


class MainWindow(QMainWindow):
    """Compatibility shell around the reusable tender workspace page."""

    def __init__(
        self,
        *,
        ai_provider_selection_service: "AiProviderSelectionService | None" = None,
    ) -> None:
        super().__init__()
        self.setObjectName("LegacyMainWindowCompatibilityWrapper")
        self.setWindowTitle("AIBOS Security — Corteris Tender AI 1.2.1")
        self.resize(1480, 920)
        self.workspace_page = TenderWorkspacePage(
            ai_provider_selection_service=ai_provider_selection_service,
            status_bar=self.statusBar(),
            parent=self,
        )
        self.setCentralWidget(self.workspace_page)

    def __getattr__(self, name: str):
        """Delegate legacy attribute reads to the sole workspace instance."""
        try:
            page = object.__getattribute__(self, "workspace_page")
        except AttributeError:
            raise AttributeError(name) from None
        return getattr(page, name)


__all__ = [
    "LEGACY_PLATFORM_COMPATIBILITY_NOTICE",
    "LEGACY_PLATFORM_CREDENTIAL_NOTICE",
    "LEGACY_PLATFORM_PROVIDER_ACTION_TEXT",
    "MainWindow",
    "TenderWorkspacePage",
]
