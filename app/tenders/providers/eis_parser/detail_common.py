"""Shared, side-effect-free helpers for EIS detail adapters."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Iterable


EIS_TIMEZONE = timezone(timedelta(hours=3), "Europe/Moscow")


def extract_fields(html: str) -> dict[str, tuple[str, ...]]:
    """Extract labelled values from current and fixture EIS detail markup."""

    # Imported lazily to keep ``app.tenders.providers.eis`` as the public facade
    # without creating an import cycle during module initialization.
    from app.tenders.providers.eis import _DomParser, _clean_text

    parser = _DomParser()
    parser.feed(html)
    parser.close()
    root = parser.root
    collected: dict[str, list[str]] = {}

    def add(label: str, value: str) -> None:
        normalized_label = normalize_label(label)
        normalized_value = _clean_text(value)
        if not normalized_label or not normalized_value:
            return
        values = collected.setdefault(normalized_label, [])
        if normalized_value not in values:
            values.append(normalized_value)

    for node in root.find_all(lambda item: bool(item.attrs.get("data-field", "").strip())):
        add(node.attrs["data-field"], node.text())

    containers = root.find_all(
        lambda item: any(
            marker in item.classes
            for marker in (
                "data-block",
                "notice-field",
                "common-text__block",
                "cardMainInfo__section",
                "lot-row",
            )
        )
    )
    title_classes = {
        "data-block__title",
        "notice-field__label",
        "common-text__title",
        "section__title",
        "lot-row__label",
    }
    value_classes = {
        "data-block__value",
        "notice-field__value",
        "common-text__value",
        "section__value",
        "lot-row__value",
    }
    for container in containers:
        titles = container.find_all(lambda item: bool(item.classes & title_classes))
        values = container.find_all(lambda item: bool(item.classes & value_classes))
        if titles and values:
            add(titles[0].text(), max((item.text() for item in values), key=len))

    # Some EIS pages use table rows with th/td rather than data-blocks.
    for row in root.find_all(lambda item: item.tag == "tr"):
        labels = row.find_all(lambda item: item.tag in {"th", "dt"})
        values = row.find_all(lambda item: item.tag in {"td", "dd"})
        if labels and values:
            add(labels[0].text(), max((item.text() for item in values), key=len))

    _extract_meta_fields(root, add)
    return {key: tuple(values) for key, values in collected.items()}


def _extract_meta_fields(root, add) -> None:
    for node in root.find_all(lambda item: item.tag == "meta"):
        key = node.attrs.get("name", "") or node.attrs.get("property", "")
        value = node.attrs.get("content", "")
        if key.startswith("eis:"):
            add(key[4:], value)


def normalize_label(value: str) -> str:
    return re.sub(r"[^0-9a-zа-я]+", " ", value.casefold().replace("ё", "е")).strip()


def first(fields: dict[str, tuple[str, ...]], *aliases: str) -> str | None:
    normalized = tuple(normalize_label(alias) for alias in aliases)
    for alias in normalized:
        values = fields.get(alias)
        if values:
            return values[0]
    for label, values in fields.items():
        if any(alias in label for alias in normalized):
            return values[0]
    return None


def all_values(fields: dict[str, tuple[str, ...]], *aliases: str) -> tuple[str, ...]:
    result: list[str] = []
    for alias in aliases:
        value = first(fields, alias)
        if value:
            result.extend(part.strip() for part in re.split(r"[;\n]", value) if part.strip())
    return tuple(dict.fromkeys(result))


def parse_decimal(value: str | None, *, percent: bool = False) -> Decimal | None:
    if not value:
        return None
    match = re.search(r"-?\d[\d\s]*(?:[.,]\d+)?", value.replace("\xa0", " "))
    if not match:
        return None
    try:
        amount = Decimal(match.group(0).replace(" ", "").replace(",", "."))
    except InvalidOperation:
        return None
    if amount < 0 or (percent and amount > 100):
        return None
    return amount


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    match = re.search(r"(\d{2}\.\d{2}\.\d{4})(?:\s+(\d{1,2}:\d{2}))?", value)
    if not match:
        return None
    raw = match.group(1) + (" " + match.group(2) if match.group(2) else "")
    fmt = "%d.%m.%Y %H:%M" if match.group(2) else "%d.%m.%Y"
    try:
        return datetime.strptime(raw, fmt).replace(tzinfo=EIS_TIMEZONE)
    except ValueError:
        return None


def extract_codes(values: Iterable[str], pattern: str) -> tuple[str, ...]:
    result: list[str] = []
    compiled = re.compile(pattern)
    for value in values:
        result.extend(compiled.findall(value))
    return tuple(dict.fromkeys(result))


__all__ = [
    "EIS_TIMEZONE",
    "all_values",
    "extract_codes",
    "extract_fields",
    "first",
    "normalize_label",
    "parse_datetime",
    "parse_decimal",
]
