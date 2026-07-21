"""RM-127 contract for one reusable tender workspace widget."""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QStatusBar

from app.config.user_settings import UserPreferences
from app.ui.pages.tender_workspace_page import TenderWorkspacePage


TOP_LEVEL_KEYS = (
    "overview",
    "analysis",
    "estimate",
    "catalog",
    "readiness",
    "tools",
    "price_monitor",
    "settings",
)
TOP_LEVEL_LABELS = (
    "Панель управления",
    "Анализ тендера",
    "Смета",
    "Оборудование и бренды",
    "Проверка заявки",
    "Инструменты 1.4",
    "Мониторинг цен 1.5",
    "Настройки",
)
SETTINGS_KEYS = (
    "platforms",
    "ai",
    "company",
    "economics",
    "templates",
    "database",
)
SETTINGS_LABELS = (
    "Площадки API/RSS/FTP",
    "ChatGPT / ИИ",
    "Компания и реквизиты",
    "Лицензии и экономика",
    "Фирменные бланки",
    "Диагностика БД",
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _TenderRepository:
    def __init__(self) -> None:
        self.items = [
            SimpleNamespace(
                id="tender-7",
                number="0373100000126000007",
                title="Монтаж видеонаблюдения",
                nmck=1_500_000,
                score=88,
                recommendation="Участвовать",
            )
        ]

    def list(self):
        return list(self.items)


class _SettingsStore:
    def load(self) -> UserPreferences:
        return UserPreferences()


class _PriceCatalog:
    def search(self, _query: str, _limit: int):
        return []


class _PriceOfferRepository:
    def __init__(self, _path) -> None:
        self.offers = []

    def load(self):
        return []


def _isolate_page_dependencies(monkeypatch) -> None:
    module = "app.ui.pages.tender_workspace_page"
    monkeypatch.setattr(f"{module}.TenderRepository", _TenderRepository)
    monkeypatch.setattr(f"{module}.UserSettingsStore", _SettingsStore)
    monkeypatch.setattr(f"{module}.PriceCatalog", lambda _path: _PriceCatalog())
    monkeypatch.setattr(f"{module}.PriceOfferRepository", _PriceOfferRepository)
    monkeypatch.setattr(f"{module}.AiProviderSettingsWidget.load", lambda _self: None)


def _page(monkeypatch) -> TenderWorkspacePage:
    _isolate_page_dependencies(monkeypatch)
    return TenderWorkspacePage(status_bar=QStatusBar())


def test_workspace_exposes_stable_ordered_tab_contract(monkeypatch) -> None:
    _app()
    page = _page(monkeypatch)

    assert page.section_keys == TOP_LEVEL_KEYS
    assert tuple(page.tabs.tabText(index) for index in range(page.tabs.count())) == TOP_LEVEL_LABELS
    assert page.tabs.objectName() == "TenderWorkspaceTabs"
    assert tuple(
        page.tabs.widget(index).objectName() for index in range(page.tabs.count())
    ) == tuple(f"TenderWorkspaceSection_{key}" for key in TOP_LEVEL_KEYS)

    assert page.settings_section_keys == SETTINGS_KEYS
    assert (
        tuple(page.settings_tabs.tabText(index) for index in range(page.settings_tabs.count()))
        == SETTINGS_LABELS
    )
    assert page.settings_tabs.objectName() == "TenderWorkspaceSettingsTabs"
    assert tuple(
        page.settings_tabs.widget(index).objectName() for index in range(page.settings_tabs.count())
    ) == tuple(f"TenderWorkspaceSettingsSection_{key}" for key in SETTINGS_KEYS)

    assert page.tabs.currentIndex() == 0
    assert page.settings_tabs.currentIndex() == 0
    assert page.select_section("catalog") is True
    assert page.tabs.currentIndex() == TOP_LEVEL_KEYS.index("catalog")
    assert page.select_section("not-a-section") is False


def test_workspace_open_tender_is_bounded(monkeypatch) -> None:
    _app()
    page = _page(monkeypatch)

    assert page.open_tender("tender-7") is True
    assert page.current_id == "tender-7"
    assert page.table.currentRow() == 0

    assert page.open_tender("missing") is False


def test_workspace_reuses_action_identity_and_binding_is_idempotent(monkeypatch) -> None:
    _app()
    page = _page(monkeypatch)
    action = QAction("Профили и поиск", page)
    action.setObjectName("actionTenderSearchProfiles")
    action.setShortcut(QKeySequence("Ctrl+Shift+F"))

    page.bind_tender_actions((action,))
    page.bind_tender_actions((action,))

    assert page.actions().count(action) == 1
    assert page.actions()[0] is action
    assert action.objectName() == "actionTenderSearchProfiles"
    assert action.shortcut().toString() == "Ctrl+Shift+F"
