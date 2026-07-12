"""JSON normalization for Moscow Supplier Portal quote sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from typing import Mapping, Sequence
from urllib.parse import urljoin

from app.tenders.models import (
    TenderCustomer,
    TenderDocument,
    TenderMoney,
    TenderProcedureType,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)
from app.tenders.provider_base import TenderProviderError
from app.tenders.providers.mos_supplier_config import MosSupplierApiConfig

@dataclass(frozen=True, slots=True)
class MosSupplierParsedSearch:
    items: tuple[UnifiedTender, ...]
    total: int | None
    warnings: tuple[str, ...] = ()


class MosSupplierApiParseError(TenderProviderError):
    """Raised when the official API response cannot be normalized."""


class MosSupplierApiParser:
    """Normalize documented quote-session fields and common API envelopes.

    The official documentation describes the semantic fields but the live
    payload can evolve.  The parser therefore accepts stable aliases and
    records unknown payloads in ``raw_metadata`` for diagnostics.
    """

    def __init__(self, config: MosSupplierApiConfig | None = None) -> None:
        self.config = config or MosSupplierApiConfig()

    def parse_search(self, payload: object) -> MosSupplierParsedSearch:
        records, total, warnings = _extract_records(payload)
        items: list[UnifiedTender] = []
        errors: list[str] = []
        for index, record in enumerate(records, start=1):
            try:
                items.append(self.parse_card(record))
            except (ValueError, MosSupplierApiParseError) as exc:
                errors.append(f"Запись {index}: {exc}")
        if records and not items:
            raise MosSupplierApiParseError(
                "Ответ API содержит записи, но ни одна не распознана: "
                + "; ".join(errors[:5])
            )
        if errors:
            warnings = (*warnings, *errors[:20])
        return MosSupplierParsedSearch(
            items=tuple(items),
            total=total,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def parse_card(self, payload: object) -> UnifiedTender:
        record = _unwrap_card(payload)
        if not isinstance(record, Mapping):
            raise MosSupplierApiParseError(
                "Карточка котировочной сессии не является JSON-объектом"
            )

        external_id = _string_value(
            record,
            "id",
            "auctionId",
            "auction.id",
            "Id",
            "ИД КС",
        )
        number = _string_value(
            record,
            "number",
            "auctionNumber",
            "purchaseNumber",
            "registryNumber",
            "code",
            "Номер КС",
        ) or external_id
        title = _string_value(
            record,
            "name",
            "title",
            "auctionName",
            "subject",
            "Наименование КС",
        )
        if not external_id:
            raise MosSupplierApiParseError("не найден ID котировочной сессии")
        if not title:
            raise MosSupplierApiParseError(
                f"котировочная сессия {external_id}: не найдено наименование"
            )

        customer_payload = _mapping_value(
            record,
            "customer",
            "customerInfo",
            "organization",
            "Заказчик",
        )
        customer_name = _string_value(
            customer_payload,
            "name",
            "fullName",
            "shortName",
            "Наименование",
        ) or _string_value(
            record,
            "customerName",
            "organizationName",
            "Наименование заказчика",
        )
        customer_inn = _string_value(
            customer_payload,
            "inn",
            "INN",
            "ИНН",
        ) or _string_value(
            record,
            "customerInn",
            "organizationInn",
            "ИНН заказчика",
        )
        region = _string_value(
            customer_payload,
            "region",
            "regionName",
            "Регион",
        ) or _string_value(
            record,
            "region",
            "regionName",
            "deliveryRegion",
            "Регион",
        )
        customer_name = customer_name or "Заказчик Портала поставщиков"

        price = _decimal_value(
            record,
            "startPrice",
            "initialPrice",
            "initialContractPrice",
            "nmck",
            "price",
            "startprice",
            "НМЦК",
            "Начальная цена",
        )
        published_at = _datetime_value(
            record,
            "publishDate",
            "publicationDate",
            "publishedAt",
            "createDate",
            "datePublished",
            "Дата публикации",
        )
        deadline = _datetime_value(
            record,
            "endDate",
            "applicationEndDate",
            "proposalEndDate",
            "deadline",
            "finishDate",
            "Дата окончания",
        )
        status_text = _string_value(
            record,
            "status.name",
            "statusName",
            "status",
            "auctionStatus",
            "Статус",
        )
        law = _string_value(
            record,
            "law",
            "lawName",
            "purchaseLaw",
            "Федеральный закон",
        )
        description = _string_value(
            record,
            "description",
            "conditions",
            "terms",
            "specification",
            "Условия",
            "Описание",
        )
        source_url = _string_value(
            record,
            "url",
            "auctionUrl",
            "noticeUrl",
            "link",
            "Ссылка",
        ) or self.config.auction_url_template.format(id=external_id)

        documents = self.parse_documents(record)
        codes = _classification_codes(record)
        raw_metadata = {
            "platform_name": "Портал поставщиков Москвы",
            "connection_mode": "official_api_bearer",
            "official_api": True,
            "api_record": dict(record),
        }
        return UnifiedTender(
            source=TenderSource.MOS_SUPPLIER,
            external_id=external_id,
            procurement_number=number,
            title=title,
            customer=TenderCustomer(
                name=customer_name,
                inn=customer_inn,
                region=region,
            ),
            source_url=_absolute_url(
                source_url,
                base_url=self.config.homepage_url,
            ),
            published_at=published_at,
            application_deadline=deadline,
            price=(
                TenderMoney(amount=price, currency="RUB")
                if price is not None and price >= 0
                else None
            ),
            status=_status_from_text(status_text),
            procedure_type=TenderProcedureType.REQUEST_FOR_QUOTATIONS,
            law=law,
            region=region,
            description=description,
            classification_codes=codes,
            tags=("Портал поставщиков Москвы", "котировочная сессия"),
            documents=documents,
            raw_metadata=raw_metadata,
        )

    def parse_documents(
        self,
        payload: Mapping[str, object],
    ) -> tuple[TenderDocument, ...]:
        candidates: list[object] = []
        for path in (
            "documents",
            "files",
            "attachments",
            "auction.documents",
            "auction.files",
            "Документы",
        ):
            value = _path_value(payload, path)
            if isinstance(value, Sequence) and not isinstance(
                value, (str, bytes, bytearray)
            ):
                candidates.extend(value)

        documents: list[TenderDocument] = []
        seen: set[str] = set()
        for index, item in enumerate(candidates, start=1):
            if not isinstance(item, Mapping):
                continue
            document_id = _string_value(
                item,
                "id",
                "fileId",
                "documentId",
                "Id",
            ) or f"document-{index}"
            name = _string_value(
                item,
                "name",
                "fileName",
                "title",
                "originalName",
                "Наименование",
            ) or f"Документ {index}"
            url = _string_value(
                item,
                "url",
                "downloadUrl",
                "fileUrl",
                "link",
                "Ссылка",
            )
            if not url and document_id and document_id != f"document-{index}":
                url = self.config.file_download_url_template.format(
                    id=document_id
                )
            if not url:
                continue
            absolute = _absolute_url(url, base_url=self.config.homepage_url)
            identity = absolute.casefold()
            if identity in seen:
                continue
            seen.add(identity)
            documents.append(
                TenderDocument(
                    id=document_id,
                    name=name,
                    url=absolute,
                    mime_type=_string_value(
                        item,
                        "mimeType",
                        "contentType",
                        "type",
                    ),
                    size_bytes=_int_value(
                        item,
                        "size",
                        "sizeBytes",
                        "fileSize",
                    ),
                    published_at=_datetime_value(
                        item,
                        "publishedAt",
                        "createDate",
                        "uploadDate",
                    ),
                    checksum_sha256=_string_value(
                        item,
                        "sha256",
                        "checksum",
                        "hash",
                    ),
                )
            )
        return tuple(documents)


def _extract_records(
    payload: object,
) -> tuple[tuple[Mapping[str, object], ...], int | None, tuple[str, ...]]:
    if isinstance(payload, Sequence) and not isinstance(
        payload, (str, bytes, bytearray)
    ):
        return (
            tuple(item for item in payload if isinstance(item, Mapping)),
            len(payload),
            (),
        )
    if not isinstance(payload, Mapping):
        raise MosSupplierApiParseError(
            "Ответ поиска API не является JSON-объектом или массивом"
        )

    total = _int_value(
        payload,
        "total",
        "totalCount",
        "count",
        "recordsTotal",
        "result.total",
        "result.totalCount",
        "data.total",
        "data.totalCount",
    )
    for path in (
        "items",
        "records",
        "auctions",
        "list",
        "result.items",
        "result.records",
        "result.auctions",
        "result.data",
        "data.items",
        "data.records",
        "data.auctions",
        "data",
    ):
        value = _path_value(payload, path)
        if isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            records = tuple(
                item for item in value if isinstance(item, Mapping)
            )
            return records, total if total is not None else len(records), ()

    if _looks_like_card(payload):
        return (payload,), total if total is not None else 1, ()
    return (), total or 0, (
        "Ответ API не содержит распознанного списка котировочных сессий.",
    )


def _unwrap_card(payload: object) -> object:
    current = payload
    for _ in range(5):
        if not isinstance(current, Mapping):
            break
        if _looks_like_card(current):
            return current
        next_value = None
        for key in ("result", "data", "item", "auction", "value"):
            candidate = _casefold_get(current, key)
            if isinstance(candidate, Mapping):
                next_value = candidate
                break
        if next_value is None:
            break
        current = next_value
    return current


def _looks_like_card(value: Mapping[str, object]) -> bool:
    return bool(
        _string_value(value, "id", "auctionId", "Id", "ИД КС")
        and _string_value(
            value,
            "name",
            "title",
            "auctionName",
            "Наименование КС",
        )
    )


def mos_supplier_api_error_message(payload: object) -> str:
    if not isinstance(payload, Mapping):
        return ""
    success = _casefold_get(payload, "success")
    error = _casefold_get(payload, "error")
    errors = _casefold_get(payload, "errors")
    message = _string_value(
        payload,
        "errorMessage",
        "message",
        "detail",
        "title",
    )
    if success is False or error or errors:
        if message:
            return message
        if isinstance(error, str):
            return error
        return json.dumps(
            error or errors,
            ensure_ascii=False,
            default=str,
        )[:500]
    return ""


def _classification_codes(record: Mapping[str, object]) -> tuple[str, ...]:
    result: list[str] = []
    for path in (
        "okpd2",
        "okpd2Codes",
        "classificationCodes",
        "specification.okpd2",
        "products",
    ):
        value = _path_value(record, path)
        if isinstance(value, str):
            result.extend(part.strip() for part in value.split(","))
        elif isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            for item in value:
                if isinstance(item, Mapping):
                    code = _string_value(
                        item,
                        "code",
                        "okpd2",
                        "classificationCode",
                    )
                    if code:
                        result.append(code)
                elif item not in (None, ""):
                    result.append(str(item).strip())
    return tuple(dict.fromkeys(item for item in result if item))


def _status_from_text(value: str) -> TenderStatus:
    normalized = value.casefold().replace("ё", "е")
    if any(item in normalized for item in ("отмен", "снят")):
        return TenderStatus.CANCELLED
    if any(
        item in normalized
        for item in ("заверш", "состоял", "итог", "заключен")
    ):
        return TenderStatus.COMPLETED
    if any(
        item in normalized
        for item in (
            "прием предлож",
            "прием заяв",
            "подача предлож",
            "торги",
            "опубликован",
            "актив",
        )
    ):
        return TenderStatus.ACCEPTING_APPLICATIONS
    if any(item in normalized for item in ("рассмотр", "подведение")):
        return TenderStatus.REVIEW
    if any(item in normalized for item in ("подача заверш", "закрыт")):
        return TenderStatus.APPLICATIONS_CLOSED
    if normalized:
        return TenderStatus.PUBLISHED
    return TenderStatus.UNKNOWN


def _path_value(mapping: Mapping[str, object], path: str) -> object:
    current: object = mapping
    for part in path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = _casefold_get(current, part)
        if current is None:
            return None
    return current


def _casefold_get(mapping: Mapping[str, object], key: str) -> object:
    if key in mapping:
        return mapping[key]
    normalized = key.casefold().replace("ё", "е")
    for candidate, value in mapping.items():
        if str(candidate).casefold().replace("ё", "е") == normalized:
            return value
    return None


def _string_value(mapping: Mapping[str, object], *paths: str) -> str:
    for path in paths:
        value = _path_value(mapping, path)
        if value is None:
            continue
        if isinstance(value, Mapping):
            for key in ("name", "title", "value", "text", "code"):
                nested = _casefold_get(value, key)
                if nested not in (None, ""):
                    return str(nested).strip()
            continue
        if isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            continue
        rendered = str(value).strip()
        if rendered:
            return rendered
    return ""


def _mapping_value(
    mapping: Mapping[str, object],
    *paths: str,
) -> Mapping[str, object]:
    for path in paths:
        value = _path_value(mapping, path)
        if isinstance(value, Mapping):
            return value
    return {}


def _decimal_value(
    mapping: Mapping[str, object],
    *paths: str,
) -> Decimal | None:
    for path in paths:
        value = _path_value(mapping, path)
        if isinstance(value, Mapping):
            value = (
                _casefold_get(value, "amount")
                or _casefold_get(value, "value")
                or _casefold_get(value, "start")
            )
        if value in (None, ""):
            continue
        rendered = (
            str(value)
            .replace("\u00a0", "")
            .replace(" ", "")
            .replace("₽", "")
            .replace("руб.", "")
            .replace("руб", "")
            .replace(",", ".")
            .strip()
        )
        try:
            return Decimal(rendered)
        except InvalidOperation:
            continue
    return None


def _datetime_value(
    mapping: Mapping[str, object],
    *paths: str,
) -> datetime | None:
    for path in paths:
        value = _path_value(mapping, path)
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _ensure_timezone(value)
    if isinstance(value, date):
        return datetime(
            value.year,
            value.month,
            value.day,
            tzinfo=timezone.utc,
        )
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    rendered = str(value).strip()
    if rendered.startswith("/Date("):
        digits = "".join(ch for ch in rendered if ch.isdigit() or ch == "-")
        try:
            return _parse_datetime(int(digits))
        except ValueError:
            return None
    try:
        return _ensure_timezone(
            datetime.fromisoformat(rendered.replace("Z", "+00:00"))
        )
    except ValueError:
        pass
    for fmt in (
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(rendered, fmt).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
    return None


def _ensure_timezone(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(
        tzinfo=timezone.utc
    )


def _int_value(mapping: Mapping[str, object], *paths: str) -> int | None:
    for path in paths:
        value = _path_value(mapping, path)
        if isinstance(value, Mapping):
            value = _casefold_get(value, "value")
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _absolute_url(value: str, *, base_url: str) -> str:
    rendered = value.strip()
    if rendered.startswith(("http://", "https://")):
        return rendered
    return urljoin(base_url, rendered)




__all__ = [
    "MosSupplierApiParseError",
    "MosSupplierApiParser",
    "MosSupplierParsedSearch",
    "mos_supplier_api_error_message",
]
