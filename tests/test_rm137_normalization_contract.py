from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.tenders.collector.codec import tender_from_payload, tender_to_payload
from app.tenders.collector.manual_adapter import CanonicalTenderField, MappingProvenance
from app.tenders.collector.models import (
    NormalizationDiagnosticCode,
    NormalizationFieldOutcome,
)
from app.tenders.collector.normalizer import (
    TENDER_NORMALIZATION_CONTRACT_VERSION,
    TenderNormalizer,
)
from app.tenders.models import (
    TenderCustomer,
    TenderMoney,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)


def _tender(**overrides: object) -> UnifiedTender:
    values: dict[str, object] = {
        "source": TenderSource.EIS,
        "external_id": " 000123 ",
        "procurement_number": " 01234567890123456789 ",
        "title": "  Поставка\r\nоборудования\x00  ",
        "customer": TenderCustomer(name="  Заказчик  ", inn=" 7700000000 "),
        "source_url": "https://example.test/tender?id=1",
        "published_at": datetime(2026, 7, 17, 9, 0, tzinfo=timezone(timedelta(hours=3))),
        "application_deadline": datetime(2026, 7, 18, 18, 0, tzinfo=timezone(timedelta(hours=3))),
        "price": TenderMoney(Decimal("1234567.890"), "RUB"),
        "status": TenderStatus.ACCEPTING_APPLICATIONS,
        "law": "44-ФЗ",
        "classification_codes": ("01.02.03", "01.02.03", "00.11"),
        "tags": (" beta ", "alpha", "alpha"),
        "raw_metadata": {"provider": "eis", "parser_version": "fixture-1"},
    }
    values.update(overrides)
    return UnifiedTender(**values)  # type: ignore[arg-type]


def test_contract_is_versioned_and_uses_existing_normalized_result() -> None:
    result = TenderNormalizer().normalize(_tender())

    assert TENDER_NORMALIZATION_CONTRACT_VERSION == 1
    assert result.contract_version == TENDER_NORMALIZATION_CONTRACT_VERSION
    assert result.semantic_fingerprint == result.content_hash
    assert len(result.semantic_fingerprint) == 64


def test_canonical_fields_are_conservative_deterministic_and_timezone_aware() -> None:
    result = TenderNormalizer().normalize(_tender())

    assert result.tender.external_id == "000123"
    assert result.tender.procurement_number == "01234567890123456789"
    assert result.tender.title == "Поставка\nоборудования"
    assert result.tender.customer.name == "Заказчик"
    assert result.tender.published_at == datetime(2026, 7, 17, 6, 0, tzinfo=timezone.utc)
    assert result.tender.application_deadline == datetime(2026, 7, 18, 15, 0, tzinfo=timezone.utc)
    assert result.tender.classification_codes == ("00.11", "01.02.03")
    assert result.tender.tags == ("alpha", "beta")
    assert all(
        value is None or value.utcoffset() is not None
        for value in (result.tender.published_at, result.tender.application_deadline)
    )


def test_naive_datetime_is_not_localized_from_machine_timezone() -> None:
    result = TenderNormalizer().normalize(_tender(published_at=datetime(2026, 7, 17, 9, 0)))

    assert result.tender.published_at is None
    diagnostic = next(item for item in result.diagnostics if item.field == "published_at")
    assert diagnostic.code is NormalizationDiagnosticCode.NAIVE_DATETIME_REJECTED
    assert diagnostic.recoverable


def test_tender_money_rejects_float_and_parses_documented_localized_strings() -> None:
    with pytest.raises(TypeError, match="float"):
        TenderMoney.from_value(0.1)

    assert TenderMoney.from_value("1 234 567,89").amount == Decimal("1234567.89")
    assert TenderMoney.from_value("1\u00a0234\u00a0567.89").amount == Decimal("1234567.89")
    with pytest.raises(ValueError):
        TenderMoney.from_value("1e6")


def test_unknown_currency_is_not_guessed_as_rub() -> None:
    result = TenderNormalizer().normalize(_tender(price=TenderMoney(Decimal("10"), "ZZZ")))

    assert result.tender.price is not None
    assert result.tender.price.currency == "ZZZ"
    assert any(
        item.code is NormalizationDiagnosticCode.UNSUPPORTED_VALUE
        and item.field == "price.currency"
        for item in result.diagnostics
    )


