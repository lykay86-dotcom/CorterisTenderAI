"""Tests for stable collector normalization and serialization."""

from __future__ import annotations

from decimal import Decimal
import json

from app.tenders.collector.codec import (
    stable_json,
    tender_from_payload,
    tender_to_payload,
)
from app.tenders.collector.models import TenderAliasType
from app.tenders.collector.normalizer import (
    TenderNormalizer,
    normalize_text,
)
from tests.collector_c3_helpers import make_tender


def test_normalize_text_handles_russian_forms_and_spacing() -> None:
    assert normalize_text("  IP—Камеры, Ёлка  ") == "ip камеры елка"


def test_normalizer_builds_strong_official_aliases() -> None:
    tender = make_tender(raw_metadata={"eis_number": "0373100000126000001"})

    normalized = TenderNormalizer().normalize(tender)

    alias_types = {alias.alias_type for alias in normalized.aliases}
    assert TenderAliasType.EIS_NUMBER in alias_types
    assert TenderAliasType.SOURCE_EXTERNAL_ID in alias_types
    assert normalized.canonical_key == ("procurement:0373100000126000001")
    assert len(normalized.content_hash) == 64
    assert 0 < normalized.completeness_score <= 100


def test_codec_preserves_decimal_without_float_rounding() -> None:
    tender = make_tender(amount="1234567890.123456789")

    payload = tender_to_payload(tender)
    rendered = stable_json(payload)
    restored = tender_from_payload(json.loads(rendered))

    assert payload["price"]["amount"] == "1234567890.123456789"
    assert restored.price is not None
    assert restored.price.amount == Decimal("1234567890.123456789")
