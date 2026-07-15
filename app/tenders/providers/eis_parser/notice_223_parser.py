"""Strict adapter for public 223-FZ notice detail pages."""

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


PARSER_VERSION = "eis-notice-223-v1"


def parse_notice_223(html: str, *, source_url: str) -> EisTenderDetails:
    fields = extract_fields(html)
    classifications = all_values(fields, "ОКПД2")
    lot_names = all_values(fields, "Лоты", "Лот")
    details = EisTenderDetails(
        procurement_number=first(fields, "Номер закупки", "Реестровый номер") or "",
        title=first(fields, "Наименование закупки", "Предмет закупки") or "",
        source_url=source_url,
        law=EisLawType.FZ_223,
        customer_name=first(fields, "Заказчик", "Организатор") or "",
        customer_inn=first(fields, "ИНН заказчика", "ИНН"),
        customer_kpp=first(fields, "КПП заказчика", "КПП"),
        organization_code=first(fields, "Внутренний идентификатор", "organizationCode"),
        customer_address=first(fields, "Адрес заказчика", "Место нахождения"),
        contact_name=first(fields, "Контактное лицо"),
        contact_phone=first(fields, "Телефон"),
        contact_email=first(fields, "Электронная почта", "E-mail"),
        region=first(fields, "Регион"),
        delivery_place=first(fields, "Место поставки"),
        bid_security=parse_decimal(first(fields, "Обеспечение заявки")),
        contract_security=parse_decimal(first(fields, "Обеспечение исполнения договора")),
        price=parse_decimal(first(fields, "Начальная максимальная цена", "Цена")),
        published_at=parse_datetime(first(fields, "Дата публикации", "Размещено")),
        updated_at=parse_datetime(first(fields, "Дата изменения")),
        application_deadline=parse_datetime(first(fields, "Окончание подачи заявок")),
        status=first(fields, "Статус"),
        procedure_type=first(fields, "Способ закупки"),
        okpd2_codes=extract_codes(classifications, r"\b\d{2}(?:\.\d{1,3}){1,3}\b"),
        requirements=all_values(fields, "Требования"),
        restrictions=all_values(fields, "Ограничения"),
        lots=tuple({"name": name} for name in lot_names),
        parser_version=PARSER_VERSION,
    )
    return validate_details(details)


__all__ = ["PARSER_VERSION", "parse_notice_223"]
