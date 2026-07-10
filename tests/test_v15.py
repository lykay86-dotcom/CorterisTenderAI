from pathlib import Path
from app.price_monitor import PriceOffer, PriceOfferRepository, PriceSearchService, TenderRequirement


def test_total_cost_accounts_for_delivery_and_vat():
    offer=PriceOffer(supplier='A',brand='X',model='M',unit_price=12200,vat_included=True,vat_percent=22,delivery_cost=1220)
    total=offer.total_cost(2,22)
    assert total['goods_net']==20000
    assert total['delivery_net']==1000
    assert total['total_gross']==25620


def test_only_compliant_offer_is_selected(tmp_path: Path):
    repo=PriceOfferRepository(tmp_path/'offers.json')
    repo.upsert(PriceOffer(supplier='A',brand='Demo',model='Good',unit_price=10000,lead_time_days=2,warranty_months=36,characteristics={'ИК':'40 м'}))
    repo.upsert(PriceOffer(supplier='B',brand='Demo',model='Bad',unit_price=8000,lead_time_days=2,warranty_months=36,characteristics={'ИК':'20 м'}))
    req=TenderRequirement(name='Demo',quantity=1,max_lead_time_days=5,min_warranty_months=24,required_characteristics={'ИК':'не менее 30 м'})
    best=PriceSearchService(repo).cheapest(req)
    assert best is not None
    assert best.offer.model=='Good'


def test_minimum_order_is_included():
    offer=PriceOffer(supplier='A',brand='X',model='M',unit_price=1000,vat_included=False,minimum_order_qty=10)
    total=offer.total_cost(3,22)
    assert total['billable_quantity']==10
    assert total['total_net']==10000


def test_import_csv(tmp_path: Path):
    path=tmp_path/'p.csv'
    path.write_text('Поставщик,Бренд,Модель,Цена,НДС включен\nA,X,M,1234,Да\n',encoding='utf-8')
    repo=PriceOfferRepository(tmp_path/'o.json')
    assert repo.import_file(path)==1
    assert repo.offers[0].unit_price==1234
