"""Strict adapter for public 44-FZ notice detail pages."""

from __future__ import annotations

from app.tenders.providers.eis_parser.detail_common import (
    all_values,
    extract_codes,
    extract_fields,
    first,
    parse_datetime,
    parse_decimal,
)
from app.tenders.providers.eis_parser.models import EisLawType, EisTenderDetails
from app.tenders.providers.eis_parser.validation import validate_details


PARSER_VERSION = "eis-notice-44-v1"


def parse_notice_44(html: str, *, source_url: str) -> EisTenderDetails:
    fields = extract_fields(html)
    classifications = all_values(fields, "ОКПД2", "КТРУ")
    details = EisTenderDetails(
        procurement_number=first(fields, "Номер закупки", "Реестровый номер") or "",
        title=first(fields, "Наименование закупки", "Объект закупки") or "",
        source_url=source_url,
        law=EisLawType.FZ_44,
        customer_name=first(fields, "Заказчик") or "",
        customer_inn=first(fields, "ИНН заказчика", "ИНН"),
        customer_kpp=first(fields, "КПП заказчика", "КПП"),
        organization_code=first(fields, "organizationCode", "Код организации"),
        customer_address=first(fields, "Адрес заказчика", "Место нахождения"),
        contact_name=first(fields, "Контактное лицо"),
        contact_phone=first(fields, "Телефон"),
        contact_email=first(fields, "Электронная почта", "E-mail"),
        region=first(fields, "Регион"),
        delivery_place=first(fields, "Место поставки", "Место выполнения работ"),
        funding_source=first(fields, "Источник финансирования"),
        bid_security=parse_decimal(first(fields, "Обеспечение заявки")),
        contract_security=parse_decimal(first(fields, "Обеспечение исполнения контракта")),
        warranty_security=parse_decimal(first(fields, "Обеспечение гарантийных обязательств")),
        advance_percent=parse_decimal(first(fields, "Аванс"), percent=True),
        price=parse_decimal(first(fields, "Начальная максимальная цена", "НМЦК")),
        published_at=parse_datetime(first(fields, "Дата публикации", "Размещено")),
        updated_at=parse_datetime(first(fields, "Дата изменения")),
        application_deadline=parse_datetime(first(fields, "Окончание подачи заявок")),
        status=first(fields, "Статус"),
        procedure_type=first(fields, "Способ определения поставщика"),
        okpd2_codes=extract_codes(classifications, r"\b\d{2}(?:\.\d{1,3}){1,3}\b"),
        ktru_codes=extract_codes(classifications, r"\b\d{2}(?:\.\d{1,3}){3,5}-\d{6,}\b"),
        requirements=all_values(fields, "Требования"),
        restrictions=all_values(fields, "Ограничения"),
        advantages=all_values(fields, "Преимущества"),
        parser_version=PARSER_VERSION,
    )
    return validate_details(details)


__all__ = ["PARSER_VERSION", "parse_notice_44"]
