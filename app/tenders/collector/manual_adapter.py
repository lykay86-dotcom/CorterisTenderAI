"""Declarative manual-adapter specification, offline preview and compiler.

The module is deliberately pure with respect to external systems: it does not
open files, resolve DNS, perform network requests, read credentials or create
background work.  Runtime adapters remain admission-blocked until RM-136.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import csv
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import hashlib
from io import StringIO
import json
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, NoReturn
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree

from app.tenders.collector.async_provider import AsyncTenderProvider
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.manual_provider_protocol import ManualProviderProtocolFamily
from app.tenders.models import TenderDocument, TenderSource, UnifiedTender
from app.tenders.provider_base import (
    ProviderCapabilities,
    ProviderCapabilityError,
    ProviderDescriptor,
    ProviderHealth,
    TenderSearchQuery,
    TenderSearchResult,
)

if TYPE_CHECKING:
    from app.tenders.collector.manual_provider_registration import ManualProviderRegistration


MANUAL_ADAPTER_SPEC_VERSION = 1
_MANUAL_ID = re.compile(r"manual_[0-9a-f]{32}\Z")
_PATH_SEGMENT = re.compile(r"(?:\{[^{}\s]{1,200}\})?[A-Za-z_][A-Za-z0-9_.-]{0,127}\Z")
_SUFFIX = re.compile(r"\.[A-Za-z0-9]{1,12}\Z")
_FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")
_XML_FORBIDDEN = (b"<!doctype", b"<!entity", b"<xi:include", b"xinclude")
_MAX_SAMPLE_BYTES = 2 * 1024 * 1024
_MAX_RECORDS = 500
_MAX_PREVIEW_RECORDS = 25
_MAX_NESTING_DEPTH = 32
_MAX_MAPPINGS = 64
_MAX_STRING_CHARS = 16_384
_MAX_SELECTOR_DEPTH = 12


class ManualAdapterDataFormat(StrEnum):
    JSON = "json"
    XML = "xml"
    RSS = "rss"
    ATOM = "atom"
    CSV = "csv"


class ManualAdapterTransform(StrEnum):
    TRIM = "trim"
    COLLAPSE_WHITESPACE = "collapse_whitespace"
    EMPTY_TO_MISSING = "empty_to_missing"
    UNICODE_NFKC = "unicode_nfkc"
    DECIMAL = "decimal"
    DATETIME_AWARE = "datetime_aware"
    URL = "url"


class CanonicalTenderField(StrEnum):
    EXTERNAL_ID = "external_id"
    PROCUREMENT_NUMBER = "procurement_number"
    TITLE = "title"
    CUSTOMER_NAME = "customer.name"
    CUSTOMER_INN = "customer.inn"
    PRICE_AMOUNT = "price.amount"
    PRICE_CURRENCY = "price.currency"
    PUBLISHED_AT = "published_at"
    APPLICATION_DEADLINE = "application_deadline"
    STATUS = "status"
    LAW = "law"
    REGION = "region"
    DESCRIPTION = "description"
    SOURCE_URL = "source_url"


class AdapterDiagnosticSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AdapterDiagnosticCode(StrEnum):
    SPEC_INVALID = "spec_invalid"
    SPEC_VERSION_UNSUPPORTED = "spec_version_unsupported"
    PROTOCOL_UNSUPPORTED = "protocol_unsupported"
    FORMAT_UNSUPPORTED = "format_unsupported"
    SAMPLE_TOO_LARGE = "sample_too_large"
    SAMPLE_PARSE_FAILED = "sample_parse_failed"
    SELECTOR_INVALID = "selector_invalid"
    MAPPING_INCOMPLETE = "mapping_incomplete"
    TRANSFORM_INVALID = "transform_invalid"
    CONNECTION_TEST_REQUIRED = "connection_test_required"


class AdapterCompileStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


class ManualAdapterReadiness(StrEnum):
    CONNECTION_TEST_REQUIRED = "connection_test_required"


class ManualAdapterCommandStatus(StrEnum):
    SAVED = "saved"
    UNCHANGED = "unchanged"
    CLEARED = "cleared"
    ROLLED_BACK = "rolled_back"
    INVALID = "invalid"
    STALE = "stale"
    NOT_FOUND = "not_found"
    UNSUPPORTED_TARGET = "unsupported_target"
    PERSISTENCE_UNAVAILABLE = "persistence_unavailable"
    OPERATION_FAILED_SAFE = "operation_failed_safe"


@dataclass(frozen=True, slots=True)
class AdapterDiagnostic:
    field_path: str
    code: AdapterDiagnosticCode
    severity: AdapterDiagnosticSeverity
    message: str


@dataclass(frozen=True, slots=True)
class ManualAdapterCommandResult:
    provider_id: str
    status: ManualAdapterCommandStatus
    readiness: ManualAdapterReadiness
    diagnostics: tuple[AdapterDiagnostic, ...]
    fingerprint: str
    revision: int | None
    message: str
    observed_at: datetime

    def __post_init__(self) -> None:
        _aware(self.observed_at)


@dataclass(frozen=True, slots=True)
class SourceRequestSpec:
    data_format: ManualAdapterDataFormat
    http_method: str = "GET"
    filename_suffix: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.data_format, ManualAdapterDataFormat):
            raise ValueError("source request format is invalid")
        if self.http_method != "GET":
            raise ValueError("source request supports GET only")
        suffix = self.filename_suffix.casefold()
        if suffix and not _SUFFIX.fullmatch(suffix):
            raise ValueError("source request filename suffix is invalid")
        object.__setattr__(self, "filename_suffix", suffix)

    def payload(self) -> dict[str, object]:
        return {
            "data_format": self.data_format.value,
            "http_method": self.http_method,
            "filename_suffix": self.filename_suffix,
        }


@dataclass(frozen=True, slots=True)
class RecordSelectorSpec:
    path: tuple[str, ...]

    def __post_init__(self) -> None:
        normalized = tuple(str(item) for item in self.path)
        if (
            not normalized
            or len(normalized) > _MAX_SELECTOR_DEPTH
            or any(not _PATH_SEGMENT.fullmatch(item) for item in normalized)
        ):
            raise ValueError("record selector is invalid")
        object.__setattr__(self, "path", normalized)

    def payload(self) -> dict[str, object]:
        return {"path": list(self.path)}


@dataclass(frozen=True, slots=True)
class FieldTransformSpec:
    kind: ManualAdapterTransform

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ManualAdapterTransform):
            raise ValueError("field transform is invalid")


@dataclass(frozen=True, slots=True)
class FieldMappingSpec:
    target_field: CanonicalTenderField
    source_path: tuple[str, ...]
    transforms: tuple[FieldTransformSpec, ...] = ()
    required: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.target_field, CanonicalTenderField):
            raise ValueError("mapping target is invalid")
        normalized = tuple(str(item) for item in self.source_path)
        if (
            not normalized
            or len(normalized) > _MAX_SELECTOR_DEPTH
            or any(not _PATH_SEGMENT.fullmatch(item) for item in normalized)
        ):
            raise ValueError("mapping source path is invalid")
        if len(self.transforms) > 8 or any(
            not isinstance(item, FieldTransformSpec) for item in self.transforms
        ):
            raise ValueError("mapping transforms are invalid")
        if not isinstance(self.required, bool):
            raise ValueError("mapping required flag is invalid")
        object.__setattr__(self, "source_path", normalized)

    def payload(self) -> dict[str, object]:
        return {
            "target_field": self.target_field.value,
            "source_path": list(self.source_path),
            "transforms": [item.kind.value for item in self.transforms],
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class AdapterResourceLimits:
    max_sample_bytes: int = 1_048_576
    max_records: int = 100
    max_preview_records: int = 10
    max_nesting_depth: int = 16
    max_string_chars: int = 4096

    def __post_init__(self) -> None:
        values = (
            (self.max_sample_bytes, 1, _MAX_SAMPLE_BYTES),
            (self.max_records, 1, _MAX_RECORDS),
            (self.max_preview_records, 1, _MAX_PREVIEW_RECORDS),
            (self.max_nesting_depth, 1, _MAX_NESTING_DEPTH),
            (self.max_string_chars, 1, _MAX_STRING_CHARS),
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high
            for value, low, high in values
        ):
            raise ValueError("resource limit is invalid")
        if self.max_preview_records > self.max_records:
            raise ValueError("resource limit is invalid")

    def payload(self) -> dict[str, int]:
        return {
            "max_sample_bytes": self.max_sample_bytes,
            "max_records": self.max_records,
            "max_preview_records": self.max_preview_records,
            "max_nesting_depth": self.max_nesting_depth,
            "max_string_chars": self.max_string_chars,
        }


@dataclass(frozen=True, slots=True)
class ManualAdapterSpec:
    spec_version: int
    provider_id: str
    protocol_family: ManualProviderProtocolFamily
    source: SourceRequestSpec
    record_selector: RecordSelectorSpec
    field_mappings: tuple[FieldMappingSpec, ...]
    limits: AdapterResourceLimits
    revision: int
    fingerprint: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.spec_version, int)
            or isinstance(self.spec_version, bool)
            or self.spec_version != MANUAL_ADAPTER_SPEC_VERSION
        ):
            raise ValueError("manual adapter spec version is unsupported")
        if not _MANUAL_ID.fullmatch(self.provider_id):
            raise ValueError("manual adapter provider identity is invalid")
        if not isinstance(self.protocol_family, ManualProviderProtocolFamily):
            raise ValueError("manual adapter protocol is invalid")
        if not isinstance(self.source, SourceRequestSpec) or not isinstance(
            self.record_selector, RecordSelectorSpec
        ):
            raise ValueError("manual adapter spec is invalid")
        if not 1 <= len(self.field_mappings) <= _MAX_MAPPINGS:
            raise ValueError("manual adapter mappings are invalid")
        if any(not isinstance(item, FieldMappingSpec) for item in self.field_mappings):
            raise ValueError("manual adapter mappings are invalid")
        targets = tuple(item.target_field for item in self.field_mappings)
        if len(targets) != len(set(targets)):
            raise ValueError("manual adapter mapping target is duplicated")
        if (
            not isinstance(self.limits, AdapterResourceLimits)
            or not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 1
        ):
            raise ValueError("manual adapter spec is invalid")
        _aware(self.created_at)
        _aware(self.updated_at)
        if self.updated_at < self.created_at:
            raise ValueError("manual adapter timestamps are invalid")
        expected = _semantic_fingerprint(self)
        if not _FINGERPRINT.fullmatch(self.fingerprint) or self.fingerprint != expected:
            raise ValueError("manual adapter fingerprint is invalid")

    def semantic_payload(self) -> dict[str, object]:
        return {
            "spec_version": self.spec_version,
            "provider_id": self.provider_id,
            "protocol_family": self.protocol_family.value,
            "source": self.source.payload(),
            "record_selector": self.record_selector.payload(),
            "field_mappings": [item.payload() for item in self.field_mappings],
            "limits": self.limits.payload(),
        }

    def persisted_payload(self) -> dict[str, object]:
        return {
            **self.semantic_payload(),
            "revision": self.revision,
            "fingerprint": self.fingerprint,
            "created_at": self.created_at.isoformat(timespec="microseconds"),
            "updated_at": self.updated_at.isoformat(timespec="microseconds"),
        }

    def public_payload(self) -> dict[str, object]:
        return {
            "spec_version": self.spec_version,
            "provider_id": self.provider_id,
            "protocol_family": self.protocol_family.value,
            "revision": self.revision,
            "fingerprint": self.fingerprint,
            "mapping_count": len(self.field_mappings),
            "readiness": ManualAdapterReadiness.CONNECTION_TEST_REQUIRED.value,
        }


def create_manual_adapter_spec(
    *,
    provider_id: str,
    protocol_family: ManualProviderProtocolFamily,
    source: SourceRequestSpec,
    record_selector: RecordSelectorSpec,
    field_mappings: Sequence[FieldMappingSpec],
    revision: int,
    timestamp: datetime,
    limits: AdapterResourceLimits | None = None,
    created_at: datetime | None = None,
) -> ManualAdapterSpec:
    _aware(timestamp)
    semantic = {
        "spec_version": MANUAL_ADAPTER_SPEC_VERSION,
        "provider_id": provider_id,
        "protocol_family": protocol_family.value,
        "source": source.payload(),
        "record_selector": record_selector.payload(),
        "field_mappings": [item.payload() for item in field_mappings],
        "limits": (limits or AdapterResourceLimits()).payload(),
    }
    fingerprint = hashlib.sha256(_stable_json(semantic).encode()).hexdigest()
    return ManualAdapterSpec(
        spec_version=MANUAL_ADAPTER_SPEC_VERSION,
        provider_id=provider_id,
        protocol_family=protocol_family,
        source=source,
        record_selector=record_selector,
        field_mappings=tuple(field_mappings),
        limits=limits or AdapterResourceLimits(),
        revision=revision,
        fingerprint=fingerprint,
        created_at=created_at or timestamp,
        updated_at=timestamp,
    )


def parse_restricted_path(value: str) -> tuple[str, ...]:
    """Parse UI path text through the same bounded selector contract."""

    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("manual adapter path is invalid")
    path = tuple(segment.strip() for segment in value.split(".") if segment.strip())
    return RecordSelectorSpec(path).path


def parse_field_mapping_lines(value: str) -> tuple[FieldMappingSpec, ...]:
    """Decode a bounded declarative mapping list; no expression syntax is accepted."""

    if not isinstance(value, str) or len(value) > _MAX_STRING_CHARS:
        raise ValueError("manual adapter mapping is invalid")
    mappings: list[FieldMappingSpec] = []
    for line in value.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        target, separator, source = stripped.partition("=")
        if not separator:
            raise ValueError("manual adapter mapping is invalid")
        required = target.startswith("!")
        target = target.removeprefix("!").strip()
        mappings.append(
            FieldMappingSpec(
                target_field=CanonicalTenderField(target),
                source_path=parse_restricted_path(source),
                required=required,
            )
        )
    if not mappings:
        raise ValueError("manual adapter mapping is invalid")
    return tuple(mappings)


def decode_manual_adapter_spec(value: object) -> ManualAdapterSpec:
    """Strictly decode one persisted spec without accepting unknown fields."""

    if not isinstance(value, Mapping):
        raise TypeError("manual adapter spec must be an object")
    allowed = {
        "spec_version",
        "provider_id",
        "protocol_family",
        "source",
        "record_selector",
        "field_mappings",
        "limits",
        "revision",
        "fingerprint",
        "created_at",
        "updated_at",
    }
    if set(value) != allowed:
        raise ValueError("manual adapter spec fields are invalid")
    raw_source = value["source"]
    raw_selector = value["record_selector"]
    raw_mappings = value["field_mappings"]
    raw_limits = value["limits"]
    if (
        not isinstance(raw_source, Mapping)
        or set(raw_source) != {"data_format", "http_method", "filename_suffix"}
        or not isinstance(raw_selector, Mapping)
        or set(raw_selector) != {"path"}
        or not isinstance(raw_mappings, list)
        or not isinstance(raw_limits, Mapping)
        or set(raw_limits)
        != {
            "max_sample_bytes",
            "max_records",
            "max_preview_records",
            "max_nesting_depth",
            "max_string_chars",
        }
    ):
        raise TypeError("manual adapter spec nested fields are invalid")
    mappings: list[FieldMappingSpec] = []
    for raw in raw_mappings:
        if not isinstance(raw, Mapping) or set(raw) != {
            "target_field",
            "source_path",
            "transforms",
            "required",
        }:
            raise TypeError("manual adapter mapping is invalid")
        transforms = raw["transforms"]
        source_path = raw["source_path"]
        if not isinstance(transforms, list) or not isinstance(source_path, list):
            raise TypeError("manual adapter mapping is invalid")
        mappings.append(
            FieldMappingSpec(
                target_field=CanonicalTenderField(str(raw["target_field"])),
                source_path=tuple(str(item) for item in source_path),
                transforms=tuple(
                    FieldTransformSpec(ManualAdapterTransform(str(item))) for item in transforms
                ),
                required=raw["required"],
            )
        )
    selector_path = raw_selector["path"]
    if not isinstance(selector_path, list):
        raise TypeError("manual adapter selector is invalid")
    return ManualAdapterSpec(
        spec_version=value["spec_version"],
        provider_id=str(value["provider_id"]),
        protocol_family=ManualProviderProtocolFamily(str(value["protocol_family"])),
        source=SourceRequestSpec(
            data_format=ManualAdapterDataFormat(str(raw_source["data_format"])),
            http_method=raw_source["http_method"],
            filename_suffix=raw_source["filename_suffix"],
        ),
        record_selector=RecordSelectorSpec(tuple(str(item) for item in selector_path)),
        field_mappings=tuple(mappings),
        limits=AdapterResourceLimits(**raw_limits),
        revision=value["revision"],
        fingerprint=str(value["fingerprint"]),
        created_at=_parse_datetime(value["created_at"]),
        updated_at=_parse_datetime(value["updated_at"]),
    )


@dataclass(frozen=True, slots=True)
class MappingProvenance:
    target_field: CanonicalTenderField
    source_path: tuple[str, ...]
    transforms: tuple[ManualAdapterTransform, ...]
    status: str
    spec_revision: int


@dataclass(frozen=True, slots=True)
class ManualAdapterPreviewRecord:
    values: Mapping[CanonicalTenderField, object] = field(repr=False)
    provenance: tuple[MappingProvenance, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True, slots=True)
class ManualAdapterPreviewResult:
    records: tuple[ManualAdapterPreviewRecord, ...]
    diagnostics: tuple[AdapterDiagnostic, ...]
    offline: bool = True
    connection_verified: bool = False

    @property
    def has_errors(self) -> bool:
        return any(item.severity is AdapterDiagnosticSeverity.ERROR for item in self.diagnostics)


def preview_manual_adapter(
    spec: ManualAdapterSpec, sample: str | bytes
) -> ManualAdapterPreviewResult:
    try:
        payload = sample.encode("utf-8") if isinstance(sample, str) else bytes(sample)
    except (UnicodeError, TypeError, ValueError):
        return _preview_failure(AdapterDiagnosticCode.SAMPLE_PARSE_FAILED)
    if len(payload) > spec.limits.max_sample_bytes:
        return _preview_failure(AdapterDiagnosticCode.SAMPLE_TOO_LARGE)
    try:
        raw_records = _parse_records(spec, payload)
    except (
        ValueError,
        TypeError,
        UnicodeError,
        RecursionError,
        json.JSONDecodeError,
        csv.Error,
        ElementTree.ParseError,
    ):
        return _preview_failure(AdapterDiagnosticCode.SAMPLE_PARSE_FAILED)
    diagnostics: list[AdapterDiagnostic] = []
    records: list[ManualAdapterPreviewRecord] = []
    for raw_record in raw_records[: spec.limits.max_preview_records]:
        values: dict[CanonicalTenderField, object] = {}
        provenance: list[MappingProvenance] = []
        for mapping in spec.field_mappings:
            raw_value = _read_path(raw_record, mapping.source_path)
            try:
                value = _apply_transforms(raw_value, mapping.transforms, spec.limits)
            except (ValueError, TypeError, InvalidOperation, OverflowError):
                diagnostics.append(
                    AdapterDiagnostic(
                        mapping.target_field.value,
                        AdapterDiagnosticCode.TRANSFORM_INVALID,
                        AdapterDiagnosticSeverity.ERROR,
                        "Значение sample не прошло разрешённое преобразование.",
                    )
                )
                value = None
            if value in (None, "") and mapping.required:
                diagnostics.append(
                    AdapterDiagnostic(
                        mapping.target_field.value,
                        AdapterDiagnosticCode.MAPPING_INCOMPLETE,
                        AdapterDiagnosticSeverity.ERROR,
                        "В sample отсутствует обязательное каноническое поле.",
                    )
                )
            if value not in (None, ""):
                values[mapping.target_field] = value
            provenance.append(
                MappingProvenance(
                    target_field=mapping.target_field,
                    source_path=mapping.source_path,
                    transforms=tuple(item.kind for item in mapping.transforms),
                    status="mapped" if value not in (None, "") else "missing",
                    spec_revision=spec.revision,
                )
            )
        records.append(ManualAdapterPreviewRecord(values, tuple(provenance)))
    return ManualAdapterPreviewResult(tuple(records), tuple(diagnostics))


@dataclass(frozen=True, slots=True)
class ManualAdapterDependencies:
    transport: object | None = field(default=None, repr=False, compare=False)
    credential_resolver: object | None = field(default=None, repr=False, compare=False)


class ManualAdapterLiveOperationError(ProviderCapabilityError):
    """Live execution is intentionally unavailable before RM-136."""

    def __init__(self) -> None:
        super().__init__(AdapterDiagnosticCode.CONNECTION_TEST_REQUIRED.value)


class CompiledManualTenderProvider(AsyncTenderProvider):
    parser_version = "manual-spec-v1"

    def __init__(
        self,
        registration: ManualProviderRegistration,
        spec: ManualAdapterSpec,
        dependencies: ManualAdapterDependencies,
    ) -> None:
        self.spec = spec
        self.spec_revision = spec.revision
        self.spec_fingerprint = spec.fingerprint
        self.protocol_family = spec.protocol_family
        self._dependencies = dependencies
        self.connection_mode = f"manual_{spec.protocol_family.value}_unverified"
        self.descriptor = ProviderDescriptor(
            id=spec.provider_id,
            display_name=registration.display_name,
            source=TenderSource.CUSTOM,
            homepage_url=registration.homepage_url,
            capabilities=ProviderCapabilities(search=True),
            enabled_by_default=False,
            implementation_status="connection_test_required",
        )

    async def search(
        self,
        query: TenderSearchQuery,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> TenderSearchResult:
        self._deny(cancellation_token)

    async def get_tender(
        self,
        external_id: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> UnifiedTender:
        self._deny(cancellation_token)

    async def list_documents(
        self,
        external_id: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> Sequence[TenderDocument]:
        self._deny(cancellation_token)

    async def check_health(
        self,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> ProviderHealth:
        self._deny(cancellation_token)

    def validate_configuration(self) -> tuple[str, ...]:
        return (AdapterDiagnosticCode.CONNECTION_TEST_REQUIRED.value,)

    @staticmethod
    def _deny(cancellation_token: CollectorCancellationToken | None) -> NoReturn:
        if cancellation_token is not None:
            cancellation_token.throw_if_cancelled()
        raise ManualAdapterLiveOperationError()


@dataclass(frozen=True, slots=True)
class AdapterCompileResult:
    status: AdapterCompileStatus
    adapter: CompiledManualTenderProvider | None
    diagnostics: tuple[AdapterDiagnostic, ...]
    fingerprint: str


def compile_manual_adapter(
    registration: ManualProviderRegistration,
    spec: ManualAdapterSpec,
    *,
    dependencies: ManualAdapterDependencies | None = None,
) -> AdapterCompileResult:
    selection = getattr(registration, "protocol_selection", None)
    if (
        getattr(registration, "provider_id", None) != spec.provider_id
        or selection is None
        or selection.family is not spec.protocol_family
    ):
        return _compile_failure(
            spec, AdapterCompileStatus.INVALID, AdapterDiagnosticCode.SPEC_INVALID
        )
    allowed_formats = {
        ManualProviderProtocolFamily.API: {
            ManualAdapterDataFormat.JSON,
            ManualAdapterDataFormat.XML,
        },
        ManualProviderProtocolFamily.RSS: {
            ManualAdapterDataFormat.RSS,
            ManualAdapterDataFormat.ATOM,
        },
        ManualProviderProtocolFamily.FTP: {
            ManualAdapterDataFormat.JSON,
            ManualAdapterDataFormat.XML,
            ManualAdapterDataFormat.CSV,
        },
        ManualProviderProtocolFamily.FTPS: {
            ManualAdapterDataFormat.JSON,
            ManualAdapterDataFormat.XML,
            ManualAdapterDataFormat.CSV,
        },
    }
    if spec.source.data_format not in allowed_formats[spec.protocol_family]:
        return _compile_failure(
            spec, AdapterCompileStatus.UNSUPPORTED, AdapterDiagnosticCode.FORMAT_UNSUPPORTED
        )
    if (
        spec.protocol_family
        in {
            ManualProviderProtocolFamily.FTP,
            ManualProviderProtocolFamily.FTPS,
        }
        and not spec.source.filename_suffix
    ):
        return _compile_failure(
            spec, AdapterCompileStatus.INVALID, AdapterDiagnosticCode.SPEC_INVALID
        )
    adapter = _BUILDERS[spec.protocol_family](
        registration, spec, dependencies or ManualAdapterDependencies()
    )
    return AdapterCompileResult(AdapterCompileStatus.VALID, adapter, (), spec.fingerprint)


def _build_adapter(
    registration: ManualProviderRegistration,
    spec: ManualAdapterSpec,
    dependencies: ManualAdapterDependencies,
) -> CompiledManualTenderProvider:
    return CompiledManualTenderProvider(registration, spec, dependencies)


_BUILDERS = MappingProxyType(
    {
        ManualProviderProtocolFamily.API: _build_adapter,
        ManualProviderProtocolFamily.RSS: _build_adapter,
        ManualProviderProtocolFamily.FTP: _build_adapter,
        ManualProviderProtocolFamily.FTPS: _build_adapter,
    }
)


def _compile_failure(
    spec: ManualAdapterSpec,
    status: AdapterCompileStatus,
    code: AdapterDiagnosticCode,
) -> AdapterCompileResult:
    return AdapterCompileResult(
        status,
        None,
        (
            AdapterDiagnostic(
                "spec",
                code,
                AdapterDiagnosticSeverity.ERROR,
                "Спецификация адаптера не поддерживается или несовместима.",
            ),
        ),
        spec.fingerprint,
    )


def _preview_failure(code: AdapterDiagnosticCode) -> ManualAdapterPreviewResult:
    return ManualAdapterPreviewResult(
        (),
        (
            AdapterDiagnostic(
                "sample",
                code,
                AdapterDiagnosticSeverity.ERROR,
                "Offline sample не прошёл безопасную обработку.",
            ),
        ),
    )


def _parse_records(spec: ManualAdapterSpec, payload: bytes) -> list[object]:
    data_format = spec.source.data_format
    if data_format is ManualAdapterDataFormat.JSON:
        decoded = json.loads(payload.decode("utf-8"))
        if _depth(decoded) > spec.limits.max_nesting_depth:
            raise ValueError("sample nesting limit exceeded")
        selected = _read_path(decoded, spec.record_selector.path)
        records = selected if isinstance(selected, list) else [selected]
    elif data_format in {
        ManualAdapterDataFormat.XML,
        ManualAdapterDataFormat.RSS,
        ManualAdapterDataFormat.ATOM,
    }:
        lowered = payload.lower()
        if any(marker in lowered for marker in _XML_FORBIDDEN):
            raise ValueError("unsafe XML")
        root = ElementTree.fromstring(payload)
        records = _select_xml(root, spec.record_selector.path)
    elif data_format is ManualAdapterDataFormat.CSV:
        text = payload.decode("utf-8-sig")
        records = list(csv.DictReader(StringIO(text)))
    else:
        raise ValueError("unsupported sample format")
    if not records or len(records) > spec.limits.max_records:
        raise ValueError("sample record limit exceeded")
    return list(records)


def _select_xml(root: ElementTree.Element, path: tuple[str, ...]) -> list[object]:
    segments = path[1:] if path and _xml_name_matches(root.tag, path[0]) else path
    current = [root]
    for segment in segments:
        current = [
            child
            for node in current
            for child in list(node)
            if _xml_name_matches(child.tag, segment)
        ]
    return list(current)


def _read_path(value: object, path: tuple[str, ...]) -> object | None:
    current = value
    for segment in path:
        if isinstance(current, Mapping):
            current = current.get(segment)
        elif isinstance(current, ElementTree.Element):
            child = next(
                (item for item in list(current) if _xml_name_matches(item.tag, segment)),
                None,
            )
            current = child
        else:
            return None
        if current is None:
            return None
    if isinstance(current, ElementTree.Element):
        return current.text
    return current


def _xml_name_matches(tag: str, selector: str) -> bool:
    return tag == selector or tag.rsplit("}", 1)[-1] == selector


def _apply_transforms(
    value: object | None,
    transforms: tuple[FieldTransformSpec, ...],
    limits: AdapterResourceLimits,
) -> object | None:
    current = value
    for transform in transforms:
        if transform.kind is ManualAdapterTransform.TRIM:
            current = str(current or "").strip()
        elif transform.kind is ManualAdapterTransform.COLLAPSE_WHITESPACE:
            current = " ".join(str(current or "").split())
        elif transform.kind is ManualAdapterTransform.EMPTY_TO_MISSING:
            current = None if not str(current or "").strip() else current
        elif transform.kind is ManualAdapterTransform.UNICODE_NFKC:
            import unicodedata

            current = unicodedata.normalize("NFKC", str(current or ""))
        elif transform.kind is ManualAdapterTransform.DECIMAL:
            current = Decimal(str(current).replace(" ", "").replace(",", "."))
            if not current.is_finite():
                raise ValueError("non-finite decimal")
        elif transform.kind is ManualAdapterTransform.DATETIME_AWARE:
            current = datetime.fromisoformat(str(current).replace("Z", "+00:00"))
            _aware(current)
        elif transform.kind is ManualAdapterTransform.URL:
            parsed = urlsplit(str(current))
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
                raise ValueError("unsafe URL")
            current = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    if isinstance(current, str) and len(current) > limits.max_string_chars:
        raise ValueError("string limit exceeded")
    return current


def _semantic_fingerprint(spec: ManualAdapterSpec) -> str:
    return hashlib.sha256(_stable_json(spec.semantic_payload()).encode()).hexdigest()


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _depth(value: object, level: int = 1) -> int:
    if isinstance(value, Mapping):
        return max(((_depth(item, level + 1)) for item in value.values()), default=level)
    if isinstance(value, list):
        return max(((_depth(item, level + 1)) for item in value), default=level)
    return level


def _aware(value: object) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")


def _parse_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _aware(parsed)
    return parsed


__all__ = [
    "MANUAL_ADAPTER_SPEC_VERSION",
    "AdapterCompileResult",
    "AdapterCompileStatus",
    "AdapterDiagnostic",
    "AdapterDiagnosticCode",
    "AdapterDiagnosticSeverity",
    "AdapterResourceLimits",
    "CanonicalTenderField",
    "CompiledManualTenderProvider",
    "FieldMappingSpec",
    "FieldTransformSpec",
    "ManualAdapterDataFormat",
    "ManualAdapterCommandResult",
    "ManualAdapterCommandStatus",
    "ManualAdapterDependencies",
    "ManualAdapterLiveOperationError",
    "ManualAdapterPreviewRecord",
    "ManualAdapterPreviewResult",
    "ManualAdapterReadiness",
    "ManualAdapterSpec",
    "ManualAdapterTransform",
    "MappingProvenance",
    "RecordSelectorSpec",
    "SourceRequestSpec",
    "compile_manual_adapter",
    "create_manual_adapter_spec",
    "decode_manual_adapter_spec",
    "preview_manual_adapter",
    "parse_field_mapping_lines",
    "parse_restricted_path",
]
