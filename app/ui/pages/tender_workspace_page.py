"""Canonical implementation of the reusable tender workspace page."""

from __future__ import annotations
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import json
import hashlib
from typing import TYPE_CHECKING
from uuid import uuid4
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from app.repositories.tenders import TenderRepository, select_dashboard_tenders
from app.services.import_service import ImportService
from app.tender_analysis.engine import AnalysisEngine
from app.estimates.calculator import EstimateCalculator, EstimateItem, ProfitMode
from app.estimates.workspace import EstimateRow, totals
from app.document_generation.generator import DocumentGenerator
from app.catalog.price_catalog import PriceCatalog
from app.config.user_settings import UserSettingsStore, PlatformConnection
from app.connectors.manual import ManualConnectorTester
from app.services.readiness import check_application
from app.connectors.eis import EISConnector
from app.equipment.catalog import EquipmentCatalog
from app.services.backup import BackupService
from app.price_monitor import PriceOfferRepository, PriceSearchService, TenderRequirement
from app.core.path_manager import PathManager
from app.database.backup_manager import BackupManager
from app.database.diagnostics import DiagnosticsService
from app.database.maintenance import DatabaseMaintenanceService
from app.database.session import get_engine
from app.core.json_serialization import json_dumps
from app.ui.ai_provider_settings import AiProviderSettingsWidget
from app.ui.navigation.contracts import DashboardFilterId, RouteId
from app.ui.tables import TableColumnId, TableRevision, TableRole, TableRowId, TableState
from app.ui.viewmodels.dashboard_viewmodel import APP_TIMEZONE

if TYPE_CHECKING:
    from app.core.ai.provider_selection import AiProviderSelectionService
    from PySide6.QtGui import QAction

LICENSE_OPTIONS = [
    "Лицензия МЧС",
    "Лицензия ФСБ",
    "Лицензия Росгвардии",
    "СРО проектирование",
    "СРО строительство",
]
TEMPLATE_NAMES = [
    "00_Фирменный_бланк_Corteris.docx",
    "01_Коммерческое_предложение.docx",
    "02_Технико_коммерческое_предложение.docx",
    "03_Запрос_на_разъяснение.docx",
    "04_Гарантийное_письмо.docx",
    "05_Письмо_об_отсутствии_лицензий.docx",
    "06_Письмо_о_системе_налогообложения.docx",
    "07_Справка_об_опыте.docx",
    "08_Декларация_соответствия.docx",
    "09_Сопроводительное_письмо.docx",
    "10_Опись_документов.docx",
    "11_Протокол_разногласий.docx",
    "12_Управленческое_заключение.docx",
]

PROJECT_ROOT = Path(__file__).resolve().parents[3]

LEGACY_PLATFORM_COMPATIBILITY_NOTICE = (
    "Ручные подключения API/RSS/FTP сохранены только для совместимости и явной проверки соединения. "
    "Они не используются Corteris Tender Collector как источники поиска."
)
LEGACY_PLATFORM_CREDENTIAL_NOTICE = (
    "Этот legacy-раздел не управляет credentials. "
    "Используйте канонический менеджер источников тендеров."
)
LEGACY_PLATFORM_PROVIDER_ACTION_TEXT = "Открыть канонические источники тендеров"