def test_secret_query_and_fragment_are_removed_without_leaking_value() -> None:
    result = TenderNormalizer().normalize(
        _tender(source_url="https://example.test/tender?id=1&token=very-secret#private")
    )

    assert result.tender.source_url == "https://example.test/tender?id=1"
    rendered = repr(result.diagnostics) + repr(result.provenance)
    assert "very-secret" not in rendered
    assert "private" not in rendered
    assert any(
        item.code is NormalizationDiagnosticCode.UNSAFE_URL_REJECTED for item in result.diagnostics
    )


def test_url_with_userinfo_is_rejected_by_canonical_model() -> None:
    with pytest.raises(ValueError):
        _tender(source_url="https://user:password@example.test/tender")


def test_diagnostics_and_provenance_are_stable_bounded_and_unverified() -> None:
    normalizer = TenderNormalizer()
    first = normalizer.normalize(_tender(published_at=datetime(2026, 7, 17, 9, 0)))
    second = normalizer.normalize(_tender(published_at=datetime(2026, 7, 17, 9, 0)))

    assert first.diagnostics == second.diagnostics
    assert first.provenance == second.provenance
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert len(first.diagnostics) <= 128
    assert all(len(item.message) <= 300 for item in first.diagnostics)
    assert all(not item.verified for item in first.provenance)
    assert any(
        item.field == "published_at" and item.outcome is NormalizationFieldOutcome.INVALID
        for item in first.provenance
    )


def test_industry_keywords_do_not_guess_law_status_or_region() -> None:
    for title in ("Видеонаблюдение СКУД ОПС", "Канцелярские товары"):
        result = TenderNormalizer().normalize(
            _tender(title=title, law="неизвестный режим", region="")
        )
        assert result.tender.law == ""
        assert result.tender.status is TenderStatus.ACCEPTING_APPLICATIONS
        assert result.tender.region == ""
        assert any(
            item.code is NormalizationDiagnosticCode.UNMAPPED_VALUE and item.field == "law"
            for item in result.diagnostics
        )


def test_legacy_payload_remains_readable_before_strict_normalization() -> None:
    payload = tender_to_payload(_tender())
    payload["published_at"] = "2026-07-17T09:00:00"

    restored = tender_from_payload(payload)
    result = TenderNormalizer().normalize(restored)

    assert restored.published_at is not None
    assert restored.published_at.tzinfo is None
    assert result.tender.published_at is None
    assert any(
        item.code is NormalizationDiagnosticCode.NAIVE_DATETIME_REJECTED
        for item in result.diagnostics
    )


@pytest.mark.parametrize("protocol_provider", ["api", "rss", "ftp", "ftps"])
def test_manual_mapping_values_route_through_same_boundary(protocol_provider: str) -> None:
    values = {
        CanonicalTenderField.EXTERNAL_ID: "0007",
        CanonicalTenderField.PROCUREMENT_NUMBER: "001122",
        CanonicalTenderField.TITLE: "Manual tender",
        CanonicalTenderField.CUSTOMER_NAME: "Customer",
        CanonicalTenderField.SOURCE_URL: "https://example.test/record/0007",
        CanonicalTenderField.PRICE_AMOUNT: Decimal("10.50"),
        CanonicalTenderField.PRICE_CURRENCY: "RUB",
        CanonicalTenderField.APPLICATION_DEADLINE: datetime(2026, 7, 20, tzinfo=timezone.utc),
    }
    provenance = tuple(
        MappingProvenance(field, ("record", field.value), (), "mapped", 1) for field in values
    )

    result = TenderNormalizer().normalize_manual_mapping(
        values,
        provenance=provenance,
        provider_id=f"manual_{protocol_provider}",
    )

    assert result.contract_version == TENDER_NORMALIZATION_CONTRACT_VERSION
    assert result.tender.source is TenderSource.CUSTOM
    assert result.tender.external_id == "0007"
    assert result.tender.price == TenderMoney(Decimal("10.50"), "RUB")
    assert all(item.provider_id == f"manual_{protocol_provider}" for item in result.provenance)


def test_normalization_does_not_mutate_source_or_use_current_time() -> None:
    source = _tender()
    before_payload = tender_to_payload(source)

    result = TenderNormalizer().normalize(source)

    assert tender_to_payload(source) == before_payload
    assert result.tender is not source
    assert "normalized_at" not in result.tender.raw_metadata


def test_resource_limits_are_bounded_and_explicit() -> None:
    result = TenderNormalizer().normalize(
        _tender(tags=tuple(f"tag-{index:03d}" for index in range(300)))
    )

    assert len(result.tender.tags) == 256
    assert any(
        item.code is NormalizationDiagnosticCode.RESOURCE_LIMIT_EXCEEDED and item.field == "tags"
        for item in result.diagnostics
    )
