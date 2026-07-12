"""Tests for safe JSON serialization of financial results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import json
from pathlib import Path

import pytest

from app.core.json_serialization import (
    json_default,
    json_dumps,
)


class Mode(Enum):
    ACTIVE = "active"


@dataclass(frozen=True)
class Payload:
    amount: Decimal
    created: date


def test_json_dumps_serializes_nested_decimal_exactly() -> None:
    payload = {
        "estimate": {
            "total": Decimal("1234567890.123456789"),
            "vat": Decimal("22.00"),
        },
        "items": [
            {"cost": Decimal("999.99")},
        ],
    }

    rendered = json_dumps(payload)
    decoded = json.loads(rendered)

    assert decoded["estimate"]["total"] == (
        "1234567890.123456789"
    )
    assert decoded["estimate"]["vat"] == "22.00"
    assert decoded["items"][0]["cost"] == "999.99"


def test_json_dumps_supports_common_application_types(
    tmp_path,
) -> None:
    payload = {
        "created_at": datetime(2026, 7, 12, 0, 53, 49),
        "day": date(2026, 7, 12),
        "path": tmp_path / "report.json",
        "mode": Mode.ACTIVE,
        "values": {"СКУД", "ОПС"},
        "payload": Payload(
            amount=Decimal("10.50"),
            created=date(2026, 7, 12),
        ),
    }

    decoded = json.loads(json_dumps(payload))

    assert decoded["created_at"] == "2026-07-12T00:53:49"
    assert decoded["day"] == "2026-07-12"
    assert decoded["path"].endswith("report.json")
    assert decoded["mode"] == "active"
    assert decoded["values"] == ["ОПС", "СКУД"]
    assert decoded["payload"]["amount"] == "10.50"


def test_json_default_rejects_unknown_object() -> None:
    with pytest.raises(TypeError):
        json_default(object())
