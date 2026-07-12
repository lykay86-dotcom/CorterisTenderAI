from __future__ import annotations
from pathlib import Path
import json, shutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import *
from app.repositories.tenders import TenderRepository
from app.services.import_service import ImportService
from app.tender_analysis.engine import AnalysisEngine
from app.estimates.calculator import EstimateCalculator,EstimateItem,ProfitMode
from app.estimates.workspace import EstimateRow,totals
from app.document_generation.generator import DocumentGenerator
from app.catalog.price_catalog import PriceCatalog
from app.config.user_settings import UserSettingsStore,PlatformConnection
from app.security.secrets import save_secret,load_secret,delete_secret
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

LICENSE_OPTIONS=['Лицензия МЧС','Лицензия ФСБ','Лицензия Росгвардии','СРО проектирование','СРО строительство']
TEMPLATE_NAMES=['00_Фирменный_бланк_Corteris.docx','01_Коммерческое_предложение.docx','02_Технико_коммерческое_предложение.docx','03_Запрос_на_разъяснение.docx','04_Гарантийное_письмо.docx','05_Письмо_об_отсутствии_лицензий.docx','06_Письмо_о_системе_налогообложения.docx','07_Справка_об_опыте.docx','08_Декларация_соответствия.docx','09_Сопроводительное_письмо.docx','10_Опись_документов.docx','11_Протокол_разногласий.docx','12_Управленческое_заключение.docx']

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('AIBOS Security — Corteris Tender AI 1.2.1'); self.resize(1480,920)
        self.repo=TenderRepository(); self.current_id=None; self.last_report=None; self.last_estimate=None; self.generated_files=[]
        self.store=UserSettingsStore(); self.prefs=self.store.load(); self.catalog=PriceCatalog(Path(__file__).resolve().parents[2]/'data'/'price_catalog.xlsx')
        self.brands=json.loads((Path(__file__).resolve().parents[2]/'data'/'brands_ru.json').read_text(encoding='utf-8'))
        self.price_repo=PriceOfferRepository(Path(__file__).resolve().parents[2]/'data'/'price_offers.json'); self.price_service=PriceSearchService(self.price_repo); self.current_price_results=[]
        self._build(); self._load(); self.refresh()

    def _build(self):
        self.tabs=QTabWidget(); self.setCentralWidget(self.tabs)
        dash=QWidget(); dl=QVBoxLayout(dash); top=QHBoxLayout(); self.logo=QLabel(); self.logo.setMaximumHeight(100); top.addWidget(self.logo); top.addWidget(QLabel('<h2>AIBOS Security — Corteris Tender AI 1.2.1</h2><p>Локальная система анализа и подготовки тендерных заявок</p>')); top.addStretch(); dl.addLayout(top)
        self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(['ID','Номер','Название','НМЦК','Балл','Рекомендация']); self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch); self.table.cellClicked.connect(self.select_row); dl.addWidget(self.table)
        actions=QHBoxLayout();
        for text,slot in [('Создать тендер',self.create_tender_dialog),('Загрузить 10 демо-тендеров',self.load_demo),('Импорт документов',self.import_docs),('Анализировать',self.run_analysis),('Сформировать пакет',self.generate_docs)]:
            b=QPushButton(text); b.clicked.connect(slot); actions.addWidget(b)
        dl.addLayout(actions); self.tabs.addTab(dash,'Панель управления')

        an=QWidget(); al=QVBoxLayout(an); calc=QHBoxLayout(); self.profit_mode=QComboBox(); self.profit_mode.addItem('Наценка к себестоимости',ProfitMode.MARKUP.value); self.profit_mode.addItem('Рентабельность по выручке',ProfitMode.REVENUE_MARGIN.value); self.profit_percent=QDoubleSpinBox(); self.profit_percent.setRange(0,99); self.vat=QDoubleSpinBox(); self.vat.setRange(0,50); self.risk=QDoubleSpinBox(); self.risk.setRange(0,100)
        for label,w in [('Расчёт прибыли',self.profit_mode),('Прибыль, %',self.profit_percent),('НДС, %',self.vat),('Резерв, %',self.risk)]: calc.addWidget(QLabel(label)); calc.addWidget(w)
        al.addLayout(calc); self.output=QTextEdit(); self.output.setReadOnly(True); al.addWidget(self.output); self.tabs.addTab(an,'Анализ тендера')

        self.tabs.addTab(self._estimate_tab(),'Смета')
        self.tabs.addTab(self._catalog_tab(),'Оборудование и бренды')
        self.tabs.addTab(self._readiness_tab(),'Проверка заявки')
        self.tabs.addTab(self._v14_tools_tab(),'Инструменты 1.4')
        self.tabs.addTab(self._price_monitor_tab(),'Мониторинг цен 1.5')
        settings=QTabWidget(); settings.addTab(self._platform_tab(),'Площадки API/RSS/FTP'); settings.addTab(self._ai_tab(),'ChatGPT / ИИ'); settings.addTab(self._company_tab(),'Компания и реквизиты'); settings.addTab(self._rules_tab(),'Лицензии и экономика'); settings.addTab(self._templates_tab(),'Фирменные бланки'); settings.addTab(self._diagnostics_tab(),'Диагностика БД'); self.tabs.addTab(settings,'Настройки')

    def _estimate_tab(self):
        w=QWidget(); l=QVBoxLayout(w); bar=QHBoxLayout();
        for text,slot in [('Добавить строку',self.add_estimate_row),('Из прайса',self.add_from_catalog),('Удалить строку',self.remove_estimate_row),('Пересчитать',self.recalculate_estimate)]:
            b=QPushButton(text); b.clicked.connect(slot); bar.addWidget(b)
        l.addLayout(bar); self.estimate_table=QTableWidget(0,7); self.estimate_table.setHorizontalHeaderLabels(['Наименование','Кол-во','Ед.','Себестоимость','Наценка %','НДС %','Цена с НДС']); self.estimate_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch); l.addWidget(self.estimate_table); self.estimate_totals=QLabel('<b>Итого: 0 ₽</b>'); l.addWidget(self.estimate_totals); return w

    def _catalog_tab(self):
        w=QWidget(); l=QVBoxLayout(w); q=QHBoxLayout(); self.catalog_query=QLineEdit(); self.catalog_query.setPlaceholderText('Поиск по прайсу'); b=QPushButton('Найти'); b.clicked.connect(self.search_catalog); q.addWidget(self.catalog_query); q.addWidget(b); l.addLayout(q); self.catalog_table=QTableWidget(0,6); self.catalog_table.setHorizontalHeaderLabels(['Категория','Позиция','Ед.','Себестоимость','Мин. рынок','Макс. рынок']); self.catalog_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); l.addWidget(self.catalog_table)
        split=QSplitter(); self.brand_categories=QListWidget(); self.brand_list=QListWidget(); self.brand_categories.addItems(self.brands.keys()); self.brand_categories.currentTextChanged.connect(self.show_brands); split.addWidget(self.brand_categories); split.addWidget(self.brand_list); l.addWidget(QLabel('<b>Реестр брендов российского рынка (редактируемый)</b>')); l.addWidget(split); br=QHBoxLayout(); self.new_brand=QLineEdit(); self.new_brand.setPlaceholderText('Добавить бренд в выбранную категорию'); bb=QPushButton('Добавить'); bb.clicked.connect(self.add_brand); br.addWidget(self.new_brand); br.addWidget(bb); l.addLayout(br); return w

    def _readiness_tab(self):
        w=QWidget(); l=QVBoxLayout(w); b=QPushButton('Проверить сформированный пакет'); b.clicked.connect(self.run_readiness); l.addWidget(b); self.readiness_table=QTableWidget(0,3); self.readiness_table.setHorizontalHeaderLabels(['Проверка','Результат','Критичность']); self.readiness_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch); l.addWidget(self.readiness_table); self.readiness_status=QLabel(); l.addWidget(self.readiness_status); return w

    def _v14_tools_tab(self):
        w=QWidget(); l=QVBoxLayout(w)
        eis_box=QGroupBox('Импорт из ЕИС по номеру или ссылке'); ef=QHBoxLayout(eis_box)
        self.eis_input=QLineEdit(); self.eis_input.setPlaceholderText('Номер закупки или ссылка zakupki.gov.ru')
        eb=QPushButton('Создать карточку'); eb.clicked.connect(self.import_eis_reference)
        ef.addWidget(self.eis_input); ef.addWidget(eb); l.addWidget(eis_box)
        cat_box=QGroupBox('Каталог оборудования поставщиков'); cf=QHBoxLayout(cat_box)
        cb=QPushButton('Импортировать прайс CSV/XLSX'); cb.clicked.connect(self.import_equipment_catalog)
        self.equipment_count=QLabel('Позиций: 0'); cf.addWidget(cb); cf.addWidget(self.equipment_count); cf.addStretch(); l.addWidget(cat_box)
        backup_box=QGroupBox('Резервное копирование'); bf=QHBoxLayout(backup_box)
        bb=QPushButton('Создать резервную копию'); bb.clicked.connect(self.create_backup)
        bf.addWidget(bb); bf.addStretch(); l.addWidget(backup_box)
        note=QLabel('OCR Tesseract и структурированный ИИ-анализ включены в ядро. Подключение выполняется через настройки ИИ.')
        note.setWordWrap(True); l.addWidget(note); l.addStretch()
        self.equipment_catalog_v14=EquipmentCatalog(Path(__file__).resolve().parents[2]/'data'/'equipment_catalog.json')
        self.equipment_count.setText(f'Позиций: {len(self.equipment_catalog_v14.items)}')
        return w

    def _price_monitor_tab(self):
        w=QWidget(); l=QVBoxLayout(w)
        form=QGridLayout()
        self.pm_name=QLineEdit(); self.pm_name.setPlaceholderText('Например: IP-камера 4 Мп')
        self.pm_qty=QDoubleSpinBox(); self.pm_qty.setRange(0.01,1_000_000); self.pm_qty.setValue(1)
        self.pm_brand=QLineEdit(); self.pm_brand.setPlaceholderText('Обязательный бренд, если есть')
        self.pm_model=QLineEdit(); self.pm_model.setPlaceholderText('Обязательная модель, если есть')
        self.pm_equiv=QCheckBox('Разрешён эквивалент'); self.pm_equiv.setChecked(True)
        self.pm_days=QSpinBox(); self.pm_days.setRange(0,3650)
        self.pm_warranty=QSpinBox(); self.pm_warranty.setRange(0,240)
        self.pm_cert=QCheckBox('Требуется сертификат')
        self.pm_official=QCheckBox('Только официальная поставка')
        form.addWidget(QLabel('Позиция ТЗ'),0,0); form.addWidget(self.pm_name,0,1,1,3)
        form.addWidget(QLabel('Количество'),1,0); form.addWidget(self.pm_qty,1,1)
        form.addWidget(QLabel('Бренд'),1,2); form.addWidget(self.pm_brand,1,3)
        form.addWidget(QLabel('Модель'),2,0); form.addWidget(self.pm_model,2,1)
        form.addWidget(self.pm_equiv,2,2); form.addWidget(self.pm_cert,2,3)
        form.addWidget(QLabel('Макс. поставка, дней'),3,0); form.addWidget(self.pm_days,3,1)
        form.addWidget(QLabel('Мин. гарантия, мес.'),3,2); form.addWidget(self.pm_warranty,3,3)
        form.addWidget(self.pm_official,4,0,1,2)
        l.addLayout(form)
        buttons=QHBoxLayout()
        for text,slot in [('Импорт прайса поставщика',self.import_price_offers),('Найти минимальную цену',self.search_lowest_price),('Показать все, включая несоответствия',lambda:self.search_lowest_price(False)),('Добавить выбранное в смету',self.add_price_result_to_estimate)]:
            b=QPushButton(text); b.clicked.connect(slot); buttons.addWidget(b)
        l.addLayout(buttons)
        self.pm_table=QTableWidget(0,10)
        self.pm_table.setHorizontalHeaderLabels(['Соответствие','Поставщик','Бренд','Модель','Цена ед.','Доставка','Итого без НДС','Итого с НДС','Срок, дн.','Комментарий'])
        self.pm_table.horizontalHeader().setSectionResizeMode(9,QHeaderView.Stretch)
        l.addWidget(self.pm_table)
        self.pm_summary=QLabel(f'Загружено предложений: {len(self.price_repo.offers)}'); l.addWidget(self.pm_summary)
        return w

    def import_price_offers(self):
        src,_=QFileDialog.getOpenFileName(self,'Прайс или предложения поставщика','','Прайсы (*.xlsx *.xlsm *.csv *.json *.xml)')
        if not src:return
        try:
            count=self.price_repo.import_file(Path(src)); self.pm_summary.setText(f'Загружено предложений: {len(self.price_repo.offers)}')
            QMessageBox.information(self,'Мониторинг цен',f'Импортировано/обновлено предложений: {count}')
        except Exception as exc: QMessageBox.warning(self,'Мониторинг цен',str(exc))

    def _current_requirement(self):
        return TenderRequirement(name=self.pm_name.text().strip(),quantity=self.pm_qty.value(),required_brand=self.pm_brand.text().strip(),required_model=self.pm_model.text().strip(),allow_equivalent=self.pm_equiv.isChecked(),max_lead_time_days=self.pm_days.value(),min_warranty_months=self.pm_warranty.value(),require_certificate=self.pm_cert.isChecked(),require_official_supply=self.pm_official.isChecked())

    def search_lowest_price(self,only_compliant=True):
        requirement=self._current_requirement()
        if not requirement.name:
            QMessageBox.warning(self,'Мониторинг цен','Введите наименование позиции из ТЗ'); return
        self.current_price_results=self.price_service.search(requirement,self.vat.value(),only_compliant)
        self.pm_table.setRowCount(len(self.current_price_results))
        for r,x in enumerate(self.current_price_results):
            comment='; '.join(x.reasons or x.neutral_notes) or 'Полное соответствие'
            values=['Да' if x.compliant else 'Нет',x.offer.supplier,x.offer.brand,x.offer.model,f'{x.offer.unit_price:,.2f}',f'{x.offer.delivery_cost:,.2f}',f'{x.total["total_net"]:,.2f}',f'{x.total["total_gross"]:,.2f}',x.offer.lead_time_days,comment]
            for c,v in enumerate(values): self.pm_table.setItem(r,c,QTableWidgetItem(str(v)))
        cheapest=next((x for x in self.current_price_results if x.compliant),None)
        if cheapest:
            self.pm_summary.setText(f'Минимальная безопасная закупка: {cheapest.total["total_net"]:,.2f} ₽ без НДС — {cheapest.offer.supplier}, {cheapest.offer.brand} {cheapest.offer.model}')
        else:self.pm_summary.setText('Подходящих предложений не найдено. Требуется запрос цены поставщикам.')

    def add_price_result_to_estimate(self):
        row=self.pm_table.currentRow()
        if row<0 or row>=len(self.current_price_results): QMessageBox.warning(self,'Мониторинг цен','Выберите предложение'); return
        result=self.current_price_results[row]
        if not result.compliant:
            QMessageBox.warning(self,'Мониторинг цен','Несоответствующее предложение нельзя автоматически добавить в смету'); return
        self.add_estimate_row(f'{result.offer.brand} {result.offer.model} ({result.offer.supplier})',result.requirement.quantity,result.requirement.unit,result.total['unit_effective_net'])
        self.recalculate_estimate(); self.tabs.setCurrentIndex(2)

    def import_eis_reference(self):
        try:
            data=EISConnector().create_stub(self.eis_input.text())
            QMessageBox.information(self,'ЕИС',json_dumps(data))
        except Exception as exc:
            QMessageBox.warning(self,'ЕИС',str(exc))

    def import_equipment_catalog(self):
        src,_=QFileDialog.getOpenFileName(self,'Прайс поставщика','','Прайсы (*.xlsx *.xlsm *.csv)')
        if not src:return
        try:
            count=self.equipment_catalog_v14.import_file(Path(src)); self.equipment_count.setText(f'Позиций: {len(self.equipment_catalog_v14.items)}')
            QMessageBox.information(self,'Каталог',f'Импортировано строк: {count}')
        except Exception as exc:
            QMessageBox.warning(self,'Каталог',str(exc))

    def create_backup(self):
        folder=QFileDialog.getExistingDirectory(self,'Папка резервных копий')
        if not folder:return
        root=Path(__file__).resolve().parents[2]
        sources=[root/'data',root/'templates',root/'assets']
        db=Path.home()/'.corteris_tender_ai'/'corteris.db'
        if db.exists():sources.append(db)
        output=BackupService().create(Path(folder),sources,{'version':'1.5'})
        QMessageBox.information(self,'Резервная копия',f'Создано: {output}')

    def _platform_tab(self):
        w=QWidget(); l=QVBoxLayout(w); f=QHBoxLayout(); self.platform_name=QLineEdit(); self.platform_name.setPlaceholderText('Название'); self.platform_protocol=QComboBox(); self.platform_protocol.addItems(['API','RSS','FTP','FTPS']); self.platform_endpoint=QLineEdit(); self.platform_endpoint.setPlaceholderText('URL'); self.platform_user=QLineEdit(); self.platform_user.setPlaceholderText('Логин'); self.platform_secret=QLineEdit(); self.platform_secret.setEchoMode(QLineEdit.Password); self.platform_secret.setPlaceholderText('Ключ/пароль');
        for x in [self.platform_name,self.platform_protocol,self.platform_endpoint,self.platform_user,self.platform_secret]:f.addWidget(x)
        l.addLayout(f); r=QHBoxLayout();
        for text,slot in [('Добавить/обновить',self.add_platform),('Удалить',self.remove_platform),('Проверить',self.test_platform)]: b=QPushButton(text); b.clicked.connect(slot); r.addWidget(b)
        l.addLayout(r); self.platform_table=QTableWidget(0,6); self.platform_table.setHorizontalHeaderLabels(['Название','Тип','Адрес','Логин','Включено','Статус']); self.platform_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch); self.platform_table.cellClicked.connect(self.platform_selected); l.addWidget(self.platform_table); return w

    def _ai_tab(self):
        w=QWidget(); f=QFormLayout(w); self.ai_provider=QComboBox(); self.ai_provider.addItems(['OpenAI API','OpenAI-совместимый сервер','Ollama','Отключено']); self.api_key=QLineEdit(); self.api_key.setEchoMode(QLineEdit.Password); self.api_model=QLineEdit(); self.api_url=QLineEdit(); b=QPushButton('Сохранить и проверить'); b.clicked.connect(self.save_preferences); f.addRow('Провайдер',self.ai_provider); f.addRow('API-ключ',self.api_key); f.addRow('Модель',self.api_model); f.addRow('Base URL',self.api_url); f.addRow(b); return w

    def _company_tab(self):
        w=QWidget(); f=QFormLayout(w); self.company_fields={}
        labels=[('company_name','Наименование'),('inn','ИНН'),('kpp','КПП'),('ogrn','ОГРН'),('legal_address','Юридический адрес'),('director','Генеральный директор'),('phone','Телефон'),('email','Email'),('website','Сайт'),('taxation_system','Система налогообложения')]
        for key,label in labels: e=QLineEdit(); self.company_fields[key]=e; f.addRow(label,e)
        self.asset_labels={}
        for kind,label in [('logo','Логотип'),('signature','Подпись'),('stamp','Печать')]:
            row=QHBoxLayout(); q=QLineEdit(); q.setReadOnly(True); self.asset_labels[kind]=q; b=QPushButton('Заменить'); b.clicked.connect(lambda checked=False,k=kind:self.replace_asset(k)); row.addWidget(q); row.addWidget(b); f.addRow(label,row)
        b=QPushButton('Сохранить карточку компании'); b.clicked.connect(self.save_preferences); f.addRow(b); return w

    def _rules_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.license_checks={}
        for name in LICENSE_OPTIONS: c=QCheckBox(name); self.license_checks[name]=c; l.addWidget(c)
        form=QFormLayout(); self.settings_profit_mode=QComboBox(); self.settings_profit_mode.addItem('Наценка к себестоимости',ProfitMode.MARKUP.value); self.settings_profit_mode.addItem('Рентабельность по выручке',ProfitMode.REVENUE_MARGIN.value); self.settings_profit=QDoubleSpinBox(); self.settings_profit.setRange(0,99); self.settings_vat=QDoubleSpinBox(); self.settings_vat.setRange(0,50); self.settings_risk=QDoubleSpinBox(); self.settings_risk.setRange(0,100); form.addRow('Метод',self.settings_profit_mode); form.addRow('Прибыль, %',self.settings_profit); form.addRow('НДС по умолчанию, %',self.settings_vat); form.addRow('Резерв риска, %',self.settings_risk); b=QPushButton('Сохранить'); b.clicked.connect(self.save_preferences); form.addRow(b); l.addLayout(form); return w

    def _templates_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.template_dir_label=QLabel(); l.addWidget(self.template_dir_label); self.template_table=QTableWidget(len(TEMPLATE_NAMES),3); self.template_table.setHorizontalHeaderLabels(['Документ','Текущий файл','Действие']); self.template_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        for r,n in enumerate(TEMPLATE_NAMES): self.template_table.setItem(r,0,QTableWidgetItem(n)); b=QPushButton('Заменить DOCX'); b.clicked.connect(lambda checked=False,row=r:self.replace_template(row)); self.template_table.setCellWidget(r,2,b)
        l.addWidget(self.template_table); return w

    def _load(self):
        p=self.prefs; self.profit_mode.setCurrentIndex(max(self.profit_mode.findData(p.profit_mode),0)); self.profit_percent.setValue(p.profit_percent); self.vat.setValue(p.vat_percent); self.risk.setValue(p.risk_percent); self.settings_profit_mode.setCurrentIndex(max(self.settings_profit_mode.findData(p.profit_mode),0)); self.settings_profit.setValue(p.profit_percent); self.settings_vat.setValue(p.vat_percent); self.settings_risk.setValue(p.risk_percent); self.ai_provider.setCurrentText(p.ai_provider); self.api_model.setText(p.ai_model); self.api_url.setText(p.ai_base_url)
        for k,e in self.company_fields.items(): e.setText(str(getattr(p,k)))
        for kind,q in self.asset_labels.items(): q.setText(getattr(p,f'{kind}_path'))
        for n,c in self.license_checks.items(): c.setChecked(n in p.licenses)
        self.refresh_platforms(); self.refresh_templates(); self._refresh_logo(); self.search_catalog(); self.brand_categories.setCurrentRow(0)

    def _refresh_logo(self):
        p=Path(self.prefs.logo_path)
        if p.exists(): self.logo.setPixmap(QPixmap(str(p)).scaledToHeight(90,Qt.SmoothTransformation))

    def save_preferences(self):
        p=self.prefs; p.profit_mode=self.settings_profit_mode.currentData(); p.profit_percent=self.settings_profit.value(); p.vat_percent=self.settings_vat.value(); p.risk_percent=self.settings_risk.value(); p.ai_provider=self.ai_provider.currentText(); p.ai_model=self.api_model.text().strip(); p.ai_base_url=self.api_url.text().strip(); p.licenses=[n for n,c in self.license_checks.items() if c.isChecked()]
        for k,e in self.company_fields.items(): setattr(p,k,e.text().strip())
        if self.api_key.text().strip(): save_secret('openai_api_key',self.api_key.text().strip()); self.api_key.clear(); self.api_key.setPlaceholderText('Сохранён')
        self.store.save(p); self.profit_mode.setCurrentIndex(max(self.profit_mode.findData(p.profit_mode),0)); self.profit_percent.setValue(p.profit_percent); self.vat.setValue(p.vat_percent); self.risk.setValue(p.risk_percent); QMessageBox.information(self,'Настройки','Настройки сохранены')

    def replace_asset(self,kind):
        src,_=QFileDialog.getOpenFileName(self,'Выберите файл','','Изображения (*.png *.jpg *.jpeg)')
        if not src:return
        target=self.store.import_company_asset(Path(src),kind); setattr(self.prefs,f'{kind}_path',str(target)); self.store.save(self.prefs); self.asset_labels[kind].setText(str(target)); self._refresh_logo()

    def create_tender_dialog(self):
        title,ok=QInputDialog.getText(self,'Новый тендер','Название закупки:');
        if not ok or not title.strip():return
        number,_=QInputDialog.getText(self,'Новый тендер','Номер закупки:'); nmck,ok=QInputDialog.getDouble(self,'Новый тендер','НМЦК:',0,0,10**12,2)
        self.current_id=ImportService().create_tender(title.strip(),number.strip(),' ',nmck); self.refresh()
    def load_demo(self):
        data=json.loads((Path(__file__).resolve().parents[2]/'data'/'demo_tenders.json').read_text(encoding='utf-8'))
        for x in data: ImportService().create_tender(x['title'],x['number'],'demo://',x['nmck'])
        self.refresh(); QMessageBox.information(self,'Демо','Добавлено 10 демонстрационных тендеров')
    def import_docs(self):
        if not self.current_id: QMessageBox.warning(self,'Тендер','Выберите тендер'); return
        p,_=QFileDialog.getOpenFileName(self,'Документ или архив','','Документы (*.zip *.pdf *.docx *.xlsx *.txt *.csv)')
        if p: QMessageBox.information(self,'Импорт',f'Импортировано: {len(ImportService().import_path(self.current_id,Path(p)))}')
    def run_analysis(self):
        if not self.current_id: QMessageBox.warning(self,'Тендер','Выберите тендер'); return
        rows=self._estimate_rows(); items=[EstimateItem(x.name,x.quantity,x.unit,x.cost,x.markup_percent) for x in rows] or [EstimateItem('Оборудование',1,'компл.',100000,self.profit_percent.value())]
        self.last_estimate=EstimateCalculator().calculate(items,vat_percent=self.vat.value(),risk_percent=self.risk.value(),profit_percent=self.profit_percent.value(),profit_mode=self.profit_mode.currentData()); self.last_report=AnalysisEngine().analyze(self.current_id,self.last_estimate['total'],self.last_estimate['protected_cost'],self.last_estimate); self.output.setPlainText(json_dumps(self.last_report)); self.refresh()
    def generate_docs(self):
        if not self.last_report or not self.last_estimate: QMessageBox.warning(self,'Пакет','Сначала выполните анализ'); return
        path=DocumentGenerator().package(self.current_id,self.last_report,self.last_estimate); self.generated_files=[Path(path)]; QMessageBox.information(self,'Пакет',f'Создан архив:\n{path}')
    def refresh(self):
        data=self.repo.list(); self.table.setRowCount(len(data))
        for r,t in enumerate(data):
            for c,v in enumerate([t.id,t.number,t.title,f'{t.nmck:,.2f}',t.score,t.recommendation]):self.table.setItem(r,c,QTableWidgetItem(str(v)))
    def select_row(self,row,col): self.current_id=self.table.item(row,0).text(); self.statusBar().showMessage(f'Выбран тендер ID {self.current_id}')

    def add_estimate_row(self,name='Новая позиция',qty=1,unit='шт.',cost=0):
        r=self.estimate_table.rowCount(); self.estimate_table.insertRow(r)
        vals=[name,qty,unit,cost,self.prefs.profit_percent,self.prefs.vat_percent,0]
        for c,v in enumerate(vals): self.estimate_table.setItem(r,c,QTableWidgetItem(str(v)))
    def add_from_catalog(self):
        row=self.catalog_table.currentRow();
        if row<0: QMessageBox.warning(self,'Прайс','Выберите позицию во вкладке «Оборудование и бренды»'); return
        self.add_estimate_row(self.catalog_table.item(row,1).text(),1,self.catalog_table.item(row,2).text(),float(self.catalog_table.item(row,3).text().replace(' ','').replace(',','.')))
    def remove_estimate_row(self):
        r=self.estimate_table.currentRow();
        if r>=0:self.estimate_table.removeRow(r); self.recalculate_estimate()
    def _estimate_rows(self):
        out=[]
        for r in range(self.estimate_table.rowCount()):
            try: out.append(EstimateRow(self.estimate_table.item(r,0).text(),float(self.estimate_table.item(r,1).text().replace(',','.')),self.estimate_table.item(r,2).text(),float(self.estimate_table.item(r,3).text().replace(' ', '').replace(',','.')),float(self.estimate_table.item(r,4).text().replace(',','.')),float(self.estimate_table.item(r,5).text().replace(',','.'))))
            except Exception: pass
        return out
    def recalculate_estimate(self):
        rows=self._estimate_rows()
        for r,x in enumerate(rows): self.estimate_table.setItem(r,6,QTableWidgetItem(f'{x.price_with_vat:,.2f}'))
        t=totals(rows); self.estimate_totals.setText(f"<b>Себестоимость: {t['cost']:,.2f} ₽ | Прибыль: {t['profit']:,.2f} ₽ | Рентабельность: {t['margin']:.2f}% | Итого с НДС: {t['gross']:,.2f} ₽</b>")
    def search_catalog(self):
        items=self.catalog.search(self.catalog_query.text() if hasattr(self,'catalog_query') else '',100); self.catalog_table.setRowCount(len(items))
        for r,x in enumerate(items):
            for c,v in enumerate([x.category,x.name,x.unit,f'{x.base_cost:.2f}',f'{x.market_min:.2f}',f'{x.market_max:.2f}']):self.catalog_table.setItem(r,c,QTableWidgetItem(str(v)))
    def show_brands(self,cat): self.brand_list.clear(); self.brand_list.addItems(self.brands.get(cat,[]))
    def add_brand(self):
        cat=self.brand_categories.currentItem().text() if self.brand_categories.currentItem() else ''; name=self.new_brand.text().strip()
        if cat and name and name not in self.brands[cat]: self.brands[cat].append(name); self.brands[cat].sort(); (Path(__file__).resolve().parents[2]/'data'/'brands_ru.json').write_text(json.dumps(self.brands,ensure_ascii=False,indent=2),encoding='utf-8'); self.show_brands(cat); self.new_brand.clear()
    def run_readiness(self):
        result=check_application(self.generated_files); self.readiness_table.setRowCount(len(result['checks']))
        for r,x in enumerate(result['checks']):
            for c,v in enumerate([x['name'],'Да' if x['ok'] else 'Нет',x['severity']]):self.readiness_table.setItem(r,c,QTableWidgetItem(v))
        self.readiness_status.setText(f"<h3>{result['status']}</h3>")

    def add_platform(self):
        name=self.platform_name.text().strip(); endpoint=self.platform_endpoint.text().strip()
        if not name or not endpoint:return
        x=PlatformConnection(name=name,protocol=self.platform_protocol.currentText(),endpoint=endpoint,username=self.platform_user.text().strip(),enabled=True); idx=next((i for i,v in enumerate(self.prefs.platforms) if v.name.lower()==name.lower()),None)
        if idx is None:self.prefs.platforms.append(x)
        else:self.prefs.platforms[idx]=x
        if self.platform_secret.text().strip():save_secret(f'platform:{name}',self.platform_secret.text().strip())
        self.store.save(self.prefs); self.refresh_platforms()
    def remove_platform(self):
        r=self.platform_table.currentRow();
        if r<0:return
        n=self.platform_table.item(r,0).text(); self.prefs.platforms=[x for x in self.prefs.platforms if x.name!=n]; delete_secret(f'platform:{n}'); self.store.save(self.prefs); self.refresh_platforms()
    def platform_selected(self,row,col):
        x=self.prefs.platforms[row]; self.platform_name.setText(x.name); self.platform_protocol.setCurrentText(x.protocol); self.platform_endpoint.setText(x.endpoint); self.platform_user.setText(x.username)
    def test_platform(self):
        r=self.platform_table.currentRow();
        if r<0:return
        x=self.prefs.platforms[r]; result=ManualConnectorTester.test(x,password=load_secret(f'platform:{x.name}') or '',api_key=load_secret(f'platform:{x.name}') or ''); self.platform_table.setItem(r,5,QTableWidgetItem('Доступно' if result.get('ok') else result.get('error','Ошибка')))
    def refresh_platforms(self):
        self.platform_table.setRowCount(len(self.prefs.platforms))
        for r,x in enumerate(self.prefs.platforms):
            for c,v in enumerate([x.name,x.protocol,x.endpoint,x.username,'Да' if x.enabled else 'Нет','Не проверено']):self.platform_table.setItem(r,c,QTableWidgetItem(str(v)))
    def replace_template(self,row):
        src,_=QFileDialog.getOpenFileName(self,'Новый шаблон','','Word (*.docx)')
        if src:self.store.import_template(Path(src),TEMPLATE_NAMES[row]);self.refresh_templates()
    def refresh_templates(self):
        d=Path(self.prefs.template_dir); self.template_dir_label.setText(f'Папка шаблонов: {d}')
        for r,n in enumerate(TEMPLATE_NAMES): self.template_table.setItem(r,1,QTableWidgetItem(str(d/n) if (d/n).exists() else 'Файл отсутствует'))

    def _database_services(self):
        paths = PathManager.instance().ensure_directories()
        backups = BackupManager(paths.database_file, paths.backups_dir)
        return paths, backups, DatabaseMaintenanceService(get_engine(), backups)

    def _diagnostics_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        controls = QHBoxLayout()
        for text, slot in [
            ('Обновить диагностику', self.refresh_database_diagnostics),
            ('Создать backup', self.create_database_backup),
            ('Восстановить', self.restore_database_backup),
            ('Оптимизировать', self.optimize_database),
            ('Экспортировать БД', self.export_database),
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
        self.db_diagnostics_table.setHorizontalHeaderLabels(['Параметр', 'Значение'])
        self.db_diagnostics_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.db_diagnostics_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.db_diagnostics_table)
        QTimer.singleShot(0, self.refresh_database_diagnostics)
        return widget

    def refresh_database_diagnostics(self):
        try:
            _, backups, _ = self._database_services()
            report = DiagnosticsService(get_engine(), backups).collect()
            values = [
                ('Состояние', 'OK' if report.healthy else 'ТРЕБУЕТ ВНИМАНИЯ'),
                ('Integrity check', report.integrity),
                ('Journal mode', report.journal_mode),
                ('Foreign keys', 'Включены' if report.foreign_keys else 'Отключены'),
                ('Версия схемы', f'{report.schema_version} / {report.expected_schema_version}'),
                ('Путь к базе', report.database_path),
                ('Размер базы', f'{report.database_size / 1024 / 1024:.2f} МБ'),
                ('Таблиц', str(report.table_count)),
                ('Индексов', str(report.index_count)),
                ('Всего записей', str(report.total_rows)),
                ('Последний backup', report.latest_backup or 'Нет'),
                ('Backup корректен', 'Да' if report.latest_backup_valid else ('Нет' if report.latest_backup_valid is False else 'Не проверялся')),
                ('Проблемы', '\n'.join(report.issues) if report.issues else 'Не обнаружены'),
            ]
            self.db_diagnostics_table.setRowCount(len(values))
            for row, (name, value) in enumerate(values):
                self.db_diagnostics_table.setItem(row, 0, QTableWidgetItem(name))
                self.db_diagnostics_table.setItem(row, 1, QTableWidgetItem(value))
            self.db_status.setText(
                '<h3 style="color:#2e8b57">База данных исправна</h3>'
                if report.healthy else
                '<h3 style="color:#b22222">Обнаружены проблемы базы данных</h3>'
            )
        except Exception as exc:
            self.db_status.setText(f'<h3 style="color:#b22222">Ошибка диагностики: {exc}</h3>')

    def create_database_backup(self):
        try:
            _, _, maintenance = self._database_services()
            record = maintenance.create_backup('manual')
            QMessageBox.information(self, 'Резервная копия', f'Создан файл:\n{record.path}')
            self.refresh_database_diagnostics()
        except Exception as exc:
            QMessageBox.critical(self, 'Резервная копия', str(exc))

    def restore_database_backup(self):
        paths, _, maintenance = self._database_services()
        source, _ = QFileDialog.getOpenFileName(
            self, 'Выберите резервную копию', str(paths.backups_dir), 'SQLite (*.db)'
        )
        if not source:
            return
        answer = QMessageBox.question(
            self, 'Восстановление',
            'Текущая база будет заменена. Перед заменой создастся страховочная копия. Продолжить?'
        )
        if answer != QMessageBox.Yes:
            return
        try:
            maintenance.restore(Path(source))
            QMessageBox.information(
                self, 'Восстановление',
                'База восстановлена. Перезапустите программу для повторного подключения.'
            )
        except Exception as exc:
            QMessageBox.critical(self, 'Восстановление', str(exc))

    def optimize_database(self):
        try:
            _, _, maintenance = self._database_services()
            maintenance.optimize()
            QMessageBox.information(self, 'Обслуживание', 'VACUUM, ANALYZE и PRAGMA optimize выполнены.')
            self.refresh_database_diagnostics()
        except Exception as exc:
            QMessageBox.critical(self, 'Обслуживание', str(exc))

    def export_database(self):
        paths, _, maintenance = self._database_services()
        destination, _ = QFileDialog.getSaveFileName(
            self, 'Экспорт базы', str(paths.exports_dir / 'corteris_database.db'), 'SQLite (*.db)'
        )
        if not destination:
            return
        try:
            output = maintenance.export_database(Path(destination))
            QMessageBox.information(self, 'Экспорт', f'База экспортирована:\n{output}')
        except Exception as exc:
            QMessageBox.critical(self, 'Экспорт', str(exc))

