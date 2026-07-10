from __future__ import annotations
from pathlib import Path
from datetime import date
import shutil
from docx import Document
from openpyxl import Workbook
from app.config.settings import get_settings
from app.company.profile import current_company_profile
from app.config.user_settings import UserSettingsStore

class DocumentGenerator:
    def __init__(self):
        self.company = current_company_profile()
        prefs = UserSettingsStore().load()
        self.template_dir = Path(prefs.template_dir) if prefs.template_dir else Path(__file__).resolve().parents[2] / 'templates' / 'company'

    def output_dir(self, tender_id: int) -> Path:
        p = get_settings().data_dir / 'outputs' / str(tender_id)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _replace(self, doc: Document, values: dict[str, str]) -> None:
        def apply(paragraph):
            full = ''.join(run.text for run in paragraph.runs)
            changed = full
            for key, value in values.items():
                changed = changed.replace(key, value)
            if changed != full:
                if paragraph.runs:
                    paragraph.runs[0].text = changed
                    for run in paragraph.runs[1:]: run.text = ''
                else:
                    paragraph.text = changed
        for p in doc.paragraphs: apply(p)
        for section in doc.sections:
            for p in section.header.paragraphs: apply(p)
            for table in section.header.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs: apply(p)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs: apply(p)

    def commercial_proposal(self, tender_id: int, report: dict, estimate: dict) -> Path:
        p = self.output_dir(tender_id) / 'Коммерческое_предложение.docx'
        template = self.template_dir / '01_Коммерческое_предложение.docx'
        doc = Document(template) if template.exists() else Document()
        values = {
            '[ТЕКУЩАЯ ДАТА]': date.today().strftime('%d.%m.%Y'),
            '[АВТОМАТИЧЕСКИЙ НОМЕР]': f'КП-{tender_id:05d}',
            '[НАИМЕНОВАНИЕ ЗАКАЗЧИКА]': report['tender'].get('customer') or 'Не указан',
            '[НОМЕР И НАЗВАНИЕ ЗАКУПКИ]': f"{report['tender'].get('number','')} {report['tender']['title']}",
            '[НАИМЕНОВАНИЕ И АДРЕС ОБЪЕКТА]': report['tender']['title'],
            '[СУММА]': f"{estimate['total']:,.2f}",
            '[СТАВКА]': str(estimate['vat_percent']),
            '[СУММА НДС]': f"{estimate['vat']:,.2f}",
            '[СРОК]': 'согласно документации закупки',
            '[УСЛОВИЯ]': 'согласно проекту договора после проверки рисков',
        }
        self._replace(doc, values)
        doc.add_heading('Расчёт стоимости', level=1)
        table = doc.add_table(rows=1, cols=5)
        for i, text in enumerate(['Наименование','Количество','Ед.','Цена без НДС','Сумма без НДС']):
            table.rows[0].cells[i].text = text
        for item in estimate['items']:
            c = table.add_row().cells
            c[0].text = item['name']; c[1].text = str(item['quantity']); c[2].text = item['unit']
            c[3].text = f"{item['price']/item['quantity']:,.2f}" if item['quantity'] else '0'
            c[4].text = f"{item['price']:,.2f}"
        doc.add_paragraph(f"Минимальная безопасная цена с НДС: {estimate['minimum_safe_price_with_vat']:,.2f} руб.")
        doc.add_paragraph(f"Расчётная прибыль: {estimate['profit']:,.2f} руб.; рентабельность по выручке: {estimate['margin_percent']:.2f}%.")
        doc.add_paragraph(f"Рекомендация системы: {report['recommendation']}")
        doc.save(p)
        return p

    def compliance_table(self, tender_id: int, report: dict) -> Path:
        p = self.output_dir(tender_id) / 'Таблица_соответствия.xlsx'
        wb = Workbook(); ws = wb.active; ws.title = 'Соответствие'
        ws.append(['Требование заказчика','Предлагаемое решение','Соответствие','Подтверждение','Комментарий'])
        for e in report.get('equipment', []):
            ws.append([e['name'], f"Подлежит подбору, {e['quantity']} {e['unit']}", 'Требуется проверка', 'Паспорт/сертификат', 'Не предлагать несоответствующие аналоги'])
        if not report.get('equipment'):
            ws.append(['Перечень оборудования', 'В документации недостаточно информации', 'Требуется уточнение', '', 'Направить запрос на разъяснение'])
        ws.freeze_panes = 'A2'
        for width, col in zip([35,45,22,28,42], 'ABCDE'): ws.column_dimensions[col].width = width
        wb.save(p); return p

    def clarification_request(self, tender_id: int, report: dict) -> Path:
        p = self.output_dir(tender_id) / 'Запрос_на_разъяснение.docx'
        template = self.template_dir / '03_Запрос_на_разъяснение.docx'
        doc = Document(template) if template.exists() else Document()
        self._replace(doc, {
            '[ТЕКУЩАЯ ДАТА]': date.today().strftime('%d.%m.%Y'),
            '[АВТОМАТИЧЕСКИЙ НОМЕР]': f'ЗР-{tender_id:05d}',
            '[НАИМЕНОВАНИЕ ЗАКАЗЧИКА]': report['tender'].get('customer') or 'Не указан',
            '[НОМЕР И НАЗВАНИЕ ЗАКУПКИ]': f"{report['tender'].get('number','')} {report['tender']['title']}",
            '[НАИМЕНОВАНИЕ И АДРЕС ОБЪЕКТА]': report['tender']['title'],
        })
        risks = report.get('license_requirements', []) + report.get('experience_requirements', []) + report.get('legal_risks', []) + report.get('competition_risks', [])
        doc.add_heading('Автоматически выявленные вопросы', level=1)
        if not risks:
            doc.add_paragraph('Автоматически значимые вопросы не выявлены. Перед направлением требуется ручная проверка полного комплекта документации.')
        for i, risk in enumerate(risks, 1):
            doc.add_paragraph(f"{i}. Просим разъяснить требование «{risk['name']}». Найденный фрагмент: {risk.get('quote','')[:350]}")
        doc.save(p); return p

    def package(self, tender_id: int, report: dict, estimate: dict) -> Path:
        out = self.output_dir(tender_id)
        self.commercial_proposal(tender_id, report, estimate)
        self.compliance_table(tender_id, report)
        self.clarification_request(tender_id, report)
        archive = shutil.make_archive(str(out / f'Пакет_заявки_{tender_id}'), 'zip', out)
        return Path(archive)
