from pathlib import Path
from app.database.session import init_database
from app.repositories.tenders import TenderRepository
from app.tender_analysis.engine import AnalysisEngine
def test_analysis(tmp_path:Path):
    init_database(f"sqlite:///{tmp_path/'t.db'}")
    repo=TenderRepository(); t=repo.create(title='Монтаж системы видеонаблюдения',nmck=1000000)
    repo.add_document(t.id,name='ТЗ.txt',path='x',kind='Техническое задание',text='Поставка 10 шт. камер Hikvision. Требуется авторизационное письмо производителя.',page_count=1)
    repo.add_document(t.id,name='Договор.txt',path='y',kind='Проект договора',text='Дополнительные работы выполняются без увеличения цены.',page_count=1)
    r=AnalysisEngine().analyze(t.id,900000,650000)
    assert r['score']>=0
    assert r['competition_risks']
    assert r['legal_risks']
