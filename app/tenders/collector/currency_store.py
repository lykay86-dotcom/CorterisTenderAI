"""SQLite history and explicit Bank of Russia exchange-rate import."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Protocol
from xml.etree import ElementTree

from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.currency import (
    ExchangeRateBook,
    ExchangeRateQuote,
)
from app.tenders.collector.schema import CollectorSchemaMigrator
from app.tenders.http_client import HttpResponse
from app.tenders.tender_registry import TenderRegistryRepository


CBR_DAILY_RATES_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
CBR_SOURCE_NAME = "Банк России"
MAX_CBR_XML_BYTES = 2 * 1024 * 1024


class CbrRatesParseError(ValueError):
    """Raised when an official daily-rates document is invalid."""


class AsyncHttpGetter(Protocol):
    async def get(
        self,
        url: str,
        *,
        provider_id: str,
        params: dict[str, str] | None = None,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> HttpResponse: ...


@dataclass(frozen=True, slots=True)
class ExchangeRateImportResult:
    requested_date: date
    effective_date: date
    quote_count: int
    inserted_count: int
    source_url: str
    retrieved_at: str


class ExchangeRateRepository:
    """Persist immutable quote history in the Collector registry DB."""

    def __init__(
        self,
        path: str | Path,
        *,
        migrator: CollectorSchemaMigrator | None = None,
    ) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrator = migrator or CollectorSchemaMigrator()
        self._lock = RLock()

    def initialize(self) -> None:
        TenderRegistryRepository(self.path).initialize()
        with self._lock, self._connect() as connection:
            self.migrator.migrate(connection)

    def save_quotes(
        self,
        quotes: tuple[ExchangeRateQuote, ...],
        *,
        imported_at: str | None = None,
    ) -> int:
        self.initialize()
        timestamp = _utc_timestamp(imported_at)
        inserted = 0
        with self._lock, self._connect() as connection:
            for quote in quotes:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO collector_exchange_rate_quotes(
                        quote_id,
                        base_currency,
                        quote_currency,
                        rate,
                        effective_date,
                        source,
                        retrieved_at,
                        source_url,
                        imported_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _quote_id(quote),
                        quote.base_currency,
                        quote.quote_currency,
                        str(quote.rate),
                        quote.effective_date.isoformat(),
                        quote.source,
                        quote.retrieved_at,
                        quote.source_url,
                        timestamp,
                    ),
                )
                inserted += max(0, cursor.rowcount)
            connection.commit()
        return inserted

    def list_quotes(
        self,
        *,
        base_currency: str | None = None,
        quote_currency: str | None = None,
        effective_from: date | None = None,
        effective_to: date | None = None,
        limit: int = 5000,
    ) -> tuple[ExchangeRateQuote, ...]:
        if not 1 <= limit <= 50000:
            raise ValueError("limit must be between 1 and 50000")
        self.initialize()
        clauses: list[str] = []
        parameters: list[object] = []
        if base_currency:
            clauses.append("base_currency = ?")
            parameters.append(base_currency.strip().upper())
        if quote_currency:
            clauses.append("quote_currency = ?")
            parameters.append(quote_currency.strip().upper())
        if effective_from is not None:
            clauses.append("effective_date >= ?")
            parameters.append(effective_from.isoformat())
        if effective_to is not None:
            clauses.append("effective_date <= ?")
            parameters.append(effective_to.isoformat())
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        parameters.append(limit)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM collector_exchange_rate_quotes
                {where}
                ORDER BY effective_date DESC, retrieved_at DESC, quote_id
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return tuple(_row_to_quote(row) for row in rows)

    def load_book(
        self,
        *,
        effective_to: date | None = None,
        max_age_days: int = 7,
        limit: int = 5000,
    ) -> ExchangeRateBook:
        return ExchangeRateBook(
            self.list_quotes(effective_to=effective_to, limit=limit),
            max_age_days=max_age_days,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


class CbrDailyRatesImporter:
    """Fetch CBR XML only when explicitly called and persist its quotes."""

    def __init__(
        self,
        client: AsyncHttpGetter,
        repository: ExchangeRateRepository,
        *,
        endpoint: str = CBR_DAILY_RATES_URL,
    ) -> None:
        self.client = client
        self.repository = repository
        self.endpoint = endpoint

    async def import_date(
        self,
        requested_date: date,
        *,
        retrieved_at: datetime | None = None,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> ExchangeRateImportResult:
        moment = retrieved_at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("retrieved_at must include a timezone")
        timestamp = moment.astimezone(timezone.utc).isoformat(
            timespec="seconds"
        )
        response = await self.client.get(
            self.endpoint,
            provider_id="cbr_exchange_rates",
            params={"date_req": requested_date.strftime("%d/%m/%Y")},
            cancellation_token=cancellation_token,
        )
        quotes = parse_cbr_daily_xml(
            response.body,
            retrieved_at=timestamp,
            source_url=response.url or self.endpoint,
        )
        effective_date = quotes[0].effective_date
        if effective_date > requested_date:
            raise CbrRatesParseError(
                "CBR effective date cannot be after requested date"
            )
        inserted = self.repository.save_quotes(
            quotes,
            imported_at=timestamp,
        )
        return ExchangeRateImportResult(
            requested_date=requested_date,
            effective_date=effective_date,
            quote_count=len(quotes),
            inserted_count=inserted,
            source_url=response.url or self.endpoint,
            retrieved_at=timestamp,
        )


def parse_cbr_daily_xml(
    payload: bytes | str,
    *,
    retrieved_at: str,
    source_url: str = CBR_DAILY_RATES_URL,
) -> tuple[ExchangeRateQuote, ...]:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    if not raw or len(raw) > MAX_CBR_XML_BYTES:
        raise CbrRatesParseError("CBR XML size is invalid")
    lowered = raw.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise CbrRatesParseError("DTD and entities are not allowed")
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise CbrRatesParseError("CBR XML is malformed") from exc
    if root.tag != "ValCurs":
        raise CbrRatesParseError("Unexpected CBR XML root")
    try:
        effective_date = datetime.strptime(
            root.attrib["Date"],
            "%d.%m.%Y",
        ).date()
    except (KeyError, ValueError) as exc:
        raise CbrRatesParseError("CBR XML date is invalid") from exc

    quotes: list[ExchangeRateQuote] = []
    seen: set[str] = set()
    for node in root.findall("Valute"):
        code = (node.findtext("CharCode") or "").strip().upper()
        nominal_text = (node.findtext("Nominal") or "").strip()
        value_text = (node.findtext("Value") or "").strip()
        if not code or code in seen:
            raise CbrRatesParseError("CBR XML contains duplicate currency")
        try:
            nominal = Decimal(nominal_text.replace(",", "."))
            value = Decimal(value_text.replace(",", "."))
        except InvalidOperation as exc:
            raise CbrRatesParseError("CBR XML rate is invalid") from exc
        if nominal <= 0 or value <= 0:
            raise CbrRatesParseError("CBR XML rate must be positive")
        quotes.append(
            ExchangeRateQuote(
                base_currency=code,
                quote_currency="RUB",
                rate=value / nominal,
                effective_date=effective_date,
                source=CBR_SOURCE_NAME,
                retrieved_at=retrieved_at,
                source_url=source_url,
            )
        )
        seen.add(code)
    if not quotes:
        raise CbrRatesParseError("CBR XML contains no rates")
    return tuple(quotes)


def _quote_id(quote: ExchangeRateQuote) -> str:
    payload = "|".join(
        (
            quote.base_currency,
            quote.quote_currency,
            str(quote.rate),
            quote.effective_date.isoformat(),
            quote.source,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _row_to_quote(row: sqlite3.Row) -> ExchangeRateQuote:
    return ExchangeRateQuote(
        base_currency=str(row["base_currency"]),
        quote_currency=str(row["quote_currency"]),
        rate=str(row["rate"]),
        effective_date=date.fromisoformat(str(row["effective_date"])),
        source=str(row["source"]),
        retrieved_at=str(row["retrieved_at"]),
        source_url=str(row["source_url"]),
    )


def _utc_timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("imported_at must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "CBR_DAILY_RATES_URL",
    "CBR_SOURCE_NAME",
    "CbrDailyRatesImporter",
    "CbrRatesParseError",
    "ExchangeRateImportResult",
    "ExchangeRateRepository",
    "parse_cbr_daily_xml",
]
