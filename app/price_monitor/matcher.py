from __future__ import annotations
import re
from .models import PriceOffer, TenderRequirement, MatchResult

class RequirementMatcher:
    @staticmethod
    def _norm(value: object) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower().replace(",", "."))

    @staticmethod
    def _number(value: object) -> float | None:
        match=re.search(r"-?\d+(?:\.\d+)?", RequirementMatcher._norm(value))
        return float(match.group()) if match else None

    def characteristic_matches(self, required: str, actual: str) -> bool:
        req=self._norm(required); act=self._norm(actual)
        req_num=self._number(req); act_num=self._number(act)
        if req_num is not None and act_num is not None:
            if any(x in req for x in ["не менее", ">=", "от "]): return act_num >= req_num
            if any(x in req for x in ["не более", "<=", "до "]): return act_num <= req_num
            return abs(act_num-req_num) < 1e-9 or req in act
        alternatives=[x.strip() for x in re.split(r"\||/| или ",req) if x.strip()]
        return any(x in act or act in x for x in alternatives)

    def match(self, requirement: TenderRequirement, offer: PriceOffer, vat_percent: float=22.0) -> MatchResult:
        reasons=[]; notes=[]; passed=0; total_checks=0
        combined=self._norm(f"{offer.brand} {offer.model} {offer.article} {offer.category}")
        for token in [x for x in self._norm(requirement.name).split() if len(x)>2]:
            total_checks += 1
            if token in combined: passed += 1
        if requirement.required_brand:
            total_checks += 1
            if self._norm(requirement.required_brand)==self._norm(offer.brand): passed += 1
            elif not requirement.allow_equivalent: reasons.append("Не совпадает обязательный бренд")
            else: notes.append("Предложен эквивалент другого бренда")
        if requirement.required_model:
            total_checks += 1
            if self._norm(requirement.required_model)==self._norm(offer.model): passed += 1
            elif not requirement.allow_equivalent: reasons.append("Не совпадает обязательная модель")
        if requirement.max_lead_time_days and offer.lead_time_days > requirement.max_lead_time_days:
            reasons.append("Срок поставки превышает допустимый")
        else: passed += 1; total_checks += 1
        if requirement.min_warranty_months and offer.warranty_months < requirement.min_warranty_months:
            reasons.append("Гарантия меньше требуемой")
        else: passed += 1; total_checks += 1
        if requirement.require_certificate and not offer.certificate_available: reasons.append("Нет подтверждения сертификата")
        if requirement.require_official_supply and not offer.official_supply: reasons.append("Не подтверждена официальная поставка")
        if offer.stock and offer.stock < requirement.quantity: reasons.append("Недостаточный остаток")
        for key,required in requirement.required_characteristics.items():
            total_checks += 1; actual=offer.characteristics.get(key,"")
            if actual and self.characteristic_matches(required,actual): passed += 1
            else: reasons.append(f"Характеристика «{key}» не подтверждена: требуется {required}, найдено {actual or 'нет данных'}")
        confidence=round(100*passed/max(total_checks,1),1)
        return MatchResult(offer,requirement,not reasons,confidence,reasons,notes,offer.total_cost(requirement.quantity,vat_percent))
