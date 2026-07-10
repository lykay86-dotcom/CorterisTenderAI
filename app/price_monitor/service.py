from __future__ import annotations
from .models import TenderRequirement, MatchResult
from .repository import PriceOfferRepository
from .matcher import RequirementMatcher

class PriceSearchService:
    def __init__(self, repository: PriceOfferRepository):
        self.repository=repository; self.matcher=RequirementMatcher()

    def search(self, requirement: TenderRequirement, vat_percent: float=22.0, only_compliant: bool=True) -> list[MatchResult]:
        results=[]
        for offer in self.repository.offers:
            hay=f"{offer.category} {offer.brand} {offer.model} {offer.article}".lower()
            query=requirement.name.lower().strip()
            if requirement.required_model and requirement.required_model.lower() not in hay and not requirement.allow_equivalent: continue
            if requirement.required_brand and requirement.required_brand.lower() not in hay and not requirement.allow_equivalent: continue
            if query and not any(t in hay for t in query.split() if len(t)>2): continue
            result=self.matcher.match(requirement,offer,vat_percent)
            if result.compliant or not only_compliant: results.append(result)
        return sorted(results,key=lambda x:x.rank_key)

    def cheapest(self, requirement: TenderRequirement, vat_percent: float=22.0) -> MatchResult | None:
        results=self.search(requirement,vat_percent,True)
        return results[0] if results else None

    def selection_variants(self, requirement: TenderRequirement, vat_percent: float=22.0) -> dict[str, MatchResult | None]:
        compliant=self.search(requirement,vat_percent,True)
        if not compliant: return {"cheapest":None,"optimal":None,"reliable":None,"exact":None}
        cheapest=min(compliant,key=lambda x:x.total["total_net"])
        exact=next((x for x in compliant if requirement.required_model and x.offer.model.lower()==requirement.required_model.lower()),None)
        optimal=max(compliant,key=lambda x:(x.confidence*2 + min(x.offer.warranty_months,60) + (20 if x.offer.official_supply else 0) - x.offer.lead_time_days/2) / max(x.total["total_net"],1)*1_000_000)
        reliable=max(compliant,key=lambda x:(x.offer.official_supply,x.offer.certificate_available,x.offer.warranty_months,-x.offer.lead_time_days,-x.total["total_net"]))
        return {"cheapest":cheapest,"optimal":optimal,"reliable":reliable,"exact":exact}