class TenderWorkspacePage(QWidget):
    """Reusable owner of the existing tender workspace and its callbacks."""

    canonical_provider_settings_requested = Signal()

    SECTION_KEYS = (
        "overview",
        "analysis",
        "estimate",
        "catalog",
        "readiness",
        "tools",
        "price_monitor",
        "settings",
    )
    SETTINGS_SECTION_KEYS = (
        "platforms",
        "ai",
        "company",
        "economics",
        "templates",
        "database",
    )

    def __init__(
        self,
        *,
        ai_provider_selection_service: "AiProviderSelectionService | None" = None,
        status_bar: QStatusBar | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("TenderWorkspacePage")
        self._status_bar = status_bar or QStatusBar(self)
        self.repo = TenderRepository()
        self.current_id = None
        self.last_report = None
        self.last_estimate = None
        self.generated_files = []
        self.store = UserSettingsStore()
        self.prefs = self.store.load()
        self.ai_provider_selection_service = ai_provider_selection_service
        self.catalog = PriceCatalog(PROJECT_ROOT / "data" / "price_catalog.xlsx")
        self.brands = json.loads(
            (PROJECT_ROOT / "data" / "brands_ru.json").read_text(encoding="utf-8")
        )
        self.price_repo = PriceOfferRepository(PROJECT_ROOT / "data" / "price_offers.json")
        self.price_service = PriceSearchService(self.price_repo)
        self.current_price_results = []
        self._dashboard_filter: DashboardFilterId | None = None
        self._unified_search_panel: QWidget | None = None
        self._build()
        self._load()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("TenderWorkspaceTabs")
        root.addWidget(self.tabs)
        self._section_indexes: dict[str, int] = {}
        self._settings_section_indexes: dict[str, int] = {}
        dash = QWidget()
        dash.setObjectName("TenderWorkspaceSection_overview")
        dl = QVBoxLayout(dash)
        top = QHBoxLayout()
        self.logo = QLabel()
        self.logo.setMaximumHeight(100)
        top.addWidget(self.logo)
        top.addWidget(
            QLabel(
                "<h2>AIBOS Security — Corteris Tender AI 1.2.1</h2><p>Локальная система анализа и подготовки тендерных заявок</p>"
            )
        )
        top.addStretch()
        dl.addLayout(top)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Номер", "Название", "НМЦК", "Балл", "Рекомендация"]
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.cellClicked.connect(self.select_row)
        dl.addWidget(self.table)
        actions = QHBoxLayout()
        for text, slot in [
            ("Создать тендер", self.create_tender_dialog),
            ("Загрузить 10 демо-тендеров", self.load_demo),
            ("Импорт документов", self.import_docs),
            ("Анализировать", self.run_analysis),
            ("Сформировать пакет", self.generate_docs),
        ]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            actions.addWidget(b)
        dl.addLayout(actions)
        self._section_indexes["overview"] = self.tabs.addTab(dash, "Панель управления")

        an = QWidget()
        an.setObjectName("TenderWorkspaceSection_analysis")
        al = QVBoxLayout(an)
        calc = QHBoxLayout()
        self.profit_mode = QComboBox()
        self.profit_mode.addItem("Наценка к себестоимости", ProfitMode.MARKUP.value)
        self.profit_mode.addItem("Рентабельность по выручке", ProfitMode.REVENUE_MARGIN.value)
        self.profit_percent = QDoubleSpinBox()
        self.profit_percent.setRange(0, 99)
        self.vat = QDoubleSpinBox()
        self.vat.setRange(0, 50)
        self.risk = QDoubleSpinBox()
        self.risk.setRange(0, 100)
        for label, w in [
            ("Расчёт прибыли", self.profit_mode),
            ("Прибыль, %", self.profit_percent),
            ("НДС, %", self.vat),
            ("Резерв, %", self.risk),
        ]:
            calc.addWidget(QLabel(label))
            calc.addWidget(w)
        al.addLayout(calc)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        al.addWidget(self.output)
        self._section_indexes["analysis"] = self.tabs.addTab(an, "Анализ тендера")

        sections = (
            ("estimate", "Смета", self._estimate_tab()),
            ("catalog", "Оборудование и бренды", self._catalog_tab()),
            ("readiness", "Проверка заявки", self._readiness_tab()),
            ("tools", "Инструменты 1.4", self._v14_tools_tab()),
            ("price_monitor", "Мониторинг цен 1.5", self._price_monitor_tab()),
        )
        for key, label, widget in sections:
            widget.setObjectName(f"TenderWorkspaceSection_{key}")
            self._section_indexes[key] = self.tabs.addTab(widget, label)

        settings_page = QWidget()
        settings_page.setObjectName("TenderWorkspaceSection_settings")
        settings_layout = QVBoxLayout(settings_page)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_tabs = QTabWidget(settings_page)
        self.settings_tabs.setObjectName("TenderWorkspaceSettingsTabs")
        settings_layout.addWidget(self.settings_tabs)
        settings_sections = (
            ("platforms", "Площадки API/RSS/FTP", self._platform_tab()),
            ("ai", "ChatGPT / ИИ", self._ai_tab()),
            ("company", "Компания и реквизиты", self._company_tab()),
            ("economics", "Лицензии и экономика", self._rules_tab()),
            ("templates", "Фирменные бланки", self._templates_tab()),
            ("database", "Диагностика БД", self._diagnostics_tab()),
        )
        for key, label, widget in settings_sections:
            widget.setObjectName(f"TenderWorkspaceSettingsSection_{key}")
            self._settings_section_indexes[key] = self.settings_tabs.addTab(widget, label)
        self._section_indexes["settings"] = self.tabs.addTab(settings_page, "Настройки")

    @property
    def section_keys(self) -> tuple[str, ...]:
        return self.SECTION_KEYS

    @property
    def settings_section_keys(self) -> tuple[str, ...]:
        return self.SETTINGS_SECTION_KEYS

    def statusBar(self) -> QStatusBar:
        """Return the shell-owned status bar used by existing callbacks."""
        return self._status_bar

    def refresh_tenders(self) -> None:
        """Refresh the existing local tender table."""
        self.refresh()

    @property
    def dashboard_filter(self) -> DashboardFilterId | None:
        return self._dashboard_filter

    def apply_dashboard_filter(self, dashboard_filter: str | None) -> None:
        """Apply or clear one closed Dashboard tender cohort."""
        if dashboard_filter is None:
            self._dashboard_filter = None
        else:
            filter_id = DashboardFilterId(dashboard_filter)
            if filter_id.route_id is not RouteId.TENDERS:
                raise ValueError("Dashboard filter does not belong to tenders")
            self._dashboard_filter = filter_id
        self.select_section("overview")
        self.refresh_tenders()

    def open_tender(self, tender_id: str) -> bool:
        """Select an existing local row without inventing a missing tender."""
        normalized = str(tender_id).strip()
        if not normalized:
            return False
        self.refresh_tenders()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None or item.text() != normalized:
                continue
            self.table.selectRow(row)
            self.select_row(row, 0)
            return True
        return False

    def apply_compatibility_search_text(self, query: str) -> None:
        """Populate only the existing price/equipment catalog query."""
        self.catalog_query.setText(str(query).strip())

    def install_unified_search_panel(self, panel: QWidget) -> None:
        """Mount the single controller-owned panel above the existing tabs."""
        if self._unified_search_panel is panel:
            return
        if self._unified_search_panel is not None:
            raise ValueError("A unified tender search panel is already installed")
        self._unified_search_panel = panel
        panel.setParent(self)
        layout = self.layout()
        if layout is None:
            raise RuntimeError("Tender workspace layout is unavailable")
        layout.insertWidget(0, panel)

    def submit_unified_search_text(self, query: str) -> bool:
        """Delegate a topbar query without owning search validation."""
        panel = self._unified_search_panel
        submitter = getattr(panel, "submit_query", None)
        if not callable(submitter):
            return False
        return bool(submitter(str(query)))

    def focus_unified_search(self) -> bool:
        """Focus the installed search panel through its narrow API."""
        panel = self._unified_search_panel
        focuser = getattr(panel, "focus_search", None)
        if not callable(focuser):
            return False
        return bool(focuser())

    def select_section(self, key: str) -> bool:
        """Select a known top-level section by its stable key."""
        index = self._section_indexes.get(str(key).strip())
        if index is None:
            return False
        self.tabs.setCurrentIndex(index)
        return True

    def select_settings_section(self, key: str) -> bool:
        """Select a known embedded settings section by its stable key."""
        index = self._settings_section_indexes.get(str(key).strip())
        if index is None or not self.select_section("settings"):
            return False
        self.settings_tabs.setCurrentIndex(index)
        return True

    def bind_tender_actions(self, actions: Iterable["QAction"]) -> None:
        """Expose existing controller actions without reparenting or recreating them."""
        installed = self.actions()
        for action in actions:
            if action not in installed:
                self.addAction(action)
                installed.append(action)

    def _estimate_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        bar = QHBoxLayout()
        for text, slot in [
            ("Добавить строку", self.add_estimate_row),
            ("Из прайса", self.add_from_catalog),
            ("Удалить строку", self.remove_estimate_row),
            ("Пересчитать", self.recalculate_estimate),
        ]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            bar.addWidget(b)
        layout.addLayout(bar)
        self.estimate_table = QTableWidget(0, 7)
        self.estimate_table.setAccessibleName("Tender estimate lines")
        self.estimate_table.setAccessibleDescription(
            "Editable estimate lines with stable identity and exact selected-row actions."
        )
        self.estimate_table.setHorizontalHeaderLabels(
            ["Наименование", "Кол-во", "Ед.", "Себестоимость", "Наценка %", "НДС %", "Цена с НДС"]
        )
        self.estimate_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.estimate_table)
        self.estimate_totals = QLabel("<b>Итого: 0 ₽</b>")
        layout.addWidget(self.estimate_totals)
        return w

    def _catalog_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        q = QHBoxLayout()
        self.catalog_query = QLineEdit()
        self.catalog_query.setPlaceholderText("Поиск по прайсу")
        b = QPushButton("Найти")
        b.clicked.connect(self.search_catalog)
        q.addWidget(self.catalog_query)
        q.addWidget(b)
        layout.addLayout(q)
        self.catalog_table = QTableWidget(0, 6)
        self.catalog_table.setAccessibleName("Equipment catalog")
        self.catalog_table.setAccessibleDescription(
            "Catalog results with stable identity; adding uses the exact selected item."
        )
        self.catalog_table.setHorizontalHeaderLabels(
            ["Категория", "Позиция", "Ед.", "Себестоимость", "Мин. рынок", "Макс. рынок"]
        )
        self.catalog_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.catalog_table)
        split = QSplitter()
        self.brand_categories = QListWidget()
        self.brand_list = QListWidget()
        self.brand_categories.addItems(self.brands.keys())
        self.brand_categories.currentTextChanged.connect(self.show_brands)
        split.addWidget(self.brand_categories)
        split.addWidget(self.brand_list)
        layout.addWidget(QLabel("<b>Реестр брендов российского рынка (редактируемый)</b>"))
        layout.addWidget(split)
        br = QHBoxLayout()
        self.new_brand = QLineEdit()
        self.new_brand.setPlaceholderText("Добавить бренд в выбранную категорию")
        bb = QPushButton("Добавить")
        bb.clicked.connect(self.add_brand)
        br.addWidget(self.new_brand)
        br.addWidget(bb)
        layout.addLayout(br)
        return w

    def _readiness_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        b = QPushButton("Проверить сформированный пакет")
        b.clicked.connect(self.run_readiness)
        layout.addWidget(b)
        self.readiness_table = QTableWidget(0, 3)
        self.readiness_table.setHorizontalHeaderLabels(["Проверка", "Результат", "Критичность"])
        self.readiness_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.readiness_table)
        self.readiness_status = QLabel()
        layout.addWidget(self.readiness_status)
        return w

    def _v14_tools_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        eis_box = QGroupBox("Импорт из ЕИС по номеру или ссылке")
        ef = QHBoxLayout(eis_box)
        self.eis_input = QLineEdit()
        self.eis_input.setPlaceholderText("Номер закупки или ссылка zakupki.gov.ru")
        eb = QPushButton("Создать карточку")
        eb.clicked.connect(self.import_eis_reference)
        ef.addWidget(self.eis_input)
        ef.addWidget(eb)
        layout.addWidget(eis_box)
        cat_box = QGroupBox("Каталог оборудования поставщиков")
        cf = QHBoxLayout(cat_box)
        cb = QPushButton("Импортировать прайс CSV/XLSX")
        cb.clicked.connect(self.import_equipment_catalog)
        self.equipment_count = QLabel("Позиций: 0")
        cf.addWidget(cb)
        cf.addWidget(self.equipment_count)
        cf.addStretch()
        layout.addWidget(cat_box)
        backup_box = QGroupBox("Резервное копирование")
        bf = QHBoxLayout(backup_box)
        bb = QPushButton("Создать резервную копию")
        bb.clicked.connect(self.create_backup)
        bf.addWidget(bb)
        bf.addStretch()
        layout.addWidget(backup_box)
        note = QLabel(
            "OCR Tesseract и структурированный ИИ-анализ включены в ядро. Подключение выполняется через настройки ИИ."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        self.equipment_catalog_v14 = EquipmentCatalog(
            PROJECT_ROOT / "data" / "equipment_catalog.json"
        )
        self.equipment_count.setText(f"Позиций: {len(self.equipment_catalog_v14.items)}")
        return w

    def _price_monitor_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        form = QGridLayout()
        self.pm_name = QLineEdit()
        self.pm_name.setPlaceholderText("Например: IP-камера 4 Мп")
        self.pm_qty = QDoubleSpinBox()
        self.pm_qty.setRange(0.01, 1_000_000)
        self.pm_qty.setValue(1)
        self.pm_brand = QLineEdit()
        self.pm_brand.setPlaceholderText("Обязательный бренд, если есть")
        self.pm_model = QLineEdit()
        self.pm_model.setPlaceholderText("Обязательная модель, если есть")
        self.pm_equiv = QCheckBox("Разрешён эквивалент")
        self.pm_equiv.setChecked(True)
        self.pm_days = QSpinBox()
        self.pm_days.setRange(0, 3650)
        self.pm_warranty = QSpinBox()
        self.pm_warranty.setRange(0, 240)
        self.pm_cert = QCheckBox("Требуется сертификат")
        self.pm_official = QCheckBox("Только официальная поставка")
        form.addWidget(QLabel("Позиция ТЗ"), 0, 0)
        form.addWidget(self.pm_name, 0, 1, 1, 3)
        form.addWidget(QLabel("Количество"), 1, 0)
        form.addWidget(self.pm_qty, 1, 1)
        form.addWidget(QLabel("Бренд"), 1, 2)
        form.addWidget(self.pm_brand, 1, 3)
        form.addWidget(QLabel("Модель"), 2, 0)
        form.addWidget(self.pm_model, 2, 1)
        form.addWidget(self.pm_equiv, 2, 2)
        form.addWidget(self.pm_cert, 2, 3)
        form.addWidget(QLabel("Макс. поставка, дней"), 3, 0)
        form.addWidget(self.pm_days, 3, 1)
        form.addWidget(QLabel("Мин. гарантия, мес."), 3, 2)
        form.addWidget(self.pm_warranty, 3, 3)
        form.addWidget(self.pm_official, 4, 0, 1, 2)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        for text, slot in [
            ("Импорт прайса поставщика", self.import_price_offers),
            ("Найти минимальную цену", self.search_lowest_price),
            ("Показать все, включая несоответствия", lambda: self.search_lowest_price(False)),
            ("Добавить выбранное в смету", self.add_price_result_to_estimate),
        ]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        layout.addLayout(buttons)
        self.pm_table = QTableWidget(0, 10)
        self.pm_table.setHorizontalHeaderLabels(
            [
                "Соответствие",
                "Поставщик",
                "Бренд",
                "Модель",
                "Цена ед.",
                "Доставка",
                "Итого без НДС",
                "Итого с НДС",
                "Срок, дн.",
                "Комментарий",
            ]
        )
        self.pm_table.horizontalHeader().setSectionResizeMode(9, QHeaderView.Stretch)
        layout.addWidget(self.pm_table)
        self.pm_summary = QLabel(f"Загружено предложений: {len(self.price_repo.offers)}")
        layout.addWidget(self.pm_summary)
        return w

    def import_price_offers(self):
        src, _ = QFileDialog.getOpenFileName(
            self,
            "Прайс или предложения поставщика",
            "",
            "Прайсы (*.xlsx *.xlsm *.csv *.json *.xml)",
        )
        if not src:
            return
        try:
            count = self.price_repo.import_file(Path(src))
            self.pm_summary.setText(f"Загружено предложений: {len(self.price_repo.offers)}")
            QMessageBox.information(
                self, "Мониторинг цен", f"Импортировано/обновлено предложений: {count}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "Мониторинг цен", str(exc))

    def _current_requirement(self):
        return TenderRequirement(
            name=self.pm_name.text().strip(),
            quantity=self.pm_qty.value(),
            required_brand=self.pm_brand.text().strip(),
            required_model=self.pm_model.text().strip(),
            allow_equivalent=self.pm_equiv.isChecked(),
            max_lead_time_days=self.pm_days.value(),
            min_warranty_months=self.pm_warranty.value(),
            require_certificate=self.pm_cert.isChecked(),
            require_official_supply=self.pm_official.isChecked(),
        )

    def search_lowest_price(self, only_compliant=True):
        requirement = self._current_requirement()
        if not requirement.name:
            QMessageBox.warning(self, "Мониторинг цен", "Введите наименование позиции из ТЗ")
            return
        self.current_price_results = self.price_service.search(
            requirement, self.vat.value(), only_compliant
        )
        self.pm_table.setRowCount(len(self.current_price_results))
        for r, x in enumerate(self.current_price_results):
            comment = "; ".join(x.reasons or x.neutral_notes) or "Полное соответствие"
            values = [
                "Да" if x.compliant else "Нет",
                x.offer.supplier,
                x.offer.brand,
                x.offer.model,
                f"{x.offer.unit_price:,.2f}",
                f"{x.offer.delivery_cost:,.2f}",
                f"{x.total['total_net']:,.2f}",
                f"{x.total['total_gross']:,.2f}",
                x.offer.lead_time_days,
                comment,
            ]
            for c, v in enumerate(values):
                self.pm_table.setItem(r, c, QTableWidgetItem(str(v)))
        cheapest = next((x for x in self.current_price_results if x.compliant), None)
        if cheapest:
            self.pm_summary.setText(
                f"Минимальная безопасная закупка: {cheapest.total['total_net']:,.2f} ₽ без НДС — {cheapest.offer.supplier}, {cheapest.offer.brand} {cheapest.offer.model}"
            )
        else:
            self.pm_summary.setText(
                "Подходящих предложений не найдено. Требуется запрос цены поставщикам."
            )

    def add_price_result_to_estimate(self):
        row = self.pm_table.currentRow()
        if row < 0 or row >= len(self.current_price_results):
            QMessageBox.warning(self, "Мониторинг цен", "Выберите предложение")
            return
        result = self.current_price_results[row]
        if not result.compliant:
            QMessageBox.warning(
                self,
                "Мониторинг цен",
                "Несоответствующее предложение нельзя автоматически добавить в смету",
            )
            return
        self.add_estimate_row(
            f"{result.offer.brand} {result.offer.model} ({result.offer.supplier})",
            result.requirement.quantity,
            result.requirement.unit,
            result.total["unit_effective_net"],
        )
        self.recalculate_estimate()
        self.tabs.setCurrentIndex(2)

    def import_eis_reference(self):
        try:
            data = EISConnector().create_stub(self.eis_input.text())
            QMessageBox.information(self, "ЕИС", json_dumps(data))
        except Exception as exc:
            QMessageBox.warning(self, "ЕИС", str(exc))

    def import_equipment_catalog(self):
        src, _ = QFileDialog.getOpenFileName(
            self, "Прайс поставщика", "", "Прайсы (*.xlsx *.xlsm *.csv)"
        )
        if not src:
            return
        try:
            count = self.equipment_catalog_v14.import_file(Path(src))
            self.equipment_count.setText(f"Позиций: {len(self.equipment_catalog_v14.items)}")
            QMessageBox.information(self, "Каталог", f"Импортировано строк: {count}")
        except Exception as exc:
            QMessageBox.warning(self, "Каталог", str(exc))

    def create_backup(self):
        folder = QFileDialog.getExistingDirectory(self, "Папка резервных копий")
        if not folder:
            return
        root = PROJECT_ROOT
        sources = [root / "data", root / "templates", root / "assets"]
        db = Path.home() / ".corteris_tender_ai" / "corteris.db"
        if db.exists():
            sources.append(db)
        output = BackupService().create(Path(folder), sources, {"version": "1.5"})
        QMessageBox.information(self, "Резервная копия", f"Создано: {output}")

    def _platform_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        compatibility_notice = QLabel(LEGACY_PLATFORM_COMPATIBILITY_NOTICE, w)
        compatibility_notice.setObjectName("LegacyPlatformCompatibilityNotice")
        compatibility_notice.setWordWrap(True)
        layout.addWidget(compatibility_notice)
        credential_notice = QLabel(LEGACY_PLATFORM_CREDENTIAL_NOTICE, w)
        credential_notice.setObjectName("LegacyPlatformCredentialNotice")
        credential_notice.setWordWrap(True)
        layout.addWidget(credential_notice)
        canonical_sources = QPushButton(LEGACY_PLATFORM_PROVIDER_ACTION_TEXT, w)
        canonical_sources.setObjectName("OpenCanonicalTenderProviders")
        canonical_sources.clicked.connect(self.canonical_provider_settings_requested.emit)
        layout.addWidget(canonical_sources)
        f = QHBoxLayout()
        self.platform_name = QLineEdit()
        self.platform_name.setPlaceholderText("Название")
        self.platform_protocol = QComboBox()
        self.platform_protocol.addItems(["API", "RSS", "FTP", "FTPS"])
        self.platform_endpoint = QLineEdit()
        self.platform_endpoint.setPlaceholderText("URL")
        self.platform_user = QLineEdit()
        self.platform_user.setPlaceholderText("Логин")
        self.platform_secret = QLineEdit()
        self.platform_secret.setEchoMode(QLineEdit.Password)
        self.platform_secret.setPlaceholderText("Credentials управляются в каноническом менеджере")
        self.platform_secret.setEnabled(False)
        for x in [
            self.platform_name,
            self.platform_protocol,
            self.platform_endpoint,
            self.platform_user,
            self.platform_secret,
        ]:
            f.addWidget(x)
        layout.addLayout(f)
        r = QHBoxLayout()
        for text, slot in [
            ("Добавить/обновить", self.add_platform),
            ("Удалить", self.remove_platform),
            ("Проверить", self.test_platform),
        ]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            r.addWidget(b)
        layout.addLayout(r)
        self.platform_table = QTableWidget(0, 6)
        self.platform_table.setHorizontalHeaderLabels(
            ["Название", "Тип", "Адрес", "Логин", "Включено", "Статус"]
        )
        self.platform_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.platform_table.cellClicked.connect(self.platform_selected)
        layout.addWidget(self.platform_table)
        return w

    def _ai_tab(self):
        self.ai_settings_widget = AiProviderSettingsWidget(
            self.ai_provider_selection_service,
        )
        self.ai_provider = self.ai_settings_widget.provider_combo
        self.api_key = self.ai_settings_widget.credential_edit
        self.api_model = self.ai_settings_widget.model_edit
        self.api_url = self.ai_settings_widget.base_url_edit
        return self.ai_settings_widget

    def _company_tab(self):
        w = QWidget()
        f = QFormLayout(w)
        self.company_fields = {}
        labels = [
            ("company_name", "Наименование"),
            ("inn", "ИНН"),
            ("kpp", "КПП"),
            ("ogrn", "ОГРН"),
            ("legal_address", "Юридический адрес"),
            ("director", "Генеральный директор"),
            ("phone", "Телефон"),
            ("email", "Email"),
            ("website", "Сайт"),
            ("taxation_system", "Система налогообложения"),
        ]
        for key, label in labels:
            e = QLineEdit()
            self.company_fields[key] = e
            f.addRow(label, e)
        self.asset_labels = {}
        for kind, label in [("logo", "Логотип"), ("signature", "Подпись"), ("stamp", "Печать")]:
            row = QHBoxLayout()
            q = QLineEdit()
            q.setReadOnly(True)
            self.asset_labels[kind] = q
            b = QPushButton("Заменить")
            b.clicked.connect(lambda checked=False, k=kind: self.replace_asset(k))
            row.addWidget(q)
            row.addWidget(b)
            f.addRow(label, row)
        b = QPushButton("Сохранить карточку компании")
        b.clicked.connect(self.save_preferences)
        f.addRow(b)
        return w

    def _rules_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.license_checks = {}
        for name in LICENSE_OPTIONS:
            c = QCheckBox(name)
            self.license_checks[name] = c
            layout.addWidget(c)
        form = QFormLayout()
        self.settings_profit_mode = QComboBox()
        self.settings_profit_mode.addItem("Наценка к себестоимости", ProfitMode.MARKUP.value)
        self.settings_profit_mode.addItem(
            "Рентабельность по выручке", ProfitMode.REVENUE_MARGIN.value
        )
        self.settings_profit = QDoubleSpinBox()
        self.settings_profit.setRange(0, 99)
        self.settings_vat = QDoubleSpinBox()
        self.settings_vat.setRange(0, 50)
        self.settings_risk = QDoubleSpinBox()
        self.settings_risk.setRange(0, 100)
        form.addRow("Метод", self.settings_profit_mode)
        form.addRow("Прибыль, %", self.settings_profit)
        form.addRow("НДС по умолчанию, %", self.settings_vat)
        form.addRow("Резерв риска, %", self.settings_risk)
        b = QPushButton("Сохранить")
        b.clicked.connect(self.save_preferences)
        form.addRow(b)
        layout.addLayout(form)
        return w

    def _templates_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.template_dir_label = QLabel()
        layout.addWidget(self.template_dir_label)
        self.template_table = QTableWidget(len(TEMPLATE_NAMES), 3)
        self.template_table.setHorizontalHeaderLabels(["Документ", "Текущий файл", "Действие"])
        self.template_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for r, n in enumerate(TEMPLATE_NAMES):
            self.template_table.setItem(r, 0, QTableWidgetItem(n))
            b = QPushButton("Заменить DOCX")
            b.clicked.connect(lambda checked=False, row=r: self.replace_template(row))
            self.template_table.setCellWidget(r, 2, b)
        layout.addWidget(self.template_table)
        return w

    def _load(self):
        p = self.prefs
        self.profit_mode.setCurrentIndex(max(self.profit_mode.findData(p.profit_mode), 0))
        self.profit_percent.setValue(p.profit_percent)
        self.vat.setValue(p.vat_percent)
        self.risk.setValue(p.risk_percent)
        self.settings_profit_mode.setCurrentIndex(
            max(self.settings_profit_mode.findData(p.profit_mode), 0)
        )
        self.settings_profit.setValue(p.profit_percent)
        self.settings_vat.setValue(p.vat_percent)
        self.settings_risk.setValue(p.risk_percent)
        self.ai_settings_widget.load()
        for k, e in self.company_fields.items():
            e.setText(str(getattr(p, k)))
        for kind, q in self.asset_labels.items():
            q.setText(getattr(p, f"{kind}_path"))
        for n, c in self.license_checks.items():
            c.setChecked(n in p.licenses)
        self.refresh_platforms()
        self.refresh_templates()
        self._refresh_logo()
        self.search_catalog()
        self.brand_categories.setCurrentRow(0)

    def _refresh_logo(self):
        p = Path(self.prefs.logo_path)
        if p.exists():
            self.logo.setPixmap(QPixmap(str(p)).scaledToHeight(90, Qt.SmoothTransformation))

    def save_preferences(self):
        p = self.prefs
        p.profit_mode = self.settings_profit_mode.currentData()
        p.profit_percent = self.settings_profit.value()
        p.vat_percent = self.settings_vat.value()
        p.risk_percent = self.settings_risk.value()
        p.licenses = [n for n, c in self.license_checks.items() if c.isChecked()]
        for k, e in self.company_fields.items():
            setattr(p, k, e.text().strip())
        self.store.save(p)
        self.profit_mode.setCurrentIndex(max(self.profit_mode.findData(p.profit_mode), 0))
        self.profit_percent.setValue(p.profit_percent)
        self.vat.setValue(p.vat_percent)
        self.risk.setValue(p.risk_percent)
        QMessageBox.information(self, "Настройки", "Настройки сохранены")

    def replace_asset(self, kind):
        src, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл", "", "Изображения (*.png *.jpg *.jpeg)"
        )
        if not src:
            return
        target = self.store.import_company_asset(Path(src), kind)
        setattr(self.prefs, f"{kind}_path", str(target))
        self.store.save(self.prefs)
        self.asset_labels[kind].setText(str(target))
        self._refresh_logo()

    def create_tender_dialog(self):
        title, ok = QInputDialog.getText(self, "Новый тендер", "Название закупки:")
        if not ok or not title.strip():
            return
        number, _ = QInputDialog.getText(self, "Новый тендер", "Номер закупки:")
        nmck, ok = QInputDialog.getDouble(self, "Новый тендер", "НМЦК:", 0, 0, 10**12, 2)
        self.current_id = ImportService().create_tender(title.strip(), number.strip(), " ", nmck)
        self.refresh()

    def load_demo(self):
        data = json.loads((PROJECT_ROOT / "data" / "demo_tenders.json").read_text(encoding="utf-8"))
        for x in data:
            ImportService().create_tender(x["title"], x["number"], "demo://", x["nmck"])
        self.refresh()
        QMessageBox.information(self, "Демо", "Добавлено 10 демонстрационных тендеров")

    def import_docs(self):
        if not self.current_id:
            QMessageBox.warning(self, "Тендер", "Выберите тендер")
            return
        p, _ = QFileDialog.getOpenFileName(
            self, "Документ или архив", "", "Документы (*.zip *.pdf *.docx *.xlsx *.txt *.csv)"
        )
        if p:
            QMessageBox.information(
                self,
                "Импорт",
                f"Импортировано: {len(ImportService().import_path(self.current_id, Path(p)))}",
            )

    def run_analysis(self):
        if not self.current_id:
            QMessageBox.warning(self, "Тендер", "Выберите тендер")
            return
        rows = self._estimate_rows()
        items = [
            EstimateItem(x.name, x.quantity, x.unit, x.cost, x.markup_percent) for x in rows
        ] or [EstimateItem("Оборудование", 1, "компл.", 100000, self.profit_percent.value())]
        self.last_estimate = EstimateCalculator().calculate(
            items,
            vat_percent=self.vat.value(),
            risk_percent=self.risk.value(),
            profit_percent=self.profit_percent.value(),
            profit_mode=self.profit_mode.currentData(),
        )
        self.last_report = AnalysisEngine().analyze(
            self.current_id,
            self.last_estimate["total"],
            self.last_estimate["protected_cost"],
            self.last_estimate,
        )
        self.output.setPlainText(json_dumps(self.last_report))
        self.refresh()

    def generate_docs(self):
        if not self.last_report or not self.last_estimate:
            QMessageBox.warning(self, "Пакет", "Сначала выполните анализ")
            return
        path = DocumentGenerator().package(self.current_id, self.last_report, self.last_estimate)
        self.generated_files = [Path(path)]
        QMessageBox.information(self, "Пакет", f"Создан архив:\n{path}")

    def refresh(self):
        data = self.repo.list()
        if self._dashboard_filter is not None:
            data = select_dashboard_tenders(
                data,
                self._dashboard_filter,
                at=datetime.now(APP_TIMEZONE),
            )
        self.table.setRowCount(len(data))
        for r, t in enumerate(data):
            for c, v in enumerate(
                [t.id, t.number, t.title, f"{t.nmck:,.2f}", t.score, t.recommendation]
            ):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))

    def select_row(self, row, col):
        self.current_id = self.table.item(row, 0).text()
        self.statusBar().showMessage(f"Выбран тендер ID {self.current_id}")

    def add_estimate_row(self, name="Новая позиция", qty=1, unit="шт.", cost=0):
        r = self.estimate_table.rowCount()
        self.estimate_table.insertRow(r)
        vals = [name, qty, unit, cost, self.prefs.profit_percent, self.prefs.vat_percent, 0]
        row_id = TableRowId("estimate_line", uuid4().hex)
        for c, v in enumerate(vals):
            item = QTableWidgetItem(str(v))
            self._set_workspace_item_roles(
                item,
                row_id=row_id,
                revision=TableRevision(f"created:{row_id.value}"),
                column_id=("name", "quantity", "unit", "cost", "profit", "vat", "total")[c],
                typed_value=self._workspace_typed_value(c, v),
                action_ids=("edit", "remove"),
            )
            self.estimate_table.setItem(r, c, item)

    def add_from_catalog(self):
        row = self._selected_workspace_row(self.catalog_table, "catalog_line")
        if row < 0:
            QMessageBox.warning(
                self, "Прайс", "Выберите позицию во вкладке «Оборудование и бренды»"
            )
            return
        self.add_estimate_row(
            self.catalog_table.item(row, 1).text(),
            1,
            self.catalog_table.item(row, 2).text(),
            float(self.catalog_table.item(row, 3).text().replace(" ", "").replace(",", ".")),
        )

    def remove_estimate_row(self):
        r = self._selected_workspace_row(self.estimate_table, "estimate_line")
        if r >= 0:
            self.estimate_table.removeRow(r)
            self.recalculate_estimate()

    def _estimate_rows(self):
        out = []
        for r in range(self.estimate_table.rowCount()):
            try:
                out.append(
                    EstimateRow(
                        self.estimate_table.item(r, 0).text(),
                        float(self.estimate_table.item(r, 1).text().replace(",", ".")),
                        self.estimate_table.item(r, 2).text(),
                        float(
                            self.estimate_table.item(r, 3).text().replace(" ", "").replace(",", ".")
                        ),
                        float(self.estimate_table.item(r, 4).text().replace(",", ".")),
                        float(self.estimate_table.item(r, 5).text().replace(",", ".")),
                    )
                )
            except Exception:
                pass
        return out

    def recalculate_estimate(self):
        rows = self._estimate_rows()
        for r, x in enumerate(rows):
            existing = self.estimate_table.item(r, 0)
            row_id = existing.data(TableRole.ROW_ID) if existing is not None else None
            if not isinstance(row_id, TableRowId):
                row_id = TableRowId("estimate_line", uuid4().hex)
            item = QTableWidgetItem(f"{x.price_with_vat:,.2f}")
            self._set_workspace_item_roles(
                item,
                row_id=row_id,
                revision=self._workspace_row_revision(self.estimate_table, r),
                column_id="total",
                typed_value=Decimal(str(x.price_with_vat)),
                action_ids=("edit", "remove"),
            )
            self.estimate_table.setItem(r, 6, item)
            self._refresh_workspace_row_roles(self.estimate_table, r, "estimate_line")
        t = totals(rows)
        self.estimate_totals.setText(
            f"<b>Себестоимость: {t['cost']:,.2f} ₽ | Прибыль: {t['profit']:,.2f} ₽ | Рентабельность: {t['margin']:.2f}% | Итого с НДС: {t['gross']:,.2f} ₽</b>"
        )

    def search_catalog(self):
        items = self.catalog.search(
            self.catalog_query.text() if hasattr(self, "catalog_query") else "", 100
        )
        self.catalog_table.setRowCount(len(items))
        for r, x in enumerate(items):
            identity_material = (
                f"{x.category}|{x.name}|{x.unit}|{x.base_cost}|{x.market_min}|{x.market_max}|{r}"
            )
            row_id = TableRowId(
                "catalog_line",
                hashlib.sha256(identity_material.encode("utf-8")).hexdigest(),
            )
            for c, v in enumerate(
                [
                    x.category,
                    x.name,
                    x.unit,
                    f"{x.base_cost:.2f}",
                    f"{x.market_min:.2f}",
                    f"{x.market_max:.2f}",
                ]
            ):
                item = QTableWidgetItem(str(v))
                self._set_workspace_item_roles(
                    item,
                    row_id=row_id,
                    revision=TableRevision(row_id.value),
                    column_id=(
                        "category",
                        "name",
                        "unit",
                        "base_cost",
                        "market_min",
                        "market_max",
                    )[c],
                    typed_value=self._workspace_typed_value(c, v, catalog=True),
                    action_ids=("add_to_estimate",),
                )
                self.catalog_table.setItem(r, c, item)

    @staticmethod
    def _workspace_typed_value(column: int, value: object, *, catalog: bool = False) -> object:
        numeric = {3, 4, 5} if catalog else {1, 3, 4, 5, 6}
        if column in numeric:
            try:
                return Decimal(str(value).replace(" ", "").replace(",", "."))
            except Exception:
                return None
        return str(value)

    @staticmethod
    def _set_workspace_item_roles(
        item: QTableWidgetItem,
        *,
        row_id: TableRowId,
        revision: TableRevision,
        column_id: str,
        typed_value: object,
        action_ids: tuple[str, ...],
    ) -> None:
        item.setData(TableRole.ROW_ID, row_id)
        item.setData(TableRole.ROW_REVISION, revision)
        item.setData(TableRole.COLUMN_ID, TableColumnId(column_id))
        item.setData(TableRole.SORT_VALUE, typed_value)
        item.setData(TableRole.EXPORT_VALUE, typed_value)
        item.setData(TableRole.ACTION_IDS, action_ids)
        item.setData(TableRole.STATE, TableState.READY)
        item.setData(Qt.ItemDataRole.AccessibleTextRole, item.text())

    @staticmethod
    def _selected_workspace_row(table: QTableWidget, namespace: str) -> int:
        current = table.currentRow()
        item = table.item(current, 0) if current >= 0 else None
        selected_id = item.data(TableRole.ROW_ID) if item is not None else None
        if item is not None and not isinstance(selected_id, TableRowId):
            material = "|".join(
                table.item(current, column).text()
                if table.item(current, column) is not None
                else ""
                for column in range(table.columnCount())
            )
            selected_id = TableRowId(
                namespace,
                hashlib.sha256(material.encode("utf-8")).hexdigest(),
            )
            for column in range(table.columnCount()):
                candidate = table.item(current, column)
                if candidate is not None:
                    candidate.setData(TableRole.ROW_ID, selected_id)
        if not isinstance(selected_id, TableRowId) or selected_id.namespace != namespace:
            return -1
        for row in range(table.rowCount()):
            candidate = table.item(row, 0)
            if candidate is not None and candidate.data(TableRole.ROW_ID) == selected_id:
                return row
        return -1

    @staticmethod
    def _workspace_row_revision(table: QTableWidget, row: int) -> TableRevision:
        material = "|".join(
            table.item(row, column).text() if table.item(row, column) is not None else ""
            for column in range(table.columnCount())
        )
        return TableRevision(hashlib.sha256(material.encode("utf-8")).hexdigest())

    def _refresh_workspace_row_roles(
        self,
        table: QTableWidget,
        row: int,
        namespace: str,
    ) -> None:
        first = table.item(row, 0)
        row_id = first.data(TableRole.ROW_ID) if first is not None else None
        if not isinstance(row_id, TableRowId) or row_id.namespace != namespace:
            return
        revision = self._workspace_row_revision(table, row)
        for column in range(table.columnCount()):
            item = table.item(row, column)
            if item is not None:
                item.setData(TableRole.ROW_REVISION, revision)

    def show_brands(self, cat):
        self.brand_list.clear()
        self.brand_list.addItems(self.brands.get(cat, []))

    def add_brand(self):
        cat = (
            self.brand_categories.currentItem().text()
            if self.brand_categories.currentItem()
            else ""
        )
        name = self.new_brand.text().strip()
        if cat and name and name not in self.brands[cat]:
            self.brands[cat].append(name)
            self.brands[cat].sort()
            (PROJECT_ROOT / "data" / "brands_ru.json").write_text(
                json.dumps(self.brands, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.show_brands(cat)
            self.new_brand.clear()

    def run_readiness(self):
        result = check_application(self.generated_files)
        self.readiness_table.setRowCount(len(result["checks"]))
        for r, x in enumerate(result["checks"]):
            for c, v in enumerate([x["name"], "Да" if x["ok"] else "Нет", x["severity"]]):
                self.readiness_table.setItem(r, c, QTableWidgetItem(v))
        self.readiness_status.setText(f"<h3>{result['status']}</h3>")

    def add_platform(self):
        name = self.platform_name.text().strip()
        endpoint = self.platform_endpoint.text().strip()
        if not name or not endpoint:
            return
        x = PlatformConnection(
            name=name,
            protocol=self.platform_protocol.currentText(),
            endpoint=endpoint,
            username=self.platform_user.text().strip(),
            enabled=True,
        )
        idx = next(
            (i for i, v in enumerate(self.prefs.platforms) if v.name.lower() == name.lower()), None
        )
        if idx is None:
            self.prefs.platforms.append(x)
        else:
            self.prefs.platforms[idx] = x
        self.platform_secret.clear()
        self.store.save(self.prefs)
        self.refresh_platforms()

    def remove_platform(self):
        r = self.platform_table.currentRow()
        if r < 0:
            return
        n = self.platform_table.item(r, 0).text()
        self.prefs.platforms = [x for x in self.prefs.platforms if x.name != n]
        self.store.save(self.prefs)
        self.refresh_platforms()

    def platform_selected(self, row, col):
        x = self.prefs.platforms[row]
        self.platform_name.setText(x.name)
        self.platform_protocol.setCurrentText(x.protocol)
        self.platform_endpoint.setText(x.endpoint)
        self.platform_user.setText(x.username)

    def test_platform(self):
        r = self.platform_table.currentRow()
        if r < 0:
            return
        x = self.prefs.platforms[r]
        result = ManualConnectorTester.test(x)
        self.platform_table.setItem(
            r,
            5,
            QTableWidgetItem("Доступно" if result.get("ok") else "Ошибка проверки соединения"),
        )

    def refresh_platforms(self):
        self.platform_table.setRowCount(len(self.prefs.platforms))
        for r, x in enumerate(self.prefs.platforms):
            for c, v in enumerate(
                [
                    x.name,
                    x.protocol,
                    x.endpoint,
                    x.username,
                    "Да" if x.enabled else "Нет",
                    "Не проверено",
                ]
            ):
                self.platform_table.setItem(r, c, QTableWidgetItem(str(v)))

    def replace_template(self, row):
        src, _ = QFileDialog.getOpenFileName(self, "Новый шаблон", "", "Word (*.docx)")
        if src:
            self.store.import_template(Path(src), TEMPLATE_NAMES[row])
            self.refresh_templates()

    def refresh_templates(self):
        d = Path(self.prefs.template_dir)
        self.template_dir_label.setText(f"Папка шаблонов: {d}")
        for r, n in enumerate(TEMPLATE_NAMES):
            self.template_table.setItem(
                r, 1, QTableWidgetItem(str(d / n) if (d / n).exists() else "Файл отсутствует")
            )

    def _database_services(self):
        paths = PathManager.instance().ensure_directories()
        backups = BackupManager(paths.database_file, paths.backups_dir)
        return paths, backups, DatabaseMaintenanceService(get_engine(), backups)

    def _diagnostics_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        controls = QHBoxLayout()
        for text, slot in [
            ("Обновить диагностику", self.refresh_database_diagnostics),
            ("Создать backup", self.create_database_backup),
            ("Восстановить", self.restore_database_backup),
            ("Оптимизировать", self.optimize_database),
            ("Экспортировать БД", self.export_database),
        ]:
            button = QPushButton(text)
            button.clicked.connect(slot)
            controls.addWidget(button)
        controls.addStretch()
        layout.addLayout(controls)
        self.db_status = QLabel()
        self.db_status.setWordWrap(True)
        layout.addWidget(self.db_status)
        self.db_diagnostics_table = QTableWidget(0, 2)
        self.db_diagnostics_table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.db_diagnostics_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.db_diagnostics_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.db_diagnostics_table)
        QTimer.singleShot(0, self.refresh_database_diagnostics)
        return widget

    def refresh_database_diagnostics(self):
        try:
            _, backups, _ = self._database_services()
            report = DiagnosticsService(get_engine(), backups).collect()
            values = [
                ("Состояние", "OK" if report.healthy else "ТРЕБУЕТ ВНИМАНИЯ"),
                ("Integrity check", report.integrity),
                ("Journal mode", report.journal_mode),
                ("Foreign keys", "Включены" if report.foreign_keys else "Отключены"),
                ("Версия схемы", f"{report.schema_version} / {report.expected_schema_version}"),
                ("Путь к базе", report.database_path),
                ("Размер базы", f"{report.database_size / 1024 / 1024:.2f} МБ"),
                ("Таблиц", str(report.table_count)),
                ("Индексов", str(report.index_count)),
                ("Всего записей", str(report.total_rows)),
                ("Последний backup", report.latest_backup or "Нет"),
                (
                    "Backup корректен",
                    "Да"
                    if report.latest_backup_valid
                    else ("Нет" if report.latest_backup_valid is False else "Не проверялся"),
                ),
                ("Проблемы", "\n".join(report.issues) if report.issues else "Не обнаружены"),
            ]
            self.db_diagnostics_table.setRowCount(len(values))
            for row, (name, value) in enumerate(values):
                self.db_diagnostics_table.setItem(row, 0, QTableWidgetItem(name))
                self.db_diagnostics_table.setItem(row, 1, QTableWidgetItem(value))
            self.db_status.setProperty("semanticTone", "success" if report.healthy else "danger")
            self.db_status.setText(
                "База данных исправна" if report.healthy else "Обнаружены проблемы базы данных"
            )
            self.db_status.style().unpolish(self.db_status)
            self.db_status.style().polish(self.db_status)
        except Exception as exc:
            self.db_status.setProperty("semanticTone", "danger")
            self.db_status.setText(f"Ошибка диагностики ({type(exc).__name__})")
            self.db_status.style().unpolish(self.db_status)
            self.db_status.style().polish(self.db_status)

    def create_database_backup(self):
        try:
            _, _, maintenance = self._database_services()
            record = maintenance.create_backup("manual")
            QMessageBox.information(self, "Резервная копия", f"Создан файл:\n{record.path}")
            self.refresh_database_diagnostics()
        except Exception as exc:
            QMessageBox.critical(self, "Резервная копия", str(exc))

    def restore_database_backup(self):
        paths, _, maintenance = self._database_services()
        source, _ = QFileDialog.getOpenFileName(
            self, "Выберите резервную копию", str(paths.backups_dir), "SQLite (*.db)"
        )
        if not source:
            return
        answer = QMessageBox.question(
            self,
            "Восстановление",
            "Текущая база будет заменена. Перед заменой создастся страховочная копия. Продолжить?",
        )
        if answer != QMessageBox.Yes:
            return
        try:
            maintenance.restore(Path(source))
            QMessageBox.information(
                self,
                "Восстановление",
                "База восстановлена. Перезапустите программу для повторного подключения.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Восстановление", str(exc))

    def optimize_database(self):
        try:
            _, _, maintenance = self._database_services()
            maintenance.optimize()
            QMessageBox.information(
                self, "Обслуживание", "VACUUM, ANALYZE и PRAGMA optimize выполнены."
            )
            self.refresh_database_diagnostics()
        except Exception as exc:
            QMessageBox.critical(self, "Обслуживание", str(exc))

    def export_database(self):
        paths, _, maintenance = self._database_services()
        destination, _ = QFileDialog.getSaveFileName(
            self, "Экспорт базы", str(paths.exports_dir / "corteris_database.db"), "SQLite (*.db)"
        )
        if not destination:
            return
        try:
            output = maintenance.export_database(Path(destination))
            QMessageBox.information(self, "Экспорт", f"База экспортирована:\n{output}")
        except Exception as exc:
            QMessageBox.critical(self, "Экспорт", str(exc))


__all__ = [
    "LEGACY_PLATFORM_COMPATIBILITY_NOTICE",
    "LEGACY_PLATFORM_CREDENTIAL_NOTICE",
    "LEGACY_PLATFORM_PROVIDER_ACTION_TEXT",
    "TenderWorkspacePage",
]
