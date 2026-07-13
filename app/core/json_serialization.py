"""Safe JSON rendering for application data and financial values."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import json
from pathlib import Path
from typing import Any


def json_default(value: Any) -> Any:
    """Convert supported application objects to JSON-compatible values.

    Decimal values are rendered as strings to preserve exact financial
    precision. The original domain objects are not modified.
    """

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, Enum):
        return value.value

    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)

    if isinstance(value, (set, frozenset)):
        return sorted(
            value,
            key=lambda item: str(item),
        )

    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def json_dumps(
    value: Any,
    *,
    ensure_ascii: bool = False,
    indent: int | None = 2,
    **kwargs: Any,
) -> str:
    """Serialize application data without crashing on Decimal values."""

    kwargs.setdefault("default", json_default)
    return json.dumps(
        value,
        ensure_ascii=ensure_ascii,
        indent=indent,
        **kwargs,
    )


__all__ = ["json_default", "json_dumps"]
