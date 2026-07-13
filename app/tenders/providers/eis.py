"""Public EIS (zakupki.gov.ru) tender provider.

The connector uses the official public search and procurement pages.  It does
not require credentials and does not emulate authenticated user actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from html.parser import HTMLParser
import mimetypes
import re
from time import perf_counter
from typing import Callable, Iterable, Sequence
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from app.tenders.http_client import (
    HttpResponse,
    HttpRetryPolicy,
    HttpTransport,
    HttpTransportError,
    UrllibHttpTransport,
)
from app.tenders.models import (
    TenderCustomer,
    TenderDocument,
    TenderMoney,
    TenderProcedureType,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)
from app.tenders.provider_base import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderHealth,
    ProviderHealthStatus,
    TenderProvider,
    TenderProviderError,
    TenderSearchQuery,
    TenderSearchResult,
)


class EisAccessBlockedError(TenderProviderError):
    """Raised when EIS returns a CAPTCHA or access-protection page."""


class EisParseError(TenderProviderError):
    """Raised when an EIS response cannot be normalized safely."""


@dataclass(frozen=True, slots=True)
class EisProviderConfig:
    base_url: str = "https://zakupki.gov.ru/"
    search_path: str = "/epz/order/extendedsearch/results.html"
    home_path: str = "/epz/main/public/home.html"
    timeout_seconds: float = 10.0
    retry_attempts: int = 3
    retry_backoff_seconds: float = 0.75
    max_attempt_timeout_seconds: float = 25.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 "
        "CorterisTenderAI/1.5.1"
    )
    supported_page_sizes: tuple[int, ...] = (10, 20, 50, 100)

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.retry_attempts < 1:
            raise ValueError("retry_attempts must be at least 1")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be non-negative")
        if self.max_attempt_timeout_seconds <= 0:
            raise ValueError("max_attempt_timeout_seconds must be positive")
        if not self.supported_page_sizes:
            raise ValueError("supported_page_sizes must not be empty")


@dataclass(slots=True)
class _Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["_Node | str"] = field(default_factory=list)
    parent: "_Node | None" = field(default=None, repr=False)

    @property
    def classes(self) -> set[str]:
        return {item for item in self.attrs.get("class", "").split() if item}

    def text(self) -> str:
        values: list[str] = []
        self._append_text(values)
        return _clean_text(" ".join(values))

    def _append_text(self, values: list[str]) -> None:
        for child in self.children:
            if isinstance(child, str):
                if child.strip():
                    values.append(child)
            else:
                child._append_text(values)

    def descendants(self) -> Iterable["_Node"]:
        for child in self.children:
            if isinstance(child, _Node):
                yield child
                yield from child.descendants()

    def find_all(
        self,
        predicate: Callable[["_Node"], bool],
    ) -> list["_Node"]:
        result: list[_Node] = []
        if predicate(self):
            result.append(self)
        for node in self.descendants():
            if predicate(node):
                result.append(node)
        return result


class _DomParser(HTMLParser):
    VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("document")
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs) -> None:
        node = _Node(
            tag=tag.casefold(),
            attrs={str(key).casefold(): str(value or "") for key, value in attrs},
            parent=self._stack[-1],
        )
        self._stack[-1].children.append(node)
        if node.tag not in self.VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if self._stack[-1].tag == tag.casefold():
            self._stack.pop()

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == normalized:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self._stack[-1].children.append(data)


@dataclass(frozen=True, slots=True)
class EisParseResult:
    items: tuple[UnifiedTender, ...]
    total: int | None
    warnings: tuple[str, ...] = ()


class EisHtmlParser:
    """Normalize current and legacy EIS result-card markup."""

    PROCUREMENT_NUMBER = re.compile(r"(?<!\d)(\d{11,25})(?!\d)")
    TOTAL_PATTERNS = (
        re.compile(r"Всего\s+(?:найдено|записей)?\s*:?\s*(\d+(?:[ \u00a0]\d{3})*)", re.I),
        re.compile(r"Найдено\s*:?\s*(\d+(?:[ \u00a0]\d{3})*)", re.I),
    )

    def __init__(self, *, base_url: str) -> None:
        self.base_url = base_url

    def parse_search(self, html: str) -> EisParseResult:
        self._ensure_not_blocked(html)
        root = self._parse(html)
        cards = root.find_all(lambda node: "search-registry-entry-block" in node.classes)
        if not cards:
            cards = root.find_all(
                lambda node: (
                    "registry-entry" in node.classes and node.tag in {"div", "article", "section"}
                )
            )

        items: list[UnifiedTender] = []
        warnings: list[str] = []
        for index, card in enumerate(cards, start=1):
            try:
                tender = self._parse_card(card)
            except EisParseError as exc:
                warnings.append(f"Карточка {index}: {exc}")
                continue
            items.append(tender)

        page_text = root.text()
        total = None
        for pattern in self.TOTAL_PATTERNS:
            match = pattern.search(page_text)
            if match:
                try:
                    total = int(re.sub(r"\s+", "", match.group(1)))
                except ValueError:
                    total = None
                break

        if cards and not items:
            raise EisParseError("EIS returned result cards, but none could be normalized")
        return EisParseResult(
            items=tuple(items),
            total=total,
            warnings=tuple(warnings),
        )

    def parse_documents(self, html: str) -> tuple[TenderDocument, ...]:
        self._ensure_not_blocked(html)
        root = self._parse(html)
        documents: list[TenderDocument] = []
        seen: set[str] = set()

        for anchor in root.find_all(lambda node: node.tag == "a"):
            href = anchor.attrs.get("href", "").strip()
            if not href:
                continue
            name = (
                anchor.attrs.get("title", "").strip() or anchor.text() or _filename_from_url(href)
            )
            if not self._is_document_link(href, name):
                continue

            url = urljoin(self.base_url, href)
            identity = url.casefold()
            if identity in seen:
                continue
            seen.add(identity)

            parent_text = anchor.parent.text() if anchor.parent else anchor.text()
            documents.append(
                TenderDocument(
                    id=hashlib.sha256(url.encode("utf-8")).hexdigest()[:20],
                    name=_clean_text(name) or "Документ ЕИС",
                    url=url,
                    mime_type=_guess_mime_type(name, url),
                    size_bytes=_parse_file_size(parent_text),
                    published_at=_parse_first_datetime(parent_text),
                )
            )
        return tuple(documents)

    def _parse_card(self, card: _Node) -> UnifiedTender:
        number_anchor = self._find_number_anchor(card)
        number_text = number_anchor.text() if number_anchor else card.text()
        number_match = self.PROCUREMENT_NUMBER.search(number_text)
        if not number_match:
            raise EisParseError("не найден реестровый номер закупки")
        procurement_number = number_match.group(1)

        href = number_anchor.attrs.get("href", "") if number_anchor else ""
        if not href:
            href = "/epz/order/extendedsearch/results.html?" + urlencode(
                {"searchString": procurement_number}
            )
        source_url = urljoin(self.base_url, href)

        title = self._field_value(
            card,
            ("объект закупки", "наименование закупки", "предмет закупки"),
        )
        if not title:
            title = self._fallback_title(card, procurement_number)
        if not title:
            raise EisParseError("не найдено наименование закупки")

        customer_name = (
            self._field_value(
                card,
                ("заказчик", "организация, осуществляющая размещение"),
            )
            or "Заказчик не указан"
        )
        region = self._field_value(
            card,
            (
                "регион",
                "место поставки",
                "место нахождения заказчика",
                "место выполнения работ",
            ),
        )
        price_text = self._class_text(card, "price-block__value")
        price = _parse_money(price_text)

        published_at = self._date_from_block(card, ("размещено", "опубликовано"))
        deadline = self._date_from_block(
            card,
            (
                "окончание подачи заявок",
                "дата и время окончания подачи заявок",
            ),
        )

        header_text = " ".join(
            filter(
                None,
                (
                    self._class_text(card, "registry-entry__header-top__title"),
                    self._class_text(card, "registry-entry__header-mid__title"),
                    card.text()[:600],
                ),
            )
        )
        law = _parse_law(header_text)
        status = _parse_status(header_text)
        procedure_type = _parse_procedure(header_text)

        external_id = _query_parameter(source_url, "regNumber") or procurement_number
        return UnifiedTender(
            source=TenderSource.EIS,
            external_id=external_id,
            procurement_number=procurement_number,
            title=title,
            customer=TenderCustomer(
                name=customer_name,
                region=region,
            ),
            source_url=source_url,
            published_at=published_at,
            application_deadline=deadline,
            price=price,
            status=status,
            procedure_type=procedure_type,
            law=law,
            region=region,
            description=title,
            raw_metadata={
                "provider": "eis",
                "interface": "public_html",
                "source_card_text": card.text()[:4000],
            },
        )

    def _find_number_anchor(self, card: _Node) -> _Node | None:
        preferred = card.find_all(
            lambda node: node.tag == "a" and "registry-entry__header-mid__number" in node.classes
        )
        if preferred:
            return preferred[0]

        number_containers = card.find_all(
            lambda node: "registry-entry__header-mid__number" in node.classes
        )
        for container in number_containers:
            anchors = container.find_all(lambda node: node.tag == "a")
            if anchors:
                return anchors[0]

        for anchor in card.find_all(lambda node: node.tag == "a"):
            if self.PROCUREMENT_NUMBER.search(anchor.text()):
                return anchor
        return None

    def _field_value(self, card: _Node, labels: Sequence[str]) -> str:
        normalized_labels = tuple(label.casefold() for label in labels)
        blocks = card.find_all(
            lambda node: any(
                token in node.classes
                for token in (
                    "registry-entry__body-block",
                    "registry-entry__body-item",
                    "data-block",
                )
            )
        )
        for block in blocks:
            block_text = block.text()
            folded = block_text.casefold()
            matched = next(
                (label for label in normalized_labels if label in folded),
                "",
            )
            if not matched:
                continue

            values = block.find_all(
                lambda node: any(
                    token in node.classes
                    for token in (
                        "registry-entry__body-value",
                        "registry-entry__body-href",
                        "data-block__value",
                    )
                )
            )
            candidates = [
                value.text()
                for value in values
                if value.text() and value.text().casefold() not in normalized_labels
            ]
            if candidates:
                return max(candidates, key=len)

            cleaned = re.sub(
                re.escape(matched),
                " ",
                block_text,
                count=1,
                flags=re.I,
            )
            cleaned = _clean_text(cleaned)
            if cleaned:
                return cleaned
        return ""

    def _fallback_title(self, card: _Node, number: str) -> str:
        candidates: list[str] = []
        for node in card.find_all(
            lambda item: any(
                token in item.classes
                for token in (
                    "registry-entry__body-value",
                    "registry-entry__body-href",
                )
            )
        ):
            text = node.text()
            if (
                len(text) >= 8
                and number not in text
                and not _looks_like_date(text)
                and not _looks_like_money(text)
            ):
                candidates.append(text)
        return max(candidates, key=len) if candidates else ""

    def _date_from_block(self, card: _Node, labels: Sequence[str]) -> datetime | None:
        value = self._field_value(card, labels)
        return _parse_first_datetime(value)

    @staticmethod
    def _class_text(card: _Node, class_name: str) -> str:
        nodes = card.find_all(lambda node: class_name in node.classes)
        return nodes[0].text() if nodes else ""

    @staticmethod
    def _is_document_link(href: str, name: str) -> bool:
        folded = f"{href} {name}".casefold()
        if any(
            marker in folded
            for marker in (
                "/filestore/",
                "/download/",
                "file.html",
                "download.html",
            )
        ):
            return True
        return bool(
            re.search(
                r"\.(?:pdf|docx?|xlsx?|xlsm|zip|rar|7z|xml|rtf|odt)(?:$|[?#])",
                folded,
            )
        )

    @staticmethod
    def _parse(html: str) -> _Node:
        parser = _DomParser()
        try:
            parser.feed(html)
            parser.close()
        except Exception as exc:
            raise EisParseError(f"ошибка HTML-парсера: {exc}") from exc
        return parser.root

    @staticmethod
    def _ensure_not_blocked(html: str) -> None:
        folded = html.casefold()
        markers = (
            "captcha",
            "проверка браузера",
            "доступ ограничен",
            "подтвердите, что вы не робот",
        )
        if any(marker in folded for marker in markers):
            raise EisAccessBlockedError("ЕИС вернула страницу защиты доступа или CAPTCHA")


def build_eis_search_url(
    query: TenderSearchQuery,
    config: EisProviderConfig | None = None,
) -> tuple[str, int]:
    """Build the public EIS search URL shared by sync and async adapters."""

    effective = config or EisProviderConfig()
    rounded_page_size = min(
        effective.supported_page_sizes,
        key=lambda size: (
            size < query.page_size,
            abs(size - query.page_size),
            size,
        ),
    )
    larger = [size for size in effective.supported_page_sizes if size >= query.page_size]
    if larger:
        rounded_page_size = min(larger)

    keywords = " ".join(keyword.strip() for keyword in query.keywords if keyword.strip())
    morphology = "off" if query.extra.get("exact_search") else "on"
    params: list[tuple[str, str]] = [
        ("searchString", keywords),
        ("morphology", morphology),
        ("search-filter", "Дате размещения"),
        ("pageNumber", str(query.page)),
        ("sortDirection", "false"),
        ("recordsPerPage", f"_{rounded_page_size}"),
        ("showLotsInfoHidden", "false"),
        ("sortBy", "UPDATE_DATE"),
        ("af", "on"),
        ("ca", "on"),
        ("pc", "on"),
        ("pa", "on"),
        ("currencyIdGeneral", "-1"),
    ]

    requested_laws = {law.casefold().replace("ё", "е") for law in query.laws}
    if not requested_laws or any("44" in law for law in requested_laws):
        params.append(("fz44", "on"))
    if not requested_laws or any("223" in law for law in requested_laws):
        params.append(("fz223", "on"))

    if query.date_from is not None:
        params.append(("publishDateFrom", query.date_from.strftime("%d.%m.%Y")))
    if query.date_to is not None:
        params.append(("publishDateTo", query.date_to.strftime("%d.%m.%Y")))
    if query.min_price is not None and query.price_currency == "RUB":
        params.append(("priceFromGeneral", _format_number(query.min_price)))
    if query.max_price is not None and query.price_currency == "RUB":
        params.append(("priceToGeneral", _format_number(query.max_price)))

    base = urljoin(effective.base_url, effective.search_path)
    return f"{base}?{urlencode(params)}", rounded_page_size


def matches_eis_query(
    item: UnifiedTender,
    query: TenderSearchQuery,
) -> bool:
    """Apply client-side filters to a normalized EIS search card."""

    searchable = " ".join(
        (
            item.title,
            item.description,
            item.customer.name,
            item.region,
            item.law,
        )
    ).casefold()

    if any(
        keyword.strip().casefold() in searchable
        for keyword in query.excluded_keywords
        if keyword.strip()
    ):
        return False

    if query.regions and item.region:
        if not any(
            region.strip().casefold() in item.region.casefold()
            or item.region.casefold() in region.strip().casefold()
            for region in query.regions
            if region.strip()
        ):
            return False

    if query.laws and item.law:
        normalized_law = item.law.casefold()
        if not any(
            law.strip().casefold() in normalized_law or normalized_law in law.strip().casefold()
            for law in query.laws
            if law.strip()
        ):
            return False

    if item.price is not None:
        if (
            query.min_price is not None or query.max_price is not None
        ) and item.price.currency != query.price_currency:
            return False
        amount = item.price.amount
        if query.min_price is not None and amount < Decimal(str(query.min_price)):
            return False
        if query.max_price is not None and amount > Decimal(str(query.max_price)):
            return False

    if item.published_at is not None:
        published_date = item.published_at.date()
        if query.date_from is not None and published_date < query.date_from:
            return False
        if query.date_to is not None and published_date > query.date_to:
            return False
    return True


def eis_documents_url(source_url: str) -> str:
    """Return the public documents tab URL for a normalized EIS card."""

    parsed = urlparse(source_url)
    path = parsed.path
    if path.endswith("/common-info.html"):
        path = path[: -len("common-info.html")] + "documents.html"
    elif path.endswith("/event-journal.html"):
        path = path[: -len("event-journal.html")] + "documents.html"
    elif not path.endswith("/documents.html"):
        separator = "&" if parsed.query else "?"
        return source_url + separator + "tab=documents"
    return urlunparse(parsed._replace(path=path))


class EisTenderProvider(TenderProvider):
    """Real connector for the official public EIS web interface."""

    descriptor = ProviderDescriptor(
        id="eis",
        display_name="ЕИС Закупки",
        source=TenderSource.EIS,
        homepage_url="https://zakupki.gov.ru/",
        capabilities=ProviderCapabilities(
            search=True,
            tender_details=True,
            documents=True,
            authentication=False,
            public_api=False,
            incremental_updates=False,
            rate_limit_per_minute=20,
        ),
        priority=10,
        implementation_status="public_html",
    )

    def __init__(
        self,
        *,
        transport: HttpTransport | None = None,
        config: EisProviderConfig | None = None,
    ) -> None:
        self.config = config or EisProviderConfig()
        self.transport = transport or UrllibHttpTransport(
            retry_policy=HttpRetryPolicy(
                max_attempts=self.config.retry_attempts,
                backoff_seconds=(self.config.retry_backoff_seconds),
                backoff_multiplier=2.0,
                timeout_multiplier=1.5,
                max_attempt_timeout_seconds=(self.config.max_attempt_timeout_seconds),
            )
        )
        self.parser = EisHtmlParser(base_url=self.config.base_url)

    def search(self, query: TenderSearchQuery) -> TenderSearchResult:
        url, rounded_page_size = build_eis_search_url(
            query,
            self.config,
        )
        response = self._get(url)
        parsed = self.parser.parse_search(response.text())

        warnings = list(parsed.warnings)
        warnings.append(
            "Использован публичный HTML-интерфейс ЕИС; структура страницы может изменяться."
        )
        if rounded_page_size != query.page_size:
            warnings.append(
                f"Размер страницы ЕИС округлён: {query.page_size} → {rounded_page_size}."
            )
        if query.regions:
            warnings.append(
                "Региональный фильтр применяется к данным карточки; "
                "тендеры без региона сохраняются."
            )

        items = tuple(item for item in parsed.items if matches_eis_query(item, query))[
            : query.page_size
        ]

        return TenderSearchResult(
            provider_id=self.descriptor.id,
            items=items,
            total=parsed.total,
            page=query.page,
            page_size=query.page_size,
            next_page_token=(
                str(query.page + 1)
                if parsed.total is None or query.page * rounded_page_size < parsed.total
                else ""
            ),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def get_tender(self, external_id: str) -> UnifiedTender:
        normalized = external_id.strip()
        if not normalized:
            raise ValueError("external_id must not be empty")
        result = self.search(
            TenderSearchQuery(
                keywords=(normalized,),
                page=1,
                page_size=10,
                extra={"exact_search": True},
            )
        )
        for item in result.items:
            if normalized in {
                item.external_id,
                item.procurement_number,
            }:
                return item
        raise TenderProviderError(f"Закупка ЕИС {normalized} не найдена")

    def list_documents(self, external_id: str) -> Sequence[TenderDocument]:
        tender = self.get_tender(external_id)
        documents_url = eis_documents_url(tender.source_url)
        response = self._get(documents_url)
        return self.parser.parse_documents(response.text())

    def check_health(self) -> ProviderHealth:
        started = perf_counter()
        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            response = self._get(
                urljoin(self.config.base_url, self.config.home_path),
                allow_non_200=True,
            )
        except TenderProviderError as exc:
            return ProviderHealth(
                provider_id=self.descriptor.id,
                status=ProviderHealthStatus.UNAVAILABLE,
                checked_at=checked_at,
                message=str(exc),
                latency_ms=_elapsed_ms(started),
            )

        text = response.text()
        if response.status_code == 200 and (
            "единая информационная система" in text.casefold() or "закуп" in text.casefold()
        ):
            status = ProviderHealthStatus.AVAILABLE
            message = "Публичная часть ЕИС доступна."
        elif response.status_code == 200:
            status = ProviderHealthStatus.DEGRADED
            message = "ЕИС ответила, но содержимое страницы не распознано."
        else:
            status = ProviderHealthStatus.UNAVAILABLE
            message = f"ЕИС вернула HTTP {response.status_code}."

        return ProviderHealth(
            provider_id=self.descriptor.id,
            status=status,
            checked_at=checked_at,
            message=message,
            latency_ms=_elapsed_ms(started),
        )

    def validate_configuration(self) -> tuple[str, ...]:
        return (
            "Используется официальный публичный HTML-интерфейс ЕИС "
            "без авторизации; при изменении верстки потребуется "
            "обновление парсера.",
        )

    def build_search_url(
        self,
        query: TenderSearchQuery,
    ) -> tuple[str, int]:
        return build_eis_search_url(query, self.config)

    def _get(
        self,
        url: str,
        *,
        allow_non_200: bool = False,
    ) -> HttpResponse:
        try:
            response = self.transport.get(
                url,
                headers={
                    "User-Agent": self.config.user_agent,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "ru-RU,ru;q=0.9",
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                },
                timeout_seconds=self.config.timeout_seconds,
            )
        except HttpTransportError as exc:
            detail = str(exc)
            if "SSL handshake timed out" in detail:
                detail = (
                    "не удалось завершить SSL-рукопожатие "
                    f"после {exc.attempts} попыток. "
                    "ЕИС не ответила в пределах сетевого таймаута"
                )
            elif "connection timed out" in detail:
                detail = f"истёк таймаут подключения после {exc.attempts} попыток"
            raise TenderProviderError(f"Ошибка подключения к ЕИС: {detail}") from exc

        if not allow_non_200 and response.status_code != 200:
            raise TenderProviderError(f"ЕИС вернула HTTP {response.status_code}")
        return response

    @staticmethod
    def _matches_query(
        item: UnifiedTender,
        query: TenderSearchQuery,
    ) -> bool:
        return matches_eis_query(item, query)

    @staticmethod
    def _documents_url(source_url: str) -> str:
        return eis_documents_url(source_url)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _parse_money(value: str) -> TenderMoney | None:
    if not value:
        return None
    cleaned = value.replace("\xa0", " ")
    match = re.search(r"-?\d[\d\s]*(?:[.,]\d{1,2})?", cleaned)
    if not match:
        return None
    number = match.group(0).replace(" ", "").replace(",", ".")
    try:
        amount = Decimal(number)
    except InvalidOperation:
        return None
    if amount < 0:
        return None
    currency = "RUB" if any(token in cleaned for token in ("₽", "руб")) else "RUB"
    return TenderMoney(amount=amount, currency=currency)


def _parse_first_datetime(value: str) -> datetime | None:
    if not value:
        return None
    match = re.search(
        r"(?<!\d)(\d{2}\.\d{2}\.\d{4})(?:\s+(\d{1,2}:\d{2}))?",
        value,
    )
    if not match:
        return None
    raw = match.group(1)
    if match.group(2):
        raw += " " + match.group(2)
        formats = ("%d.%m.%Y %H:%M",)
    else:
        formats = ("%d.%m.%Y",)
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _parse_law(value: str) -> str:
    folded = value.casefold()
    if "44-фз" in folded or "44 фз" in folded:
        return "44-ФЗ"
    if "223-фз" in folded or "223 фз" in folded:
        return "223-ФЗ"
    return ""


def _parse_status(value: str) -> TenderStatus:
    folded = value.casefold().replace("ё", "е")
    if "отмен" in folded:
        return TenderStatus.CANCELLED
    if "определение поставщика завершено" in folded or "закупка завершена" in folded:
        return TenderStatus.COMPLETED
    if "работа комиссии" in folded or "рассмотрение заявок" in folded:
        return TenderStatus.REVIEW
    if "подача заявок завершена" in folded or "прием заявок завершен" in folded:
        return TenderStatus.APPLICATIONS_CLOSED
    if "подача заявок" in folded or "прием заявок" in folded:
        return TenderStatus.ACCEPTING_APPLICATIONS
    if "размещен" in folded or "опубликован" in folded:
        return TenderStatus.PUBLISHED
    return TenderStatus.UNKNOWN


def _parse_procedure(value: str) -> TenderProcedureType:
    folded = value.casefold().replace("ё", "е")
    if "электронн" in folded and "аукцион" in folded:
        return TenderProcedureType.ELECTRONIC_AUCTION
    if "открыт" in folded and "конкурс" in folded:
        return TenderProcedureType.OPEN_COMPETITION
    if "запрос котировок" in folded:
        return TenderProcedureType.REQUEST_FOR_QUOTATIONS
    if "запрос предложений" in folded:
        return TenderProcedureType.REQUEST_FOR_PROPOSALS
    if "единственн" in folded and "поставщик" in folded:
        return TenderProcedureType.SINGLE_SUPPLIER
    if "частью 12 статьи 93" in folded:
        return TenderProcedureType.SINGLE_SUPPLIER
    return TenderProcedureType.UNKNOWN


def _parse_file_size(value: str) -> int | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(Б|КБ|МБ|ГБ)\b", value, re.I)
    if not match:
        return None
    number = float(match.group(1).replace(",", "."))
    multiplier = {
        "Б": 1,
        "КБ": 1024,
        "МБ": 1024**2,
        "ГБ": 1024**3,
    }[match.group(2).upper()]
    return int(number * multiplier)


def _guess_mime_type(name: str, url: str) -> str:
    mime, _ = mimetypes.guess_type(name or _filename_from_url(url))
    return mime or "application/octet-stream"


def _filename_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] if path else ""


def _query_parameter(url: str, name: str) -> str:
    values = parse_qs(urlparse(url).query).get(name, [])
    return values[0] if values else ""


def _looks_like_date(value: str) -> bool:
    return bool(re.fullmatch(r"\d{2}\.\d{2}\.\d{4}(?:\s+\d{1,2}:\d{2})?", value.strip()))


def _looks_like_money(value: str) -> bool:
    return bool(re.search(r"\d[\d\s]*(?:[.,]\d{2})?\s*(?:₽|руб)", value, re.I))


def _format_number(value: Decimal | int | float) -> str:
    rendered = format(Decimal(str(value)), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))


__all__ = [
    "EisAccessBlockedError",
    "EisHtmlParser",
    "EisParseError",
    "EisParseResult",
    "EisProviderConfig",
    "EisTenderProvider",
    "build_eis_search_url",
    "eis_documents_url",
    "matches_eis_query",
]
