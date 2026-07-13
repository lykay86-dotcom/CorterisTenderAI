from __future__ import annotations
from dataclasses import dataclass, asdict
from app.config.user_settings import UserSettingsStore


@dataclass(slots=True)
class CompanyProfile:
    full_name: str = "ООО «КОРТЕРИС»"
    inn: str = "9701327346"
    kpp: str = "770101001"
    ogrn: str = "1267700130092"
    legal_address: str = ""
    director: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    taxation_system: str = "ОСНО"
    vat_percent: float = 22.0
    licenses: tuple[str, ...] = ()
    sro_memberships: tuple[str, ...] = ()
    confirmed_experience_contracts: int = 0
    minimum_markup_percent: float = 30.0
    minimum_revenue_margin_percent: float = 30.0
    logo_path: str = ""
    signature_path: str = ""
    stamp_path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def current_company_profile() -> CompanyProfile:
    p = UserSettingsStore().load()
    return CompanyProfile(
        full_name=p.company_name,
        inn=p.inn,
        kpp=p.kpp,
        ogrn=p.ogrn,
        legal_address=p.legal_address,
        director=p.director,
        phone=p.phone,
        email=p.email,
        website=p.website,
        taxation_system=p.taxation_system,
        vat_percent=p.vat_percent,
        licenses=tuple(p.licenses),
        sro_memberships=tuple(p.sro_memberships),
        minimum_markup_percent=p.profit_percent,
        minimum_revenue_margin_percent=p.profit_percent,
        logo_path=p.logo_path,
        signature_path=p.signature_path,
        stamp_path=p.stamp_path,
    )


DEFAULT_COMPANY_PROFILE = CompanyProfile()
