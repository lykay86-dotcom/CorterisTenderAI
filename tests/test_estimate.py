from app.estimates.calculator import EstimateCalculator,EstimateItem
def test_estimate():
    r=EstimateCalculator().calculate([EstimateItem('Камера',2,'шт.',10000,20)],vat_percent=22,risk_percent=5)
    assert r['cost_total']==20000
    assert r['total']>r['price_without_vat']
    assert r['vat_percent']==22
