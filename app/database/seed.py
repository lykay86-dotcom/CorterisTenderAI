"""Начальные данные новой локальной базы."""
from __future__ import annotations

from decimal import Decimal

from .models import Company
from .unit_of_work import UnitOfWork


DEFAULT_SETTINGS: dict[str, object] = {
    "finance.vat_rate": 22.0,
    "finance.profit_mode": "markup",
    "finance.profit_percent": 30.0,
    "finance.risk_reserve_percent": 5.0,
    "database.schema_version": 1,
}


def seed_default_data() -> Company:
    """Идемпотентно создаёт ООО «КОРТЕРИС» и системные настройки."""
    with UnitOfWork() as uow:
        company = uow.companies.get_by_inn("9701327346")
        if company is None:
            company = uow.companies.add(
                Company(
                    full_name='Общество с ограниченной ответственностью «КОРТЕРИС»',
                    short_name='ООО «КОРТЕРИС»',
                    inn="9701327346",
                    kpp="770101001",
                    ogrn="1267700130092",
                    legal_address=(
                        "105066, г. Москва, вн.тер.г. муниципальный округ Басманный, "
                        "ул. Доброслободская, д. 7/1, стр. 3, помещ. 3/2"
                    ),
                    bank_name="ПАО Сбербанк",
                    bank_bik="044525225",
                    settlement_account="40702810638720041873",
                    correspondent_account="30101810400000000225",
                    director_name="Лукин Юрий Юрьевич",
                    phone="+7 (495) 150-04-03",
                    email="info@corteris.ru",
                    website="www.corteris.ru",
                    tax_system="ОСНО",
                    vat_rate=Decimal("22.00"),
                    profit_mode="markup",
                    profit_percent=Decimal("30.00"),
                    risk_reserve_percent=Decimal("5.00"),
                    licenses=[],
                )
            )
            uow.audit.record(
                "company.created",
                entity_type="Company",
                entity_id=company.id,
                summary="Создан профиль ООО «КОРТЕРИС»",
                after_data=company.as_dict(),
            )

        for key, value in DEFAULT_SETTINGS.items():
            uow.settings.set_value(key, value, description="Начальная настройка Sprint 1.2.1")
        return company
