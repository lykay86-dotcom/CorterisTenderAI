"""RM-135 bounded offline sample parsing, mapping and provenance."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.tenders.collector.manual_adapter import (
    CanonicalTenderField,
    FieldMappingSpec,
    FieldTransformSpec,
    ManualAdapterDataFormat,
    ManualAdapterTransform,
    RecordSelectorSpec,
    SourceRequestSpec,
    create_manual_adapter_spec,
    preview_manual_adapter,
)
from app.tenders.collector.manual_provider_protocol import ManualProviderProtocolFamily


MANUAL_ID = f"manual_{'c' * 32}"
NOW = datetime(2026, 7, 17, 15, 0, tzinfo=timezone.utc)


def _spec():
    return create_manual_adapter_spec(
        provider_id=MANUAL_ID,
        protocol_family=ManualProviderProtocolFamily.API,
        source=SourceRequestSpec(data_format=ManualAdapterDataFormat.JSON),
        record_selector=RecordSelectorSpec(path=("result", "items")),
        field_mappings=(
            FieldMappingSpec(CanonicalTenderField.EXTERNAL_ID, ("id",), required=True),
            FieldMappingSpec(CanonicalTenderField.TITLE, ("title",), required=True),
            FieldMappingSpec(
                CanonicalTenderField.PRICE_AMOUNT,
                ("price",),
                (FieldTransformSpec(ManualAdapterTransform.DECIMAL),),
            ),
            FieldMappingSpec(
                CanonicalTenderField.APPLICATION_DEADLINE,
                ("deadline",),
                (FieldTransformSpec(ManualAdapterTransform.DATETIME_AWARE),),
            ),
        ),
        revision=1,
        timestamp=NOW,
    )


def test_json_preview_is_bounded_typed_and_explicitly_unverified() -> None:
    result = preview_manual_adapter(
        _spec(),
        b'{"result":{"items":[{"id":"42","title":" Tender ","price":"1234.50","deadline":"2026-08-01T12:00:00+03:00"}]}}',
    )

    assert result.offline is True
    assert result.connection_verified is False
    assert len(result.records) == 1
    record = result.records[0]
    assert record.values[CanonicalTenderField.PRICE_AMOUNT] == Decimal("1234.50")
    assert record.values[CanonicalTenderField.APPLICATION_DEADLINE].utcoffset() is not None
    assert all(item.spec_revision == 1 for item in record.provenance)


def test_xml_dtd_is_rejected_without_echoing_payload() -> None:
    spec = create_manual_adapter_spec(
        provider_id=MANUAL_ID,
        protocol_family=ManualProviderProtocolFamily.API,
        source=SourceRequestSpec(data_format=ManualAdapterDataFormat.XML),
        record_selector=RecordSelectorSpec(path=("items", "item")),
        field_mappings=(FieldMappingSpec(CanonicalTenderField.TITLE, ("title",), required=True),),
        revision=1,
        timestamp=NOW,
    )
    sentinel = "RM135_RAW_SAMPLE_SENTINEL"
    result = preview_manual_adapter(spec, f'<!DOCTYPE x [<!ENTITY e "{sentinel}">]><items/>')

    assert result.records == ()
    assert result.has_errors
    assert sentinel not in repr(result)
    assert sentinel not in " ".join(item.message for item in result.diagnostics)


@pytest.mark.parametrize(
    ("data_format", "selector", "sample"),
    (
        (
            ManualAdapterDataFormat.RSS,
            ("rss", "channel", "item"),
            "<rss><channel><item><title>RSS tender</title></item></channel></rss>",
        ),
        (
            ManualAdapterDataFormat.ATOM,
            ("feed", "entry"),
            '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom tender</title></entry></feed>',
        ),
    ),
)
def test_feed_preview_supports_rss_and_namespaced_atom(data_format, selector, sample) -> None:
    spec = create_manual_adapter_spec(
        provider_id=MANUAL_ID,
        protocol_family=ManualProviderProtocolFamily.RSS,
        source=SourceRequestSpec(data_format=data_format),
        record_selector=RecordSelectorSpec(path=selector),
        field_mappings=(FieldMappingSpec(CanonicalTenderField.TITLE, ("title",), required=True),),
        revision=1,
        timestamp=NOW,
    )

    result = preview_manual_adapter(spec, sample)

    assert not result.has_errors
    assert result.records[0].values[CanonicalTenderField.TITLE].endswith("tender")


def test_csv_preview_and_record_limit_are_bounded() -> None:
    spec = create_manual_adapter_spec(
        provider_id=MANUAL_ID,
        protocol_family=ManualProviderProtocolFamily.FTP,
        source=SourceRequestSpec(data_format=ManualAdapterDataFormat.CSV, filename_suffix=".csv"),
        record_selector=RecordSelectorSpec(path=("records",)),
        field_mappings=(FieldMappingSpec(CanonicalTenderField.TITLE, ("title",), required=True),),
        revision=1,
        timestamp=NOW,
    )
    result = preview_manual_adapter(spec, "title\nCSV tender\n")

    assert not result.has_errors
    assert result.records[0].values[CanonicalTenderField.TITLE] == "CSV tender"
