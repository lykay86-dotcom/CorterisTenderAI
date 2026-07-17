"""RM-135 static compiler and no-side-effect runtime adapter contract."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.tenders.collector.manual_adapter import (
    AdapterCompileStatus,
    CanonicalTenderField,
    FieldMappingSpec,
    ManualAdapterDataFormat,
    ManualAdapterDependencies,
    ManualAdapterLiveOperationError,
    RecordSelectorSpec,
    SourceRequestSpec,
    compile_manual_adapter,
    create_manual_adapter_spec,
)
from app.tenders.collector.manual_provider_protocol import (
    ManualProviderAuthenticationKind,
    ManualProviderPayloadFormat,
    ManualProviderProtocolDraft,
    ManualProviderProtocolFamily,
    create_manual_provider_protocol_selection,
)
from app.tenders.collector.manual_provider_registration import (
    ManualProviderLifecycle,
    ManualProviderRegistration,
)
from app.tenders.provider_base import TenderSearchQuery


MANUAL_ID = f"manual_{'b' * 32}"
NOW = datetime(2026, 7, 17, 14, 30, tzinfo=timezone.utc)


def _registration(family: ManualProviderProtocolFamily) -> ManualProviderRegistration:
    payload = {
        ManualProviderProtocolFamily.API: ManualProviderPayloadFormat.JSON,
        ManualProviderProtocolFamily.RSS: ManualProviderPayloadFormat.RSS,
    }.get(family)
    scheme = {"api": "https", "rss": "https", "ftp": "ftp", "ftps": "ftps"}[family.value]
    auth = (
        ManualProviderAuthenticationKind.USERNAME_PASSWORD
        if family in {ManualProviderProtocolFamily.FTP, ManualProviderProtocolFamily.FTPS}
        else ManualProviderAuthenticationKind.NONE
    )
    selection = create_manual_provider_protocol_selection(
        ManualProviderProtocolDraft(
            family=family,
            endpoint_url=f"{scheme}://source.example.test/tenders",
            payload_format=payload,
            authentication_kind=auth,
        ),
        timestamp=NOW,
    )
    return ManualProviderRegistration(
        provider_id=MANUAL_ID,
        display_name="Площадка",
        homepage_url="https://example.test",
        lifecycle_state=ManualProviderLifecycle.ADAPTER_REQUIRED,
        protocol_selection=selection,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.parametrize("family", tuple(ManualProviderProtocolFamily))
def test_static_compiler_dispatches_all_families_without_invoking_dependencies(family) -> None:
    calls: list[str] = []
    registration = _registration(family)
    data_format = {
        ManualProviderProtocolFamily.API: ManualAdapterDataFormat.JSON,
        ManualProviderProtocolFamily.RSS: ManualAdapterDataFormat.RSS,
        ManualProviderProtocolFamily.FTP: ManualAdapterDataFormat.CSV,
        ManualProviderProtocolFamily.FTPS: ManualAdapterDataFormat.CSV,
    }[family]
    spec = create_manual_adapter_spec(
        provider_id=MANUAL_ID,
        protocol_family=family,
        source=SourceRequestSpec(
            data_format=data_format, filename_suffix=".csv" if "ftp" in family.value else ""
        ),
        record_selector=RecordSelectorSpec(path=("items",)),
        field_mappings=(FieldMappingSpec(CanonicalTenderField.TITLE, ("title",), required=True),),
        revision=1,
        timestamp=NOW,
    )
    dependencies = ManualAdapterDependencies(
        transport=lambda *_args, **_kwargs: calls.append("transport"),
        credential_resolver=lambda *_args, **_kwargs: calls.append("credential"),
    )

    result = compile_manual_adapter(registration, spec, dependencies=dependencies)

    assert result.status is AdapterCompileStatus.VALID
    assert result.adapter is not None
    assert result.adapter.descriptor.id == MANUAL_ID
    assert result.adapter.spec_revision == 1
    assert calls == []


def test_compiled_adapter_stays_non_runnable_until_rm136() -> None:
    registration = _registration(ManualProviderProtocolFamily.API)
    spec = create_manual_adapter_spec(
        provider_id=MANUAL_ID,
        protocol_family=ManualProviderProtocolFamily.API,
        source=SourceRequestSpec(data_format=ManualAdapterDataFormat.JSON),
        record_selector=RecordSelectorSpec(path=("items",)),
        field_mappings=(FieldMappingSpec(CanonicalTenderField.TITLE, ("title",), required=True),),
        revision=1,
        timestamp=NOW,
    )
    adapter = compile_manual_adapter(registration, spec).adapter
    assert adapter is not None
    with pytest.raises(ManualAdapterLiveOperationError, match="connection_test_required"):
        asyncio.run(adapter.search(TenderSearchQuery()))
