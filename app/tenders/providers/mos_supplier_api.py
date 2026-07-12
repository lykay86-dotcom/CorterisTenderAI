"""Official bearer-token API provider for the Moscow Supplier Portal."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
import re
from time import perf_counter
from typing import Mapping, Sequence
from urllib.parse import quote

from app.tenders.collector.async_http import AsyncHttpClient, AsyncHttpError
from app.tenders.collector.async_provider import AsyncTenderProvider
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.mos_supplier_checkpoint import (
    MosSupplierCheckpointCoordinator,
    MosSupplierCheckpointPolicy,
)
from app.tenders.collector.network_settings import (
    ProviderNetworkSettings,
    default_collector_network_settings,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.models import TenderDocument, TenderSource, UnifiedTender
from app.tenders.provider_base import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderNotConfiguredError,
    TenderProviderError,
    TenderSearchQuery,
    TenderSearchResult,
)
from app.tenders.providers.mos_supplier_config import MosSupplierApiConfig
from app.tenders.providers.mos_supplier_parser import (
    MosSupplierApiParseError,
    MosSupplierApiParser,
    MosSupplierParsedSearch,
    mos_supplier_api_error_message,
)

class AsyncMosSupplierTenderProvider(AsyncTenderProvider):
    """Bearer-authenticated provider for official Moscow quote-session API."""

    descriptor = ProviderDescriptor(
        id="mos_supplier",
        display_name="Портал поставщиков Москвы",
        source=TenderSource.MOS_SUPPLIER,
        homepage_url="https://zakupki.mos.ru/",
        capabilities=ProviderCapabilities(
            search=True,
            tender_details=True,
            documents=True,
            authentication=True,
            public_api=True,
            incremental_updates=True,
            rate_limit_per_minute=60,
        ),
        enabled_by_default=True,
        priority=20,
        implementation_status="official_api_token_required",
    )
    connection_mode = "official_api_bearer"
    parser_version = "mos-supplier-api-1"

    def __init__(
        self,
        http_client: AsyncHttpClient,
        *,
        config: MosSupplierApiConfig | None = None,
        network_settings: ProviderNetworkSettings | None = None,
        checkpoint_repository: CollectorStateRepository | None = None,
        checkpoint_policy: MosSupplierCheckpointPolicy | None = None,
    ) -> None:
        self.http_client = http_client
        self.config = config or MosSupplierApiConfig.from_environment()
        self.network_settings = network_settings or (
            default_collector_network_settings().get("mos_supplier")
        )
        self.parser = MosSupplierApiParser(self.config)
        self.checkpoints = MosSupplierCheckpointCoordinator(
            checkpoint_repository,
            policy=checkpoint_policy,
        )

    async def search(
        self,
        query: TenderSearchQuery,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> TenderSearchResult:
        self._require_token()
        prepared = self.checkpoints.prepare(query)
        payload = build_mos_supplier_search_payload(prepared.query)
        response = await self._request_json(
            build_mos_supplier_api_url(self.config.search_url, payload),
            cancellation_token=cancellation_token,
        )
        parsed = self.parser.parse_search(response)
        filtered = tuple(
            item
            for item in parsed.items
            if matches_mos_supplier_query(item, prepared.query)
        )
        start = (prepared.query.page - 1) * prepared.query.page_size
        end = start + prepared.query.page_size
        page_items = filtered[start:end]
        warnings = list(parsed.warnings)
        warnings.extend(prepared.warnings)
        warnings.append(
            "Использован официальный API Портала поставщиков с "
            "bearer-токеном. Параметры серверной пагинации не "
            "зафиксированы в текущем контракте и применяются локально."
        )
        result = TenderSearchResult(
            provider_id=self.descriptor.id,
            items=page_items,
            total=(parsed.total if parsed.total is not None else len(filtered)),
            page=prepared.query.page,
            page_size=prepared.query.page_size,
            next_page_token=(
                str(prepared.query.page + 1)
                if end < len(filtered)
                else ""
            ),
            warnings=tuple(dict.fromkeys(warnings)),
        )
        self.checkpoints.mark_success(prepared, result)
        return result

    async def get_tender(
        self,
        external_id: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> UnifiedTender:
        self._require_token()
        normalized = external_id.strip()
        if not normalized:
            raise ValueError("external_id must not be empty")
        payload = {"id": normalized}
        response = await self._request_json(
            build_mos_supplier_api_url(self.config.get_url, payload),
            cancellation_token=cancellation_token,
        )
        return self.parser.parse_card(response)

    async def list_documents(
        self,
        external_id: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> Sequence[TenderDocument]:
        tender = await self.get_tender(
            external_id,
            cancellation_token=cancellation_token,
        )
        return tender.documents

    async def check_health(
        self,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> ProviderHealth:
        started = perf_counter()
        checked_at = _utc_now()
        if not self.config.configured:
            return ProviderHealth(
                provider_id=self.descriptor.id,
                status=ProviderHealthStatus.NOT_CONFIGURED,
                checked_at=checked_at,
                message=(
                    "Не задан bearer-токен Портала поставщиков. "
                    f"Укажите {self.config.token_environment_variable}."
                ),
                latency_ms=0,
            )
        try:
            response = await self._request_json(
                build_mos_supplier_api_url(
                    self.config.search_url,
                    {"filter": {"name": "видеонаблюдение"}},
                ),
                cancellation_token=cancellation_token,
            )
            self.parser.parse_search(response)
            status = ProviderHealthStatus.AVAILABLE
            message = (
                "Официальный API Портала поставщиков доступен; "
                "bearer-токен принят."
            )
        except ProviderNotConfiguredError as exc:
            status = ProviderHealthStatus.NOT_CONFIGURED
            message = str(exc)
        except MosSupplierApiParseError as exc:
            status = ProviderHealthStatus.DEGRADED
            message = (
                "API ответил, но структура ответа не распознана: "
                f"{exc}"
            )
        except TenderProviderError as exc:
            status = ProviderHealthStatus.UNAVAILABLE
            message = str(exc)
        return ProviderHealth(
            provider_id=self.descriptor.id,
            status=status,
            checked_at=checked_at,
            message=message,
            latency_ms=max(0, int((perf_counter() - started) * 1000)),
        )

    def validate_configuration(self) -> tuple[str, ...]:
        if not self.config.configured:
            return (
                "Требуется bearer-токен официального API Портала "
                "поставщиков.",
                f"Переменная окружения: "
                f"{self.config.token_environment_variable}.",
                "Без токена сетевой запрос не выполняется.",
            )
        return (
            "Настроен официальный API Портала поставщиков.",
            f"Токен: {self.config.masked_token}.",
            "Работоспособность следует подтвердить кнопкой проверки "
            "подключения или scripts/check_mos_supplier_api.py.",
        )

    def _require_token(self) -> None:
        if not self.config.configured:
            raise ProviderNotConfiguredError(
                "Портал поставщиков не настроен: отсутствует "
                f"{self.config.token_environment_variable}."
            )

    async def _request_json(
        self,
        url: str,
        *,
        cancellation_token: CollectorCancellationToken | None,
    ) -> object:
        try:
            response = await self.http_client.get(
                url,
                provider_id=self.descriptor.id,
                headers={
                    "Authorization": f"Bearer {self.config.api_token}",
                    "Accept": "application/json",
                    "Accept-Language": "ru-RU,ru;q=0.9",
                    "Cache-Control": "no-cache",
                },
                timeouts=self.network_settings.timeouts,
                retry_policy=self.network_settings.retry,
                cancellation_token=cancellation_token,
            )
        except AsyncHttpError as exc:
            if exc.status_code in {401, 403}:
                raise ProviderNotConfiguredError(
                    "Портал поставщиков отклонил bearer-токен "
                    f"(HTTP {exc.status_code}). Проверьте ключ и права "
                    "доступа к сервисам API."
                ) from exc
            detail = str(exc)
            if "timeout" in detail.casefold():
                detail = (
                    "истёк сетевой тайм-аут Портала поставщиков после "
                    f"{exc.attempts} попыток: {detail}"
                )
            raise TenderProviderError(
                f"Ошибка подключения к Порталу поставщиков: {detail}"
            ) from exc

        try:
            payload = json.loads(response.text())
        except json.JSONDecodeError as exc:
            raise MosSupplierApiParseError(
                "Официальный API вернул повреждённый JSON"
            ) from exc
        error_message = mos_supplier_api_error_message(payload)
        if error_message:
            raise TenderProviderError(
                f"Портал поставщиков вернул ошибку API: {error_message}"
            )
        return payload


def build_mos_supplier_search_payload(
    query: TenderSearchQuery,
) -> dict[str, object]:
    """Build only documented filters plus explicit user-supplied extensions."""

    filter_payload: dict[str, object] = {}
    if query.keywords:
        filter_payload["name"] = " ".join(
            item.strip() for item in query.keywords if item.strip()
        )
    customer_inn = str(query.extra.get("customer_inn", "")).strip()
    customer_name = str(query.extra.get("customer_name", "")).strip()
    status = query.extra.get("mos_status")
    if customer_inn:
        filter_payload["inn"] = customer_inn
    if customer_name:
        filter_payload["customer"] = customer_name
    if status not in (None, "", (), []):
        filter_payload["status"] = status

    payload: dict[str, object] = {"filter": filter_payload}
    if (
        query.price_currency == "RUB"
        and (query.min_price is not None or query.max_price is not None)
    ):
        price_filter: dict[str, object] = {"isNotNull": True}
        if query.min_price is not None:
            price_filter["start"] = [_transport_number(query.min_price)]
        if query.max_price is not None:
            price_filter["end"] = [_transport_number(query.max_price)]
        payload["startprice"] = price_filter

    extension = query.extra.get("mos_api_payload")
    if isinstance(extension, Mapping):
        payload = _deep_merge(payload, extension)
    return payload


def build_mos_supplier_api_url(
    endpoint: str,
    payload: Mapping[str, object],
) -> str:
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    separator = "&" if "?" in endpoint else "?"
    return f"{endpoint}{separator}{quote(rendered, safe='')}"


def matches_mos_supplier_query(
    tender: UnifiedTender,
    query: TenderSearchQuery,
) -> bool:
    haystack = " ".join(
        (
            tender.title,
            tender.description,
            tender.customer.name,
            tender.region,
            " ".join(tender.classification_codes),
        )
    ).casefold().replace("ё", "е")
    keywords = tuple(
        item.strip().casefold().replace("ё", "е")
        for item in query.keywords
        if item.strip()
    )
    excluded = tuple(
        item.strip().casefold().replace("ё", "е")
        for item in query.excluded_keywords
        if item.strip()
    )
    if keywords:
        match_all = bool(query.extra.get("match_all_keywords", False))
        checks = tuple(_term_matches(haystack, item) for item in keywords)
        if (match_all and not all(checks)) or (
            not match_all and not any(checks)
        ):
            return False
    if excluded and any(_term_matches(haystack, item) for item in excluded):
        return False
    if query.regions and tender.region:
        normalized_region = tender.region.casefold().replace("ё", "е")
        if not any(
            item.strip().casefold().replace("ё", "е")
            in normalized_region
            for item in query.regions
            if item.strip()
        ):
            return False
    if tender.price is not None:
        if (
            (query.min_price is not None or query.max_price is not None)
            and tender.price.currency != query.price_currency
        ):
            return False
        if (
            query.min_price is not None
            and tender.price.amount < Decimal(str(query.min_price))
        ):
            return False
        if (
            query.max_price is not None
            and tender.price.amount > Decimal(str(query.max_price))
        ):
            return False
    if tender.published_at is not None:
        published = tender.published_at.date()
        if query.date_from is not None and published < query.date_from:
            return False
        if query.date_to is not None and published > query.date_to:
            return False
    return True


_RUSSIAN_SUFFIXES = tuple(
    sorted(
        {
            "иями", "ями", "ами", "ов", "ев", "ей", "ого", "ему",
            "ами", "ями", "иях", "ах", "ях", "ия", "ья", "ию",
            "ий", "ый", "ой", "ая", "яя", "ое", "ее", "ие", "ые",
            "ую", "юю", "ам", "ям", "а", "я", "ы", "и", "у", "ю",
            "е", "о",
        },
        key=len,
        reverse=True,
    )
)


def _term_matches(text: str, term: str) -> bool:
    if term in text:
        return True
    text_tokens = re.findall(r"[a-zа-я0-9]+", text)
    term_tokens = re.findall(r"[a-zа-я0-9]+", term)
    if not term_tokens:
        return False
    return all(
        any(_tokens_match(text_token, term_token) for text_token in text_tokens)
        for term_token in term_tokens
    )


def _tokens_match(text_token: str, term_token: str) -> bool:
    if text_token == term_token:
        return True
    if min(len(text_token), len(term_token)) <= 3:
        return False
    return _russian_stem(text_token) == _russian_stem(term_token)


def _russian_stem(token: str) -> str:
    if not re.fullmatch(r"[а-я]+", token):
        return token
    for suffix in _RUSSIAN_SUFFIXES:
        if token.endswith(suffix):
            stem = token[: -len(suffix)]
            if len(stem) >= 4:
                return stem
    return token


def _transport_number(value: float | int | Decimal) -> int | float:
    decimal_value = Decimal(str(value))
    if decimal_value == decimal_value.to_integral_value():
        return int(decimal_value)
    return float(decimal_value)


def _deep_merge(
    base: Mapping[str, object],
    extension: Mapping[str, object],
) -> dict[str, object]:
    result = dict(base)
    for key, value in extension.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _deep_merge(
                result[key],  # type: ignore[arg-type]
                value,
            )
        else:
            result[str(key)] = value
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")




__all__ = [
    "AsyncMosSupplierTenderProvider",
    "MosSupplierApiConfig",
    "MosSupplierApiParseError",
    "MosSupplierApiParser",
    "MosSupplierParsedSearch",
    "build_mos_supplier_api_url",
    "build_mos_supplier_search_payload",
    "matches_mos_supplier_query",
]
