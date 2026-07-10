import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.session import init_database
from app.repositories.tenders import TenderRepository
from app.tender_analysis.engine import AnalysisEngine
from app.estimates.calculator import EstimateCalculator,EstimateItem
from app.document_generation.generator import DocumentGenerator
DB=Path('demo_corteris.db').resolve(); init_database(f'sqlite:///{DB.as_posix()}'); repo=TenderRepository(); t=repo.create(number='DEMO-001',title='Монтаж системы видеонаблюдения и СКУД',customer='Демонстрационный заказчик',region='Москва',law='44-ФЗ',nmck=1500000)
repo.add_document(t.id,name='Техническое задание.txt',path='demo',kind='Техническое задание',text='Требуется поставить 12 шт. камер Hikvision, 2 шт. коммутатора и 4 шт. считывателя. Требуется авторизационное письмо производителя.',page_count=3)
repo.add_document(t.id,name='Проект договора.txt',path='demo',kind='Проект договора',text='Оплата производится в течение 90 календарных дней. Дополнительные работы выполняются без увеличения цены договора.',page_count=5)
est=EstimateCalculator().calculate([EstimateItem('IP-камеры',12,'шт.',15000,25),EstimateItem('Коммутаторы PoE',2,'шт.',30000,20),EstimateItem('Монтаж и ПНР',1,'компл.',180000,30)])
rep=AnalysisEngine().analyze(t.id,est['total'],est['cost_total']); gen=DocumentGenerator(); print(gen.commercial_proposal(t.id,rep,est)); print(gen.compliance_table(t.id,rep)); print(gen.clarification_request(t.id,rep)); print(rep)
