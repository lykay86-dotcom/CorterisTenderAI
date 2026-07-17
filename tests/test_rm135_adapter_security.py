"""RM-135 forbidden-mechanism and private-payload regression contract."""

from __future__ import annotations

import inspect

from dataclasses import replace
from datetime import datetime, timezone

import pytest

import app.tenders.collector.manual_adapter as manual_adapter
from app.tenders.collector.manual_adapter import (
    AdapterResourceLimits,
    CanonicalTenderField,
    FieldMappingSpec,
    ManualAdapterDataFormat,
    RecordSelectorSpec,
    SourceRequestSpec,
    create_manual_adapter_spec,
    decode_manual_adapter_spec,
)
from app.tenders.collector.manual_provider_protocol import ManualProviderProtocolFamily


def test_manual_adapter_domain_has_no_dynamic_execution_or_import_path() -> None:
    source = inspect.getsource(manual_adapter)
    forbidden = (
        "eval(",
        "exec(",
        "pickle.loads",
        "marshal.loads",
        "import_module(",
        "entry_points(",
        "subprocess.",
        "os.system(",
    )
    assert not any(marker in source for marker in forbidden)


def test_manual_adapter_module_does_not_import_legacy_tester_or_keyring() -> None:
    source = inspect.getsource(manual_adapter)
    assert "ManualConnectorTester" not in source
    assert "load_secret" not in source
    assert "keyring" not in source


def test_persisted_decoder_rejects_unknown_fields_and_boolean_integer_confusion() -> None:
    now = datetime(2026, 7, 17, 18, 0, tzinfo=timezone.utc)
    spec = create_manual_adapter_spec(
        provider_id=f"manual_{'f' * 32}",
        protocol_family=ManualProviderProtocolFamily.API,
        source=SourceRequestSpec(ManualAdapterDataFormat.JSON),
        record_selector=RecordSelectorSpec(("items",)),
        field_mappings=(FieldMappingSpec(CanonicalTenderField.TITLE, ("title",)),),
        revision=1,
        timestamp=now,
    )
    unknown = spec.persisted_payload()
    unknown["script"] = "run()"
    with pytest.raises(ValueError, match="fields"):
        decode_manual_adapter_spec(unknown)

    invalid_revision = spec.persisted_payload()
    invalid_revision["revision"] = True
    with pytest.raises(ValueError, match="spec"):
        decode_manual_adapter_spec(invalid_revision)
    with pytest.raises(ValueError, match="resource limit"):
        replace(AdapterResourceLimits(), max_records=True)
