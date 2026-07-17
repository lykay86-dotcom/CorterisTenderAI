"""RM-135 immutable declarative custom-adapter specification contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from app.tenders.collector.manual_adapter import (
    MANUAL_ADAPTER_SPEC_VERSION,
    AdapterResourceLimits,
    CanonicalTenderField,
    FieldMappingSpec,
    FieldTransformSpec,
    ManualAdapterDataFormat,
    ManualAdapterTransform,
    RecordSelectorSpec,
    SourceRequestSpec,
    create_manual_adapter_spec,
)
from app.tenders.collector.manual_provider_protocol import ManualProviderProtocolFamily


MANUAL_ID = f"manual_{'a' * 32}"
NOW = datetime(2026, 7, 17, 14, 0, tzinfo=timezone.utc)


def _spec(*, timestamp: datetime = NOW, revision: int = 1):
    return create_manual_adapter_spec(
        provider_id=MANUAL_ID,
        protocol_family=ManualProviderProtocolFamily.API,
        source=SourceRequestSpec(data_format=ManualAdapterDataFormat.JSON),
        record_selector=RecordSelectorSpec(path=("result", "items")),
        field_mappings=(
            FieldMappingSpec(
                target_field=CanonicalTenderField.EXTERNAL_ID,
                source_path=("id",),
                required=True,
            ),
            FieldMappingSpec(
                target_field=CanonicalTenderField.TITLE,
                source_path=("name",),
                transforms=(FieldTransformSpec(ManualAdapterTransform.TRIM),),
                required=True,
            ),
        ),
        limits=AdapterResourceLimits(),
        revision=revision,
        timestamp=timestamp,
    )


def test_spec_is_frozen_versioned_and_fingerprint_is_semantic() -> None:
    first = _spec()
    later = _spec(timestamp=NOW + timedelta(hours=1))

    assert first.spec_version == MANUAL_ADAPTER_SPEC_VERSION == 1
    assert first.fingerprint == later.fingerprint
    assert first.created_at.utcoffset() is not None
    assert first.public_payload()["fingerprint"] == first.fingerprint
    assert "endpoint" not in repr(first).casefold()
    with pytest.raises(FrozenInstanceError):
        first.revision = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    "path",
    (("..",), ("*",), ("$", "items"), ("items[?(@.x)]",), ("a()",)),
)
def test_selector_rejects_executable_or_unrestricted_path(path: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="selector"):
        RecordSelectorSpec(path=path)


def test_resource_caps_can_only_be_tightened() -> None:
    limits = AdapterResourceLimits(max_sample_bytes=64_000, max_records=25)
    assert limits.max_sample_bytes == 64_000
    assert limits.max_records == 25
    with pytest.raises(ValueError, match="resource limit"):
        AdapterResourceLimits(max_sample_bytes=100_000_000)
