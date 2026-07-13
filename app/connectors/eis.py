from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse, parse_qs


@dataclass(slots=True)
class EISReference:
    purchase_number: str
    source_url: str


def parse_eis_reference(value: str) -> EISReference:
    value = value.strip()
    if re.fullmatch(r"\d{10,25}", value):
        return EISReference(
            value,
            f"https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber={value}",
        )
    parsed = urlparse(value)
    if parsed.netloc and "zakupki.gov.ru" not in parsed.netloc.lower():
        raise ValueError("Ссылка не относится к ЕИС")
    qs = parse_qs(parsed.query)
    number = (qs.get("regNumber") or qs.get("purchaseNumber") or [""])[0]
    if not number:
        match = re.search(r"(?<!\d)(\d{10,25})(?!\d)", value)
        number = match.group(1) if match else ""
    if not number:
        raise ValueError("Не удалось определить номер закупки")
    return EISReference(number, value)


class EISConnector:
    """Безопасный локальный коннектор 1.4.

    Нормализует номер/ссылку и формирует карточку для ручной загрузки.
    Прямая автоматическая загрузка включается только через документированный
    официальный интерфейс, заданный пользователем в настройках.
    """

    def create_stub(self, value: str) -> dict[str, str]:
        ref = parse_eis_reference(value)
        return {
            "number": ref.purchase_number,
            "platform": "ЕИС",
            "url": ref.source_url,
            "status": "Требуется загрузка открытых данных или архива документов",
        }
