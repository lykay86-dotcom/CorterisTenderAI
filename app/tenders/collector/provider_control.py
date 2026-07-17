"""Source management and connection diagnostics for the collector UI."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import json
from pathlib import Path
from threading import RLock
import time
from uuid import uuid4

from app.tenders.collector.async_provider_factory import (
    create_default_async_providers,
)
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.network_runtime import (
    create_collector_network_runtime,
)
from app.tenders.collector.provider_settings import (
    ProviderConfiguration,
    ProviderEnablementRepository,
    ProviderSettingOrigin,
    ProviderSettingsRecord,
    ProviderSettingsLoadStatus,
    ProviderSettingsMutationError,
    ProviderSettingsStaleWriteError,
    ProviderSettingsSnapshot,
    create_provider_settings_snapshot,
)
from app.tenders.collector.manual_provider_registration import (
    ManualProviderCommandResult,
    ManualProviderCommandStatus,
    ManualProviderConflictError,
    ManualProviderDraft,
    ManualProviderErrorCategory,
    ManualProviderExecutionError,
    ManualProviderLifecycle,
    ManualProviderRegistration,
    create_manual_provider_registration,
)
from app.tenders.collector.manual_provider_protocol import (
    ManualProviderAuthenticationKind,
    ManualProviderProtocolCommandResult,
    ManualProviderProtocolCommandStatus,
    ManualProviderProtocolDraft,
    ManualProviderProtocolErrorCategory,
    ManualProviderProtocolPolicy,
    ManualProviderProtocolReadiness,
    ManualProviderProtocolSelection,
    create_manual_provider_protocol_selection,
    manual_provider_protocol_policies,
)
from app.tenders.collector.manual_adapter import (
    AdapterCompileResult,
    AdapterCompileStatus,
    ManualAdapterCommandResult,
    ManualAdapterCommandStatus,
    ManualAdapterPreviewResult,
    ManualAdapterReadiness,
    ManualAdapterSpec,
    compile_manual_adapter,
    create_manual_adapter_spec,
    preview_manual_adapter,
)
from app.tenders.collector.manual_provider_health import (
    HealthCheckBinding,
    ManualHealthAdmissionState,
    ManualHealthCheckCommand,
    ManualHealthCheckResult,
    ManualHealthEvidence,
    ManualHealthOutcome,
    ManualHealthReasonCode,
    ManualHealthState,
    ManualProviderHealthService,
    build_health_check_binding,
    evaluate_manual_provider_admission,
    evaluate_manual_probe_payload,
)
from app.tenders.collector.manual_probe_transport import (
    ManualProbeCredentials,
    ManualProbeTransportError,
    ManualProbeTransportReason,
    ManualProviderProbeTransport,
    PinnedFtpsProbePort,
    PinnedHttpsProbePort,
    SystemManualProbeResolver,
)
from app.tenders.collector.provider_definitions import (
    ProviderCatalogEntry,
    ProviderCatalogOrigin,
    resolved_provider_catalog,
)
from app.tenders.provider_base import (
    ProviderDescriptor,
    ProviderHealth,
    ProviderHealthStatus,
)
from app.tenders.provider_credentials import (
    CredentialCommandStatus,
    CredentialCommandResult,
    CredentialState,
    CredentialStateResult,
    ProviderCredentialService,
)
from app.tenders.providers.commercial_catalog import (
    CommercialProviderSettingsRepository,
    default_commercial_provider_definitions,
)
from app.tenders.providers.eis_async import AsyncEisTenderProvider
from app.tenders.providers.mos_supplier_api import (
    AsyncMosSupplierTenderProvider,
    MosSupplierApiConfig,
)
from app.tenders.collector.vertical_source_verification import (
    VerticalSourceVerificationRepository,
)


class ProviderUiState(StrEnum):
    WORKING = "working"
    LIMITED = "limited"
    ERROR = "error"
    DISABLED = "disabled"
    NOT_CONFIGURED = "not_configured"
    UNKNOWN = "unknown"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class ProviderCheckRecord:
    provider_id: str
    status: ProviderHealthStatus
    checked_at: str
    last_success_at: str = ""
    message: str = ""
    last_error: str = ""
    latency_ms: int | None = None

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")


class ProviderCheckLoadStatus(StrEnum):
    MISSING = "missing"
    CURRENT = "current"
    MIGRATED_V1 = "migrated_v1"
    CORRUPT = "corrupt"
    UNSUPPORTED_FUTURE = "unsupported_future"


@dataclass(frozen=True, slots=True)
class ProviderCheckLoadResult:
    records: Mapping[str, ProviderCheckRecord]
    manual_evidence: Mapping[str, ManualHealthEvidence]
    status: ProviderCheckLoadStatus
    source_schema_version: int | None


class ProviderCheckRepository:
    """Persist only public provider diagnostics, never secrets."""

    SCHEMA_VERSION = 2

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = RLock()

    def load(self) -> dict[str, ProviderCheckRecord]:
        with self._lock:
            payload = self._read_payload()
            if payload is None:
                return {}
            raw_records = payload.get("providers", {})
            if not isinstance(raw_records, dict):
                return {}

            result: dict[str, ProviderCheckRecord] = {}
            for provider_id, raw in raw_records.items():
                if not isinstance(raw, dict):
                    continue
                try:
                    status = ProviderHealthStatus(str(raw.get("status", "unknown")))
                except ValueError:
                    status = ProviderHealthStatus.UNKNOWN
                latency = raw.get("latency_ms")
                result[str(provider_id).strip().casefold()] = ProviderCheckRecord(
                    provider_id=str(provider_id).strip().casefold(),
                    status=status,
                    checked_at=str(raw.get("checked_at", "")),
                    last_success_at=str(raw.get("last_success_at", "")),
                    message=str(raw.get("message", "")),
                    last_error=str(raw.get("last_error", "")),
                    latency_ms=(int(latency) if latency is not None else None),
                )
            return result

    def load_result(self) -> ProviderCheckLoadResult:
        with self._lock:
            if not self.path.is_file():
                return ProviderCheckLoadResult({}, {}, ProviderCheckLoadStatus.MISSING, None)
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError):
                return ProviderCheckLoadResult({}, {}, ProviderCheckLoadStatus.CORRUPT, None)
            if not isinstance(payload, dict):
                return ProviderCheckLoadResult({}, {}, ProviderCheckLoadStatus.CORRUPT, None)
            version = payload.get("schema_version", 1)
            if not isinstance(version, int) or isinstance(version, bool):
                return ProviderCheckLoadResult({}, {}, ProviderCheckLoadStatus.CORRUPT, None)
            if version > self.SCHEMA_VERSION:
                return ProviderCheckLoadResult(
                    {}, {}, ProviderCheckLoadStatus.UNSUPPORTED_FUTURE, version
                )
            if version not in {1, self.SCHEMA_VERSION}:
                return ProviderCheckLoadResult({}, {}, ProviderCheckLoadStatus.CORRUPT, version)
            return ProviderCheckLoadResult(
                self.load(),
                self._load_manual_evidence_unlocked(),
                (
                    ProviderCheckLoadStatus.CURRENT
                    if version == self.SCHEMA_VERSION
                    else ProviderCheckLoadStatus.MIGRATED_V1
                ),
                version,
            )

    def save(
        self,
        records: Mapping[str, ProviderCheckRecord],
    ) -> None:
        with self._lock:
            evidence = self._load_manual_evidence_unlocked()
            self._write(records, evidence)

    def update(
        self,
        health: ProviderHealth,
    ) -> ProviderCheckRecord:
        records = self.load()
        provider_id = health.provider_id.strip().casefold()
        previous = records.get(provider_id)
        successful = health.status == ProviderHealthStatus.AVAILABLE
        record = ProviderCheckRecord(
            provider_id=provider_id,
            status=health.status,
            checked_at=health.checked_at,
            last_success_at=(
                health.checked_at
                if successful
                else (previous.last_success_at if previous is not None else "")
            ),
            message=health.message.strip(),
            last_error=("" if successful else health.message.strip()),
            latency_ms=health.latency_ms,
        )
        records[provider_id] = record
        self.save(records)
        return record

    def manual_evidence(self, provider_id: str) -> ManualHealthEvidence | None:
        normalized = str(provider_id).strip().casefold()
        with self._lock:
            return self._load_manual_evidence_unlocked().get(normalized)

    def save_manual_evidence(
        self,
        evidence: ManualHealthEvidence,
        *,
        expected_check_id: str | None = None,
    ) -> bool:
        if not isinstance(evidence, ManualHealthEvidence):
            raise TypeError("evidence must be ManualHealthEvidence")
        with self._lock:
            current = self._load_manual_evidence_unlocked()
            previous = current.get(evidence.binding.provider_id)
            if expected_check_id is not None and (
                previous is None or previous.check_id != expected_check_id
            ):
                return False
            current[evidence.binding.provider_id] = evidence
            self._write(self.load(), current)
            return True

    def invalidate_manual_evidence(self, provider_id: str) -> bool:
        normalized = str(provider_id).strip().casefold()
        with self._lock:
            current = self._load_manual_evidence_unlocked()
            if current.pop(normalized, None) is None:
                return False
            self._write(self.load(), current)
            return True

    def _read_payload(self) -> dict[str, object] | None:
        if not self.path.is_file():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return None
        if not isinstance(payload, dict):
            return None
        version = payload.get("schema_version", 1)
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version > self.SCHEMA_VERSION
        ):
            return None
        return payload

    def _load_manual_evidence_unlocked(self) -> dict[str, ManualHealthEvidence]:
        payload = self._read_payload()
        if payload is None or payload.get("schema_version", 1) != self.SCHEMA_VERSION:
            return {}
        raw_evidence = payload.get("manual_evidence", {})
        if not isinstance(raw_evidence, dict):
            return {}
        result: dict[str, ManualHealthEvidence] = {}
        for provider_id, raw in raw_evidence.items():
            try:
                evidence = _decode_manual_health_evidence(raw)
            except (KeyError, TypeError, ValueError):
                continue
            normalized = str(provider_id).strip().casefold()
            if normalized == evidence.binding.provider_id:
                result[normalized] = evidence
        return result

    def _write(
        self,
        records: Mapping[str, ProviderCheckRecord],
        evidence: Mapping[str, ManualHealthEvidence],
    ) -> None:
        self._backup_v1_if_needed()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "providers": {
                provider_id: {
                    "status": record.status.value,
                    "checked_at": record.checked_at,
                    "last_success_at": record.last_success_at,
                    "message": record.message,
                    "last_error": record.last_error,
                    "latency_ms": record.latency_ms,
                }
                for provider_id, record in sorted(records.items())
            },
            "manual_evidence": {
                provider_id: item.public_payload() for provider_id, item in sorted(evidence.items())
            },
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def _backup_v1_if_needed(self) -> None:
        payload = self._read_payload()
        if payload is None or payload.get("schema_version", 1) != 1:
            return
        if tuple(self.path.parent.glob(f"{self.path.name}.v1-*.bak")):
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = self.path.with_name(f"{self.path.name}.v1-{stamp}.bak")
        with backup.open("xb") as handle:
            handle.write(self.path.read_bytes())


def _decode_manual_health_evidence(value: object) -> ManualHealthEvidence:
    if not isinstance(value, dict):
        raise TypeError("manual health evidence must be an object")
    if set(value) != {
        "check_id",
        "binding",
        "outcome",
        "health",
        "checked_at",
        "valid_until",
    }:
        raise ValueError("manual health evidence fields are invalid")
    raw_binding = value["binding"]
    if not isinstance(raw_binding, dict) or set(raw_binding) != {
        "provider_id",
        "protocol_fingerprint",
        "adapter_spec_version",
        "adapter_revision",
        "adapter_fingerprint",
        "credential_marker",
        "target_policy_version",
        "transport_policy_version",
        "contract_version",
    }:
        raise ValueError("manual health binding fields are invalid")
    binding = HealthCheckBinding(
        provider_id=str(raw_binding["provider_id"]),
        protocol_fingerprint=str(raw_binding["protocol_fingerprint"]),
        adapter_spec_version=int(raw_binding["adapter_spec_version"]),
        adapter_revision=int(raw_binding["adapter_revision"]),
        adapter_fingerprint=str(raw_binding["adapter_fingerprint"]),
        credential_marker=str(raw_binding["credential_marker"]),
        target_policy_version=str(raw_binding["target_policy_version"]),
        transport_policy_version=str(raw_binding["transport_policy_version"]),
        contract_version=int(raw_binding["contract_version"]),
    )
    checked_at = datetime.fromisoformat(str(value["checked_at"]).replace("Z", "+00:00"))
    valid_until = datetime.fromisoformat(str(value["valid_until"]).replace("Z", "+00:00"))
    return ManualHealthEvidence(
        check_id=str(value["check_id"]),
        binding=binding,
        outcome=ManualHealthOutcome(str(value["outcome"])),
        health=ManualHealthState(str(value["health"])),
        checked_at=checked_at,
        valid_until=valid_until,
    )


@dataclass(frozen=True, slots=True)
class ProviderDisplayState:
    provider_id: str
    display_name: str
    enabled: bool
    ui_state: ProviderUiState
    status_text: str
    connection_mode: str
    implementation_status: str
    homepage_url: str
    last_checked_at: str
    last_success_at: str
    last_error: str
    latency_ms: int | None
    configuration_details: tuple[str, ...] = ()
    configuration: ProviderConfiguration = field(default_factory=ProviderConfiguration)
    enabled_origin: ProviderSettingOrigin = ProviderSettingOrigin.DEFAULT
    configuration_origin: ProviderSettingOrigin = ProviderSettingOrigin.DEFAULT
    enabled_editable: bool = True
    configuration_editable: bool = True
    settings_status: ProviderSettingsLoadStatus = ProviderSettingsLoadStatus.MISSING
    credential_state: CredentialState | None = None
    origin: ProviderCatalogOrigin = ProviderCatalogOrigin.BUILTIN
    lifecycle: ManualProviderLifecycle | None = None
    registration_only: bool = False
    runnable: bool = True
    factory_available: bool = True
    protocol_configured: bool = True
    adapter_compiled: bool = True
    credential_available: bool = True
    health_check_available: bool = True
    manual_registration: ManualProviderRegistration | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")


@dataclass(frozen=True, slots=True)
class _ProviderDefinitionView:
    descriptor: ProviderDescriptor
    connection_mode: str
    configuration_details: tuple[str, ...]
    catalog_entry: ProviderCatalogEntry | None = None


HealthChecker = Callable[
    [tuple[str, ...]],
    Awaitable[Mapping[str, ProviderHealth]],
]
ManualProviderIdFactory = Callable[[], str]
ManualProviderClock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class _PreparedManualHealthCheck:
    registration: ManualProviderRegistration
    binding: HealthCheckBinding
    credentials: ManualProbeCredentials = field(repr=False)


class CollectorProviderManager:
    """Manage source switches and perform explicit background health checks."""

    def __init__(
        self,
        data_directory: str | Path,
        *,
        environment: Mapping[str, str] | None = None,
        enablement_repository: ProviderEnablementRepository | None = None,
        check_repository: ProviderCheckRepository | None = None,
        health_checker: HealthChecker | None = None,
        credential_service: ProviderCredentialService | None = None,
        vertical_verification_repository: (VerticalSourceVerificationRepository | None) = None,
        manual_provider_id_factory: ManualProviderIdFactory | None = None,
        manual_provider_clock: ManualProviderClock | None = None,
        manual_health_service: ManualProviderHealthService | None = None,
        manual_probe_transport: ManualProviderProbeTransport | None = None,
    ) -> None:
        self.data_directory = Path(data_directory).expanduser()
        self.data_directory.mkdir(parents=True, exist_ok=True)
        self.environment = environment
        self.settings_repository = enablement_repository or ProviderEnablementRepository(
            self.data_directory / "collector_provider_settings.json",
            legacy_settings_path=(self.data_directory / "commercial_provider_settings.json"),
        )
        # Compatibility alias for existing injection/tests. The canonical owner is
        # settings_repository and no second enablement store is created.
        self.enablement_repository = self.settings_repository
        self.check_repository = check_repository or ProviderCheckRepository(
            self.data_directory / "collector_provider_health.json"
        )
        self.commercial_settings_repository = CommercialProviderSettingsRepository(
            self.data_directory / "commercial_provider_settings.json"
        )
        self._health_checker = health_checker
        self.credential_service = credential_service or ProviderCredentialService(
            environment=self.environment
        )
        self._credential_states: dict[tuple[str, str], CredentialStateResult] = {}
        self._manual_provider_id_factory = manual_provider_id_factory or (
            lambda: f"manual_{uuid4().hex}"
        )
        self._manual_provider_clock = manual_provider_clock or (lambda: datetime.now(timezone.utc))
        self.manual_probe_transport = manual_probe_transport or ManualProviderProbeTransport(
            resolver=SystemManualProbeResolver(),
            http=PinnedHttpsProbePort(),
            ftp=PinnedFtpsProbePort(),
        )
        self.manual_health_service = manual_health_service or ManualProviderHealthService(
            prepare=self._prepare_manual_health_check,
            probe=self._execute_manual_health_check,
            persist=lambda _result: None,
            utc_now=self._safe_manual_timestamp,
        )
        self.vertical_verification_repository = (
            vertical_verification_repository
            or VerticalSourceVerificationRepository(self.data_directory / "tender_registry.sqlite3")
        )

    def states(self) -> tuple[ProviderDisplayState, ...]:
        snapshot = self.settings_snapshot()
        definitions = self._definitions(snapshot)
        records = self.check_repository.load()
        return tuple(
            self._display_state(
                definition,
                records.get(definition.descriptor.id.casefold()),
                snapshot.get(definition.descriptor.id),
                snapshot.status,
                manual_verified=(
                    definition.descriptor.id.casefold() in snapshot.verified_manual_provider_ids
                ),
            )
            for definition in definitions
        )

    def enabled_provider_ids(self) -> tuple[str, ...]:
        return self.settings_snapshot().enabled_provider_ids

    def settings_snapshot(self) -> ProviderSettingsSnapshot:
        snapshot = create_provider_settings_snapshot(
            self.settings_repository,
            environment=self.environment,
        )
        verified: set[str] = set()
        now = self._safe_manual_timestamp()
        for registration in snapshot.manual_registrations:
            try:
                binding = self._manual_health_binding(registration)
            except (RuntimeError, TypeError, ValueError):
                continue
            evidence = self.check_repository.manual_evidence(registration.provider_id)
            admission = evaluate_manual_provider_admission(True, evidence, binding, now)
            if admission.state is ManualHealthAdmissionState.READY:
                verified.add(registration.provider_id)
        persisted = {
            item.provider_id: item for item in self.settings_repository.load_result().records
        }
        providers = tuple(
            replace(
                item,
                enabled=bool(persisted[item.provider_id].enabled),
            )
            if item.provider_id in verified and item.provider_id in persisted
            else item
            for item in snapshot.providers
        )
        return replace(
            snapshot,
            providers=providers,
            verified_manual_provider_ids=frozenset(verified),
        )

    def resolve_provider_ids(self, provider_ids: Iterable[str]) -> tuple[str, ...]:
        return self.settings_snapshot().resolve_provider_ids(tuple(provider_ids))

    def assert_runnable_provider_ids(
        self,
        provider_ids: Iterable[str],
    ) -> tuple[str, ...]:
        return self.settings_snapshot().assert_runnable_provider_ids(tuple(provider_ids))

    def set_enabled(
        self,
        provider_id: str,
        enabled: bool,
    ) -> ProviderDisplayState:
        normalized = self.resolve_provider_ids((provider_id,))[0]
        snapshot = self.settings_snapshot()
        try:
            snapshot.get_manual(normalized)
        except KeyError:
            pass
        else:
            registration = snapshot.get_manual(normalized)
            if registration.lifecycle_state is not ManualProviderLifecycle.CONNECTION_TEST_REQUIRED:
                raise ManualProviderExecutionError(registration.lifecycle_state)
            if enabled and normalized not in snapshot.verified_manual_provider_ids:
                raise ManualProviderExecutionError(ManualProviderLifecycle.CONNECTION_TEST_REQUIRED)
        definitions = {
            item.descriptor.id.casefold(): item
            for item in self._definitions(self.settings_snapshot())
        }
        if normalized not in definitions:
            raise KeyError(provider_id)
        current = snapshot.get(normalized)
        if current.enabled_origin is ProviderSettingOrigin.ENVIRONMENT:
            raise PermissionError("Provider enablement is overridden by environment")

        self.settings_repository.set_enabled(
            normalized,
            enabled,
        )
        states = {item.provider_id: item for item in self.states()}
        return states[normalized]

    def set_configuration(
        self,
        provider_id: str,
        configuration: ProviderConfiguration,
    ) -> ProviderDisplayState:
        normalized = self.resolve_provider_ids((provider_id,))[0]
        commercial_ids = {
            item.provider_id.casefold() for item in default_commercial_provider_definitions()
        }
        if normalized not in commercial_ids:
            raise KeyError(provider_id)
        current = self.settings_snapshot().get(normalized)
        if not current.configuration_editable:
            raise PermissionError("Provider configuration is overridden by environment")
        self.settings_repository.set_configuration(normalized, configuration)
        return next(item for item in self.states() if item.provider_id == normalized)

    def register_manual_provider(
        self,
        draft: ManualProviderDraft,
    ) -> ManualProviderCommandResult:
        provider_id = "unknown"
        try:
            provider_id = str(self._manual_provider_id_factory()).strip().casefold()
            timestamp = self._manual_provider_clock()
            registration = create_manual_provider_registration(
                draft,
                provider_id=provider_id,
                timestamp=timestamp,
            )
            self.settings_repository.register_manual_provider(registration)
        except ManualProviderConflictError as exc:
            return _manual_command_result(
                provider_id,
                ManualProviderCommandStatus.DUPLICATE,
                exc.category,
                "Площадка с такими данными уже зарегистрирована.",
                self._safe_manual_timestamp(),
            )
        except ProviderSettingsMutationError:
            status = self.settings_repository.load_result().status
            return _manual_command_result(
                provider_id,
                (
                    ManualProviderCommandStatus.UNSUPPORTED_SCHEMA
                    if status is ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE
                    else ManualProviderCommandStatus.PERSISTENCE_UNAVAILABLE
                ),
                (
                    ManualProviderErrorCategory.UNSUPPORTED_SCHEMA
                    if status is ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE
                    else ManualProviderErrorCategory.PERSISTENCE_UNAVAILABLE
                ),
                "Регистрация недоступна: проверьте файл настроек.",
                self._safe_manual_timestamp(),
            )
        except (TypeError, ValueError, AttributeError):
            return _manual_command_result(
                "unknown",
                ManualProviderCommandStatus.INVALID_INPUT,
                ManualProviderErrorCategory.INVALID_INPUT,
                "Данные площадки отклонены безопасной валидацией.",
                self._safe_manual_timestamp(),
            )
        except OSError:
            return _manual_command_result(
                provider_id,
                ManualProviderCommandStatus.PERSISTENCE_UNAVAILABLE,
                ManualProviderErrorCategory.PERSISTENCE_UNAVAILABLE,
                "Не удалось сохранить регистрацию площадки.",
                self._safe_manual_timestamp(),
            )
        except Exception:
            return _manual_command_result(
                provider_id,
                ManualProviderCommandStatus.OPERATION_FAILED_SAFE,
                ManualProviderErrorCategory.OPERATION_FAILED,
                "Операция регистрации не выполнена.",
                self._safe_manual_timestamp(),
            )
        return _manual_command_result(
            registration.provider_id,
            ManualProviderCommandStatus.CREATED,
            ManualProviderErrorCategory.NONE,
            "Площадка зарегистрирована; требуется выбор протокола.",
            registration.updated_at,
        )

    def update_manual_provider(
        self,
        provider_id: str,
        draft: ManualProviderDraft,
    ) -> ManualProviderCommandResult:
        normalized = str(provider_id).strip().casefold()
        try:
            current = self._manual_mutation_snapshot().get_manual(normalized)
            validated = ManualProviderDraft(
                display_name=draft.display_name,
                homepage_url=draft.homepage_url,
                endpoint_url=draft.endpoint_url,
            )
            updated = ManualProviderRegistration(
                provider_id=current.provider_id,
                display_name=validated.display_name,
                homepage_url=validated.homepage_url,
                endpoint_url=validated.endpoint_url,
                lifecycle_state=current.lifecycle_state,
                protocol_selection=current.protocol_selection,
                adapter_spec=current.adapter_spec,
                adapter_spec_history=current.adapter_spec_history,
                created_at=current.created_at,
                updated_at=self._next_manual_timestamp(current.updated_at),
            )
            self.settings_repository.replace_manual_provider_if_current(
                updated,
                expected_updated_at=current.updated_at,
            )
            self.check_repository.invalidate_manual_evidence(updated.provider_id)
        except ManualProviderConflictError as exc:
            return _manual_command_result(
                normalized,
                ManualProviderCommandStatus.DUPLICATE,
                exc.category,
                "Площадка с такими данными уже зарегистрирована.",
                self._safe_manual_timestamp(),
            )
        except KeyError:
            return _manual_command_result(
                "unknown",
                ManualProviderCommandStatus.CONFLICT,
                ManualProviderErrorCategory.IDENTITY_COLLISION,
                "Регистрация площадки не найдена.",
                self._safe_manual_timestamp(),
            )
        except ProviderSettingsStaleWriteError:
            return _manual_command_result(
                normalized or "unknown",
                ManualProviderCommandStatus.CONFLICT,
                ManualProviderErrorCategory.IDENTITY_COLLISION,
                "Регистрация была изменена; обновите список и повторите.",
                self._safe_manual_timestamp(),
            )
        except (TypeError, ValueError, AttributeError):
            return _manual_command_result(
                normalized or "unknown",
                ManualProviderCommandStatus.INVALID_INPUT,
                ManualProviderErrorCategory.INVALID_INPUT,
                "Данные площадки отклонены безопасной валидацией.",
                self._safe_manual_timestamp(),
            )
        except ProviderSettingsMutationError:
            return _manual_command_result(
                normalized or "unknown",
                ManualProviderCommandStatus.PERSISTENCE_UNAVAILABLE,
                ManualProviderErrorCategory.PERSISTENCE_UNAVAILABLE,
                "Изменение регистрации недоступно.",
                self._safe_manual_timestamp(),
            )
        except OSError:
            return _manual_command_result(
                normalized or "unknown",
                ManualProviderCommandStatus.PERSISTENCE_UNAVAILABLE,
                ManualProviderErrorCategory.PERSISTENCE_UNAVAILABLE,
                "Не удалось сохранить изменения площадки.",
                self._safe_manual_timestamp(),
            )
        except Exception:
            return _manual_command_result(
                normalized or "unknown",
                ManualProviderCommandStatus.OPERATION_FAILED_SAFE,
                ManualProviderErrorCategory.OPERATION_FAILED,
                "Операция изменения не выполнена.",
                self._safe_manual_timestamp(),
            )
        return _manual_command_result(
            updated.provider_id,
            ManualProviderCommandStatus.UPDATED,
            ManualProviderErrorCategory.NONE,
            (
                "Данные площадки обновлены; требуется создание адаптера."
                if updated.protocol_selection is not None
                else "Данные площадки обновлены; требуется выбор протокола."
            ),
            updated.updated_at,
            updated.lifecycle_state,
        )

    def manual_protocol_policies(self) -> tuple[ManualProviderProtocolPolicy, ...]:
        return manual_provider_protocol_policies()

    def manual_adapter_spec(self, provider_id: str) -> ManualAdapterSpec | None:
        return self.settings_snapshot().get_manual(provider_id).adapter_spec

    def manual_health_binding(self, provider_id: str) -> HealthCheckBinding:
        """Build the current non-secret admission binding without network I/O."""

        registration = create_provider_settings_snapshot(
            self.settings_repository,
            environment=self.environment,
        ).get_manual(provider_id)
        return self._manual_health_binding(registration)

    def compile_manual_provider_adapter(
        self,
        provider_id: str,
        spec: ManualAdapterSpec | None = None,
    ) -> AdapterCompileResult:
        registration = self.settings_snapshot().get_manual(provider_id)
        selected = spec or registration.adapter_spec
        if selected is None:
            raise ValueError("manual adapter specification is required")
        return compile_manual_adapter(registration, selected)

    def preview_manual_provider_adapter(
        self,
        provider_id: str,
        spec: ManualAdapterSpec,
        sample: str | bytes,
    ) -> ManualAdapterPreviewResult:
        registration = self.settings_snapshot().get_manual(provider_id)
        compiled = compile_manual_adapter(registration, spec)
        if compiled.status is not AdapterCompileStatus.VALID:
            return ManualAdapterPreviewResult((), compiled.diagnostics)
        return preview_manual_adapter(spec, sample)

    def save_manual_adapter_spec(
        self,
        provider_id: str,
        spec: ManualAdapterSpec,
        *,
        expected_updated_at: datetime,
    ) -> ManualAdapterCommandResult:
        normalized = str(provider_id).strip().casefold()
        try:
            current = self._manual_mutation_snapshot().get_manual(normalized)
            if current.updated_at != expected_updated_at:
                raise ProviderSettingsStaleWriteError(normalized)
            if (
                current.adapter_spec is not None
                and current.adapter_spec.fingerprint == spec.fingerprint
            ):
                return _manual_adapter_command_result(
                    normalized,
                    ManualAdapterCommandStatus.UNCHANGED,
                    (),
                    current.adapter_spec,
                    "Спецификация адаптера не изменилась.",
                    current.updated_at,
                )
            expected_revision = current.next_adapter_revision
            if spec.revision != expected_revision:
                raise ValueError("manual adapter revision is not monotonic")
            compiled = compile_manual_adapter(current, spec)
            if compiled.status is not AdapterCompileStatus.VALID:
                return _manual_adapter_command_result(
                    normalized,
                    ManualAdapterCommandStatus.INVALID,
                    compiled.diagnostics,
                    spec,
                    "Спецификация адаптера отклонена безопасной проверкой.",
                    self._safe_manual_timestamp(),
                )
            timestamp = self._next_manual_timestamp(current.updated_at)
            history = (
                ((current.adapter_spec,) if current.adapter_spec is not None else ())
                + current.adapter_spec_history
            )[:5]
            updated = ManualProviderRegistration(
                provider_id=current.provider_id,
                display_name=current.display_name,
                homepage_url=current.homepage_url,
                endpoint_url=current.endpoint_url,
                lifecycle_state=ManualProviderLifecycle.CONNECTION_TEST_REQUIRED,
                protocol_selection=current.protocol_selection,
                adapter_spec=spec,
                adapter_spec_history=history,
                created_at=current.created_at,
                updated_at=timestamp,
            )
            self.settings_repository.replace_manual_provider_if_current(
                updated,
                expected_updated_at=expected_updated_at,
            )
            self.check_repository.invalidate_manual_evidence(updated.provider_id)
        except ProviderSettingsStaleWriteError:
            return _manual_adapter_command_result(
                normalized,
                ManualAdapterCommandStatus.STALE,
                (),
                None,
                "Спецификация была изменена; обновите список и повторите.",
                self._safe_manual_timestamp(),
            )
        except KeyError:
            return _manual_adapter_command_result(
                normalized,
                (
                    ManualAdapterCommandStatus.UNSUPPORTED_TARGET
                    if not normalized.startswith("manual_")
                    else ManualAdapterCommandStatus.NOT_FOUND
                ),
                (),
                None,
                "Ручная регистрация не найдена.",
                self._safe_manual_timestamp(),
            )
        except (TypeError, ValueError, AttributeError):
            return _manual_adapter_command_result(
                normalized,
                ManualAdapterCommandStatus.INVALID,
                (),
                None,
                "Спецификация адаптера отклонена безопасной проверкой.",
                self._safe_manual_timestamp(),
            )
        except (ProviderSettingsMutationError, OSError):
            return _manual_adapter_command_result(
                normalized,
                ManualAdapterCommandStatus.PERSISTENCE_UNAVAILABLE,
                (),
                None,
                "Не удалось сохранить спецификацию адаптера.",
                self._safe_manual_timestamp(),
            )
        except Exception:
            return _manual_adapter_command_result(
                normalized,
                ManualAdapterCommandStatus.OPERATION_FAILED_SAFE,
                (),
                None,
                "Операция настройки адаптера не выполнена.",
                self._safe_manual_timestamp(),
            )
        return _manual_adapter_command_result(
            normalized,
            ManualAdapterCommandStatus.SAVED,
            (),
            spec,
            "Адаптер настроен. Требуется проверка подключения.",
            updated.updated_at,
        )

    def clear_manual_adapter_spec(
        self,
        provider_id: str,
        *,
        expected_updated_at: datetime,
    ) -> ManualAdapterCommandResult:
        normalized = str(provider_id).strip().casefold()
        try:
            current = self._manual_mutation_snapshot().get_manual(normalized)
            if current.protocol_selection is None:
                raise ValueError("manual protocol is required")
            timestamp = self._next_manual_timestamp(current.updated_at)
            history = (
                ((current.adapter_spec,) if current.adapter_spec is not None else ())
                + current.adapter_spec_history
            )[:5]
            updated = ManualProviderRegistration(
                provider_id=current.provider_id,
                display_name=current.display_name,
                homepage_url=current.homepage_url,
                endpoint_url=current.endpoint_url,
                lifecycle_state=ManualProviderLifecycle.ADAPTER_REQUIRED,
                protocol_selection=current.protocol_selection,
                adapter_spec=None,
                adapter_spec_history=history,
                created_at=current.created_at,
                updated_at=timestamp,
            )
            self.settings_repository.replace_manual_provider_if_current(
                updated,
                expected_updated_at=expected_updated_at,
            )
            self.check_repository.invalidate_manual_evidence(updated.provider_id)
        except ProviderSettingsStaleWriteError:
            return _manual_adapter_command_result(
                normalized,
                ManualAdapterCommandStatus.STALE,
                (),
                None,
                "Спецификация была изменена; обновите список и повторите.",
                self._safe_manual_timestamp(),
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            return _manual_adapter_command_result(
                normalized,
                ManualAdapterCommandStatus.INVALID,
                (),
                None,
                "Сброс адаптера отклонён безопасной проверкой.",
                self._safe_manual_timestamp(),
            )
        except (ProviderSettingsMutationError, OSError):
            return _manual_adapter_command_result(
                normalized,
                ManualAdapterCommandStatus.PERSISTENCE_UNAVAILABLE,
                (),
                None,
                "Не удалось сбросить спецификацию адаптера.",
                self._safe_manual_timestamp(),
            )
        return _manual_adapter_command_result(
            normalized,
            ManualAdapterCommandStatus.CLEARED,
            (),
            None,
            "Спецификация адаптера сброшена.",
            updated.updated_at,
        )

    def rollback_manual_adapter_spec(
        self,
        provider_id: str,
        *,
        expected_updated_at: datetime,
        history_revision: int | None = None,
    ) -> ManualAdapterCommandResult:
        normalized = str(provider_id).strip().casefold()
        try:
            current = self._manual_mutation_snapshot().get_manual(normalized)
            candidates = current.adapter_spec_history
            selected = next(
                (
                    item
                    for item in candidates
                    if history_revision is None or item.revision == history_revision
                ),
                None,
            )
            if selected is None:
                raise ValueError("manual adapter rollback revision is unavailable")
            timestamp = self._next_manual_timestamp(current.updated_at)
            revision = current.next_adapter_revision
            replacement = create_manual_adapter_spec(
                provider_id=selected.provider_id,
                protocol_family=selected.protocol_family,
                source=selected.source,
                record_selector=selected.record_selector,
                field_mappings=selected.field_mappings,
                limits=selected.limits,
                revision=revision,
                timestamp=timestamp,
                created_at=selected.created_at,
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            return _manual_adapter_command_result(
                normalized,
                ManualAdapterCommandStatus.INVALID,
                (),
                None,
                "Revision для rollback недоступна.",
                self._safe_manual_timestamp(),
            )
        result = self.save_manual_adapter_spec(
            normalized,
            replacement,
            expected_updated_at=expected_updated_at,
        )
        if result.status is not ManualAdapterCommandStatus.SAVED:
            return result
        return ManualAdapterCommandResult(
            provider_id=result.provider_id,
            status=ManualAdapterCommandStatus.ROLLED_BACK,
            readiness=result.readiness,
            diagnostics=result.diagnostics,
            fingerprint=result.fingerprint,
            revision=result.revision,
            message="Предыдущая спецификация восстановлена как новая revision. Требуется проверка подключения.",
            observed_at=result.observed_at,
        )

    def manual_protocol_selection(
        self,
        provider_id: str,
    ) -> ManualProviderProtocolSelection | None:
        return self.settings_snapshot().get_manual(provider_id).protocol_selection

    def manual_protocol_readiness_gaps(self, provider_id: str) -> tuple[str, ...]:
        registration = self.settings_snapshot().get_manual(provider_id)
        if registration.protocol_selection is None:
            return ("protocol_required", "adapter_required")
        if registration.adapter_spec is not None:
            return ("connection_test_required",)
        return registration.protocol_selection.readiness_gaps()

    def save_manual_provider_protocol(
        self,
        provider_id: str,
        draft: ManualProviderProtocolDraft,
        *,
        expected_updated_at: datetime,
    ) -> ManualProviderProtocolCommandResult:
        normalized = str(provider_id).strip().casefold()
        try:
            current = self._manual_mutation_snapshot().get_manual(normalized)
            validated = ManualProviderProtocolDraft(
                family=draft.family,
                endpoint_url=draft.endpoint_url,
                payload_format=draft.payload_format,
                authentication_kind=draft.authentication_kind,
                ftps_mode=draft.ftps_mode,
            )
            timestamp = self._next_manual_timestamp(current.updated_at)
            selection = create_manual_provider_protocol_selection(
                validated,
                timestamp=timestamp,
                selected_at=(
                    current.protocol_selection.selected_at
                    if current.protocol_selection is not None
                    else timestamp
                ),
            )
            updated = ManualProviderRegistration(
                provider_id=current.provider_id,
                display_name=current.display_name,
                homepage_url=current.homepage_url,
                endpoint_url=current.endpoint_url,
                lifecycle_state=ManualProviderLifecycle.ADAPTER_REQUIRED,
                protocol_selection=selection,
                created_at=current.created_at,
                updated_at=timestamp,
            )
            self.settings_repository.replace_manual_provider_if_current(
                updated,
                expected_updated_at=expected_updated_at,
            )
            self.check_repository.invalidate_manual_evidence(updated.provider_id)
            status = (
                ManualProviderProtocolCommandStatus.CHANGED
                if current.protocol_selection is not None
                else ManualProviderProtocolCommandStatus.SAVED
            )
        except ProviderSettingsStaleWriteError:
            return _manual_protocol_command_result(
                normalized,
                ManualProviderProtocolCommandStatus.STALE,
                ManualProviderLifecycle.PROTOCOL_REQUIRED,
                ManualProviderProtocolErrorCategory.STALE_EDIT,
                "Настройка была изменена; обновите список и повторите.",
                self._safe_manual_timestamp(),
            )
        except KeyError:
            unsupported_target = not normalized.startswith("manual_")
            return _manual_protocol_command_result(
                normalized or "unknown",
                (
                    ManualProviderProtocolCommandStatus.UNSUPPORTED_TARGET
                    if unsupported_target
                    else ManualProviderProtocolCommandStatus.NOT_FOUND
                ),
                ManualProviderLifecycle.PROTOCOL_REQUIRED,
                (
                    ManualProviderProtocolErrorCategory.UNSUPPORTED_TARGET
                    if unsupported_target
                    else ManualProviderProtocolErrorCategory.NOT_FOUND
                ),
                (
                    "Настройка протокола доступна только для ручной регистрации."
                    if unsupported_target
                    else "Ручная регистрация не найдена."
                ),
                self._safe_manual_timestamp(),
            )
        except (TypeError, ValueError, AttributeError):
            return _manual_protocol_command_result(
                normalized or "unknown",
                ManualProviderProtocolCommandStatus.INVALID_INPUT,
                ManualProviderLifecycle.PROTOCOL_REQUIRED,
                ManualProviderProtocolErrorCategory.INVALID_INPUT,
                "Настройка протокола отклонена безопасной валидацией.",
                self._safe_manual_timestamp(),
            )
        except (ProviderSettingsMutationError, OSError):
            return _manual_protocol_command_result(
                normalized or "unknown",
                ManualProviderProtocolCommandStatus.PERSISTENCE_UNAVAILABLE,
                ManualProviderLifecycle.PROTOCOL_REQUIRED,
                ManualProviderProtocolErrorCategory.PERSISTENCE_UNAVAILABLE,
                "Не удалось сохранить настройку протокола.",
                self._safe_manual_timestamp(),
            )
        except Exception:
            return _manual_protocol_command_result(
                normalized or "unknown",
                ManualProviderProtocolCommandStatus.OPERATION_FAILED_SAFE,
                ManualProviderLifecycle.PROTOCOL_REQUIRED,
                ManualProviderProtocolErrorCategory.OPERATION_FAILED,
                "Операция настройки протокола не выполнена.",
                self._safe_manual_timestamp(),
            )
        return _manual_protocol_command_result(
            normalized,
            status,
            ManualProviderLifecycle.ADAPTER_REQUIRED,
            ManualProviderProtocolErrorCategory.NONE,
            "Протокол сохранён; требуется создание адаптера.",
            updated.updated_at,
        )

    def clear_manual_provider_protocol(
        self,
        provider_id: str,
        *,
        expected_updated_at: datetime,
    ) -> ManualProviderProtocolCommandResult:
        normalized = str(provider_id).strip().casefold()
        try:
            current = self._manual_mutation_snapshot().get_manual(normalized)
            timestamp = self._next_manual_timestamp(current.updated_at)
            updated = ManualProviderRegistration(
                provider_id=current.provider_id,
                display_name=current.display_name,
                homepage_url=current.homepage_url,
                endpoint_url=current.endpoint_url,
                lifecycle_state=ManualProviderLifecycle.PROTOCOL_REQUIRED,
                protocol_selection=None,
                created_at=current.created_at,
                updated_at=timestamp,
            )
            self.settings_repository.replace_manual_provider_if_current(
                updated,
                expected_updated_at=expected_updated_at,
            )
            self.check_repository.invalidate_manual_evidence(updated.provider_id)
        except ProviderSettingsStaleWriteError:
            return _manual_protocol_command_result(
                normalized,
                ManualProviderProtocolCommandStatus.STALE,
                ManualProviderLifecycle.PROTOCOL_REQUIRED,
                ManualProviderProtocolErrorCategory.STALE_EDIT,
                "Настройка была изменена; обновите список и повторите.",
                self._safe_manual_timestamp(),
            )
        except KeyError:
            unsupported_target = not normalized.startswith("manual_")
            return _manual_protocol_command_result(
                normalized or "unknown",
                (
                    ManualProviderProtocolCommandStatus.UNSUPPORTED_TARGET
                    if unsupported_target
                    else ManualProviderProtocolCommandStatus.NOT_FOUND
                ),
                ManualProviderLifecycle.PROTOCOL_REQUIRED,
                (
                    ManualProviderProtocolErrorCategory.UNSUPPORTED_TARGET
                    if unsupported_target
                    else ManualProviderProtocolErrorCategory.NOT_FOUND
                ),
                (
                    "Настройка протокола доступна только для ручной регистрации."
                    if unsupported_target
                    else "Ручная регистрация не найдена."
                ),
                self._safe_manual_timestamp(),
            )
        except (TypeError, ValueError, AttributeError):
            return _manual_protocol_command_result(
                normalized or "unknown",
                ManualProviderProtocolCommandStatus.INVALID_INPUT,
                ManualProviderLifecycle.PROTOCOL_REQUIRED,
                ManualProviderProtocolErrorCategory.INVALID_INPUT,
                "Сброс протокола отклонён безопасной валидацией.",
                self._safe_manual_timestamp(),
            )
        except (ProviderSettingsMutationError, OSError):
            return _manual_protocol_command_result(
                normalized or "unknown",
                ManualProviderProtocolCommandStatus.PERSISTENCE_UNAVAILABLE,
                ManualProviderLifecycle.PROTOCOL_REQUIRED,
                ManualProviderProtocolErrorCategory.PERSISTENCE_UNAVAILABLE,
                "Не удалось сбросить настройку протокола.",
                self._safe_manual_timestamp(),
            )
        except Exception:
            return _manual_protocol_command_result(
                normalized or "unknown",
                ManualProviderProtocolCommandStatus.OPERATION_FAILED_SAFE,
                ManualProviderLifecycle.PROTOCOL_REQUIRED,
                ManualProviderProtocolErrorCategory.OPERATION_FAILED,
                "Операция сброса протокола не выполнена.",
                self._safe_manual_timestamp(),
            )
        return _manual_protocol_command_result(
            normalized,
            ManualProviderProtocolCommandStatus.CLEARED,
            ManualProviderLifecycle.PROTOCOL_REQUIRED,
            ManualProviderProtocolErrorCategory.NONE,
            "Выбор протокола сброшен.",
            updated.updated_at,
        )

    def _next_manual_timestamp(self, current: datetime) -> datetime:
        value = self._manual_provider_clock()
        if value.utcoffset() is None:
            raise ValueError("manual provider clock must be timezone-aware")
        return value if value > current else current + timedelta(microseconds=1)

    def _manual_mutation_snapshot(self) -> ProviderSettingsSnapshot:
        snapshot = self.settings_snapshot()
        if snapshot.status in {
            ProviderSettingsLoadStatus.CORRUPT,
            ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE,
        }:
            raise ProviderSettingsMutationError(
                f"Provider settings mutation blocked: {snapshot.status.value}"
            )
        return snapshot

    def _safe_manual_timestamp(self) -> datetime:
        value = self._manual_provider_clock()
        return value if value.utcoffset() is not None else datetime.now(timezone.utc)

    def _manual_health_binding(
        self,
        registration: ManualProviderRegistration,
    ) -> HealthCheckBinding:
        selection = registration.protocol_selection
        spec = registration.adapter_spec
        if selection is None or spec is None:
            raise ValueError("manual provider is not configured")
        compiled = compile_manual_adapter(registration, spec)
        if compiled.status is not AdapterCompileStatus.VALID or compiled.adapter is None:
            raise ValueError("manual provider adapter is invalid")
        secret_names = {
            ManualProviderAuthenticationKind.NONE: (),
            ManualProviderAuthenticationKind.API_KEY: ("api_key",),
            ManualProviderAuthenticationKind.USERNAME_PASSWORD: ("username", "password"),
        }[selection.authentication_kind]
        marker = self.credential_service.credential_marker(
            registration.provider_id,
            secret_names,
        )
        return build_health_check_binding(
            provider_id=registration.provider_id,
            protocol_payload=selection.persisted_payload(),
            adapter_spec_version=spec.spec_version,
            adapter_revision=spec.revision,
            adapter_fingerprint=spec.fingerprint,
            credential_marker=marker,
        )

    def _prepare_manual_health_check(self, provider_id: str) -> _PreparedManualHealthCheck:
        snapshot = create_provider_settings_snapshot(
            self.settings_repository,
            environment=self.environment,
        )
        registration = snapshot.get_manual(provider_id)
        binding = self._manual_health_binding(registration)
        selection = registration.protocol_selection
        if selection is None:
            raise ValueError("manual provider protocol is required")
        credentials = ManualProbeCredentials()
        if selection.authentication_kind is ManualProviderAuthenticationKind.API_KEY:
            secret = self.credential_service.resolve_runtime_secret(provider_id, "api_key")
            credentials = ManualProbeCredentials(api_key=secret.value)
        elif selection.authentication_kind is ManualProviderAuthenticationKind.USERNAME_PASSWORD:
            username = self.credential_service.resolve_runtime_secret(provider_id, "username")
            password = self.credential_service.resolve_runtime_secret(provider_id, "password")
            credentials = ManualProbeCredentials(
                username=username.value,
                password=password.value,
            )
        return _PreparedManualHealthCheck(registration, binding, credentials)

    async def _execute_manual_health_check(
        self,
        prepared: _PreparedManualHealthCheck,
        cancellation_token: CollectorCancellationToken,
    ) -> ManualHealthCheckResult:
        started_at = self._safe_manual_timestamp()
        started_monotonic = time.monotonic()
        registration = prepared.registration
        selection = registration.protocol_selection
        spec = registration.adapter_spec
        if selection is None or spec is None:
            raise ValueError("manual provider is not configured")
        try:
            if selection.family.value in {"api", "rss"}:
                if selection.payload_format is None:
                    raise ValueError("manual provider payload format is required")
                payload = await self.manual_probe_transport.probe_http(
                    selection.endpoint_url,
                    selection.family,
                    selection.payload_format,
                    cancellation_token,
                    prepared.credentials,
                )
            else:
                payload = await self.manual_probe_transport.probe_ftp(
                    selection.endpoint_url,
                    selection.family,
                    spec.source.filename_suffix,
                    cancellation_token,
                    ftps_mode=selection.ftps_mode,
                    credentials=prepared.credentials,
                )
            compatibility = evaluate_manual_probe_payload(spec, payload)
            if selection.family.value == "ftp":
                outcome = ManualHealthOutcome.DEGRADED
                health = ManualHealthState.DEGRADED
                reason = ManualHealthReasonCode.PLAINTEXT_TRANSPORT
            elif compatibility.health is ManualHealthState.HEALTHY:
                outcome = ManualHealthOutcome.PASSED
            elif compatibility.health is ManualHealthState.DEGRADED:
                outcome = ManualHealthOutcome.DEGRADED
            else:
                outcome = ManualHealthOutcome.FAILED
            health = compatibility.health
            reason = compatibility.reason_code
        except ManualProbeTransportError as exc:
            if exc.reason is ManualProbeTransportReason.TARGET_BLOCKED:
                outcome = ManualHealthOutcome.BLOCKED
                health = ManualHealthState.UNKNOWN
                reason = ManualHealthReasonCode.TARGET_BLOCKED
            elif exc.reason is ManualProbeTransportReason.DNS_BLOCKED:
                outcome = ManualHealthOutcome.BLOCKED
                health = ManualHealthState.UNKNOWN
                reason = ManualHealthReasonCode.DNS_BLOCKED
            else:
                outcome = ManualHealthOutcome.FAILED
                health = ManualHealthState.UNHEALTHY
                reason = ManualHealthReasonCode.PROTOCOL_ERROR
        finished_at = self._safe_manual_timestamp()
        if finished_at < started_at:
            finished_at = started_at
        return ManualHealthCheckResult(
            check_id=uuid4().hex,
            binding=prepared.binding,
            outcome=outcome,
            health=health,
            reason_code=reason,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=max(0, int((time.monotonic() - started_monotonic) * 1000)),
            stages=(),
        )

    def credential_state(
        self,
        provider_id: str,
        secret_name: str = "api_key",
    ) -> CredentialStateResult:
        result = self.credential_service.has_secret(provider_id, secret_name)
        self._credential_states[(result.provider_id, result.secret_name)] = result
        return result

    def save_credential(
        self,
        provider_id: str,
        secret_name: str,
        value: str,
        *,
        replace: bool = False,
    ) -> CredentialCommandResult:
        result = self.credential_service.save_secret(
            provider_id,
            secret_name,
            value,
            replace=replace,
        )
        self._remember_credential_command(result)
        if result.provider_id != "unknown" and result.status in {
            CredentialCommandStatus.SAVED,
            CredentialCommandStatus.REPLACED,
        }:
            self.check_repository.invalidate_manual_evidence(result.provider_id)
        return result

    def delete_credential(
        self,
        provider_id: str,
        secret_name: str = "api_key",
    ) -> CredentialCommandResult:
        result = self.credential_service.delete_secret(provider_id, secret_name)
        self._remember_credential_command(result)
        if result.provider_id != "unknown" and result.status is CredentialCommandStatus.DELETED:
            self.check_repository.invalidate_manual_evidence(result.provider_id)
        return result

    def _remember_credential_command(self, result: CredentialCommandResult) -> None:
        if result.provider_id == "unknown":
            return
        self._credential_states[(result.provider_id, result.secret_name)] = CredentialStateResult(
            provider_id=result.provider_id,
            secret_name=result.secret_name,
            state=result.state,
            message=result.message,
            observed_at=result.observed_at,
            protected_store_configured=(result.state is CredentialState.CONFIGURED),
            environment_override=(result.state is CredentialState.ENVIRONMENT_OVERRIDE),
        )

    async def check_provider(
        self,
        provider_id: str,
    ) -> ProviderDisplayState:
        results = await self.check_providers((provider_id,))
        normalized = provider_id.strip().casefold()
        for item in results:
            if item.provider_id == normalized:
                return item
        raise KeyError(provider_id)

    async def test_manual_provider_connection(
        self,
        provider_id: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> ManualHealthCheckResult:
        normalized = self.resolve_provider_ids((provider_id,))[0]
        registration = self.settings_snapshot().get_manual(normalized)
        if registration.adapter_spec is None or registration.protocol_selection is None:
            raise ManualProviderExecutionError(registration.lifecycle_state)
        if self.manual_health_service is None:
            raise ManualProviderExecutionError(ManualProviderLifecycle.CONNECTION_TEST_REQUIRED)
        result = await self.manual_health_service.test_connection(
            ManualHealthCheckCommand(
                normalized,
                cancellation_token=(cancellation_token or CollectorCancellationToken()),
            )
        )
        if result.creates_evidence:
            current = self.settings_snapshot().get_manual(normalized)
            binding = self._manual_health_binding(current)
            if result.binding == binding:
                self.check_repository.save_manual_evidence(ManualHealthEvidence.from_result(result))
        return result

    async def check_providers(
        self,
        provider_ids: Iterable[str],
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> tuple[ProviderDisplayState, ...]:
        normalized_ids = tuple(
            dict.fromkeys(item.strip().casefold() for item in provider_ids if item.strip())
        )
        known = {state.provider_id: state for state in self.states()}
        unknown = [provider_id for provider_id in normalized_ids if provider_id not in known]
        if unknown:
            raise KeyError(", ".join(unknown))
        manual_ids = tuple(
            provider_id for provider_id in normalized_ids if known[provider_id].registration_only
        )
        for provider_id in manual_ids:
            await self.test_manual_provider_connection(
                provider_id,
                cancellation_token=cancellation_token,
            )

        selected = tuple(
            provider_id
            for provider_id in normalized_ids
            if provider_id not in manual_ids and known[provider_id].enabled
        )
        if not selected:
            return self.states()

        if self._health_checker is not None:
            health_results = await self._health_checker(selected)
        else:
            health_results = await self._check_real(selected)

        checked_at = _utc_now()
        for provider_id in selected:
            health = health_results.get(provider_id)
            if health is None:
                health = ProviderHealth(
                    provider_id=provider_id,
                    status=ProviderHealthStatus.UNAVAILABLE,
                    checked_at=checked_at,
                    message=("Проверка не вернула состояние источника."),
                    latency_ms=None,
                )
            self.check_repository.update(health)
        return self.states()

    async def _check_real(
        self,
        provider_ids: tuple[str, ...],
    ) -> Mapping[str, ProviderHealth]:
        runtime = create_collector_network_runtime()
        try:
            snapshot = self.settings_snapshot()
            providers = create_default_async_providers(
                runtime,
                mos_supplier_config=(MosSupplierApiConfig.from_environment(self.environment)),
                include_commercial_catalog=True,
                provider_settings_snapshot=snapshot,
                environment=self.environment,
                include_disabled=True,
            )
            by_id = {provider.descriptor.id.casefold(): provider for provider in providers}
            results: dict[str, ProviderHealth] = {}
            for provider_id in provider_ids:
                provider = by_id.get(provider_id)
                if provider is None:
                    results[provider_id] = ProviderHealth(
                        provider_id=provider_id,
                        status=ProviderHealthStatus.UNAVAILABLE,
                        checked_at=_utc_now(),
                        message="Провайдер не зарегистрирован.",
                    )
                    continue
                try:
                    results[provider_id] = await provider.check_health()
                except Exception as exc:
                    results[provider_id] = ProviderHealth(
                        provider_id=provider_id,
                        status=ProviderHealthStatus.UNAVAILABLE,
                        checked_at=_utc_now(),
                        message=(f"{type(exc).__name__}: {exc}"),
                    )
            return results
        finally:
            await runtime.aclose()

    def _definitions(
        self,
        snapshot: ProviderSettingsSnapshot,
    ) -> tuple[_ProviderDefinitionView, ...]:
        catalog = {
            item.descriptor.id.casefold(): item
            for item in resolved_provider_catalog(snapshot.manual_registrations)
        }
        mos_credential_state = self._credential_states.get(("mos_supplier", "api_key"))
        result = [
            _ProviderDefinitionView(
                descriptor=AsyncEisTenderProvider.descriptor,
                connection_mode="public_html_async",
                configuration_details=(
                    "Публичный HTML-интерфейс ЕИС.",
                    "Резервный режим, не официальный API.",
                    "CAPTCHA и ограничения сайта не обходятся.",
                ),
                catalog_entry=catalog["eis"],
            ),
            _ProviderDefinitionView(
                descriptor=(AsyncMosSupplierTenderProvider.descriptor),
                connection_mode="official_api_bearer",
                configuration_details=(
                    (
                        mos_credential_state.message
                        if mos_credential_state is not None
                        else "Состояние credential не запрашивалось."
                    ),
                    "Официальный API Портала поставщиков.",
                ),
                catalog_entry=catalog["mos_supplier"],
            ),
        ]

        for definition in default_commercial_provider_definitions():
            settings = snapshot.get(definition.provider_id)
            configuration = settings.configuration
            result.append(
                _ProviderDefinitionView(
                    descriptor=definition.descriptor,
                    connection_mode=("commercial_access_pending"),
                    configuration_details=(
                        _commercial_configuration_message(configuration),
                        "Credentials управляются защищённым контуром отдельно.",
                        (
                            f"Endpoint: {configuration.api_base_url}"
                            if configuration.api_base_url
                            else "Проверенный API endpoint не задан."
                        ),
                    ),
                    catalog_entry=catalog[definition.provider_id.casefold()],
                )
            )
        for registration in snapshot.manual_registrations:
            entry = catalog[registration.provider_id]
            selected = registration.protocol_selection
            result.append(
                _ProviderDefinitionView(
                    descriptor=entry.descriptor,
                    connection_mode=(
                        "manual_adapter_unverified"
                        if registration.adapter_spec is not None
                        else (
                            "manual_protocol_selected"
                            if selected is not None
                            else "manual_protocol_required"
                        )
                    ),
                    configuration_details=(
                        (
                            f"Выбрано семейство: {selected.family.value.upper()}."
                            if selected is not None
                            else "Регистрация сохранена без протокола и адаптера."
                        ),
                        (
                            "Адаптер настроен. Требуется проверка подключения."
                            if registration.adapter_spec is not None
                            else (
                                "Протокол выбран; для запуска требуется отдельный адаптер."
                                if selected is not None
                                else "Для продолжения требуется отдельный этап выбора протокола."
                            )
                        ),
                    ),
                    catalog_entry=entry,
                )
            )
        return tuple(
            sorted(
                result,
                key=lambda item: item.descriptor.priority,
            )
        )

    def _display_state(
        self,
        definition: _ProviderDefinitionView,
        record: ProviderCheckRecord | None,
        settings: ProviderSettingsRecord,
        settings_status: ProviderSettingsLoadStatus,
        *,
        manual_verified: bool = False,
    ) -> ProviderDisplayState:
        descriptor = definition.descriptor
        catalog_entry = definition.catalog_entry
        enabled = bool(settings.enabled)
        details = definition.configuration_details
        credential_result = self._credential_states.get((descriptor.id.casefold(), "api_key"))
        manual_evidence = (
            self.check_repository.manual_evidence(descriptor.id)
            if catalog_entry is not None and catalog_entry.registration_only
            else None
        )

        if catalog_entry is not None and catalog_entry.registration_only:
            if manual_verified:
                ui_state = ProviderUiState.WORKING if enabled else ProviderUiState.UNVERIFIED
                status_text = "Проверено" if enabled else "Готов к включению"
            else:
                ui_state = ProviderUiState.NOT_CONFIGURED
                status_text = (
                    "Адаптер настроен — требуется проверка подключения"
                    if catalog_entry.adapter_compiled
                    else (
                        "Протокол выбран — требуется создание адаптера"
                        if catalog_entry.protocol_configured
                        else "Требуется выбор протокола"
                    )
                )
        elif settings_status is ProviderSettingsLoadStatus.CORRUPT:
            ui_state = ProviderUiState.ERROR
            status_text = "Файл настроек повреждён; запуск заблокирован"
        elif settings_status is ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE:
            ui_state = ProviderUiState.ERROR
            status_text = "Версия файла настроек не поддерживается; запуск заблокирован"
        elif not enabled:
            ui_state = ProviderUiState.DISABLED
            status_text = "Отключён пользователем"
        elif record is not None:
            ui_state, status_text = _record_state(
                record,
                vertically_verified=(
                    self.vertical_verification_repository.is_working(descriptor.id)
                ),
            )
        else:
            ui_state, status_text = self._initial_state(definition, settings.configuration)

        return ProviderDisplayState(
            provider_id=descriptor.id.casefold(),
            display_name=descriptor.display_name,
            enabled=enabled,
            ui_state=ui_state,
            status_text=status_text,
            connection_mode=_connection_mode_label(definition.connection_mode),
            implementation_status=(descriptor.implementation_status),
            homepage_url=descriptor.homepage_url,
            last_checked_at=(
                manual_evidence.checked_at.isoformat(timespec="seconds")
                if manual_evidence is not None
                else record.checked_at
                if record
                else ""
            ),
            last_success_at=(
                manual_evidence.checked_at.isoformat(timespec="seconds")
                if manual_evidence is not None and manual_verified
                else record.last_success_at
                if record
                else ""
            ),
            last_error=(record.last_error if record else ""),
            latency_ms=(record.latency_ms if record else None),
            configuration_details=details,
            configuration=settings.configuration,
            enabled_origin=settings.enabled_origin,
            configuration_origin=settings.configuration_origin,
            enabled_editable=(
                (catalog_entry is None or not catalog_entry.registration_only or manual_verified)
                and settings.enabled_origin is not ProviderSettingOrigin.ENVIRONMENT
                and settings_status
                not in {
                    ProviderSettingsLoadStatus.CORRUPT,
                    ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE,
                }
            ),
            configuration_editable=(
                settings.configuration_editable
                and settings_status
                not in {
                    ProviderSettingsLoadStatus.CORRUPT,
                    ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE,
                }
            ),
            settings_status=settings_status,
            credential_state=(credential_result.state if credential_result is not None else None),
            origin=(
                catalog_entry.origin if catalog_entry is not None else ProviderCatalogOrigin.BUILTIN
            ),
            lifecycle=(catalog_entry.lifecycle if catalog_entry is not None else None),
            registration_only=(
                catalog_entry.registration_only if catalog_entry is not None else False
            ),
            runnable=(
                enabled and manual_verified
                if catalog_entry is not None and catalog_entry.registration_only
                else catalog_entry.runnable
                if catalog_entry is not None
                else True
            ),
            factory_available=(
                catalog_entry.factory_available if catalog_entry is not None else True
            ),
            protocol_configured=(
                catalog_entry.protocol_configured if catalog_entry is not None else True
            ),
            adapter_compiled=(
                catalog_entry.adapter_compiled if catalog_entry is not None else True
            ),
            credential_available=(
                (
                    catalog_entry.manual_registration is not None
                    and catalog_entry.manual_registration.protocol_selection is not None
                    and catalog_entry.manual_registration.adapter_spec is not None
                    and catalog_entry.manual_registration.protocol_selection.authentication_kind
                    is not ManualProviderAuthenticationKind.NONE
                )
                if catalog_entry is not None and catalog_entry.registration_only
                else catalog_entry.credential_available
                if catalog_entry is not None
                else False
            ),
            health_check_available=(
                catalog_entry.adapter_compiled
                if catalog_entry is not None and catalog_entry.registration_only
                else catalog_entry.health_check_available
                if catalog_entry is not None
                else True
            ),
            manual_registration=(
                catalog_entry.manual_registration if catalog_entry is not None else None
            ),
        )

    def _initial_state(
        self,
        definition: _ProviderDefinitionView,
        configuration: ProviderConfiguration,
    ) -> tuple[ProviderUiState, str]:
        provider_id = definition.descriptor.id.casefold()
        if provider_id == "eis":
            return (
                ProviderUiState.LIMITED,
                "Не проверен · резервный HTML-режим",
            )
        if provider_id == "mos_supplier":
            credential = self._credential_states.get((provider_id, "api_key"))
            if credential is None:
                if self.environment is not None:
                    return (
                        ProviderUiState.NOT_CONFIGURED,
                        "Credential не задан в hermetic environment",
                    )
                return (
                    ProviderUiState.UNKNOWN,
                    "Credential не проверялся",
                )
            if credential.state is CredentialState.NOT_CONFIGURED:
                return (ProviderUiState.NOT_CONFIGURED, credential.message)
            if credential.state in {
                CredentialState.BACKEND_UNAVAILABLE,
                CredentialState.INVALID_REQUEST,
            }:
                return (ProviderUiState.ERROR, credential.message)
            return (
                ProviderUiState.UNKNOWN,
                "Настроен, подключение не проверено",
            )

        if configuration.access_confirmed and configuration.api_base_url:
            return (
                ProviderUiState.UNKNOWN,
                "Non-secret настройки заполнены; нужны credentials и проверка",
            )
        return (
            ProviderUiState.NOT_CONFIGURED,
            _commercial_configuration_message(configuration),
        )


def _record_state(
    record: ProviderCheckRecord,
    *,
    vertically_verified: bool = False,
) -> tuple[ProviderUiState, str]:
    if record.status == ProviderHealthStatus.AVAILABLE:
        if not vertically_verified:
            return (
                ProviderUiState.UNVERIFIED,
                "Health-check успешен; полный C19 live-smoke не пройден",
            )
        return (
            ProviderUiState.WORKING,
            record.message or "Источник работает",
        )
    if record.status == ProviderHealthStatus.DEGRADED:
        return (
            ProviderUiState.LIMITED,
            record.message or "Ограниченный режим",
        )
    if record.status == ProviderHealthStatus.NOT_CONFIGURED:
        return (
            ProviderUiState.NOT_CONFIGURED,
            record.message or "Источник не настроен",
        )
    if record.status == ProviderHealthStatus.UNAVAILABLE:
        return (
            ProviderUiState.ERROR,
            record.message or "Источник недоступен",
        )
    return (
        ProviderUiState.UNKNOWN,
        record.message or "Состояние не определено",
    )


def _connection_mode_label(value: str) -> str:
    return {
        "public_html_async": ("Публичный HTML · резервный режим"),
        "official_api_bearer": ("Официальный API · Bearer"),
        "commercial_access_pending": ("API-доступ ожидает подтверждения"),
        "manual_protocol_required": "Ручная регистрация · протокол не выбран",
        "manual_protocol_selected": "Ручная регистрация · протокол выбран",
        "manual_adapter_unverified": "Ручной адаптер · подключение не проверено",
    }.get(value, value or "Не указан")


def _commercial_configuration_message(configuration: ProviderConfiguration) -> str:
    if not configuration.access_confirmed:
        return "Не подтверждён разрешённый способ доступа. Проверьте договор и право использования API."
    if not configuration.api_base_url:
        return "Разрешённый доступ подтверждён, но проверенный API endpoint не задан."
    return "Non-secret настройки доступа заполнены."


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _manual_command_result(
    provider_id: str,
    status: ManualProviderCommandStatus,
    error_category: ManualProviderErrorCategory,
    message: str,
    observed_at: datetime,
    lifecycle: ManualProviderLifecycle = ManualProviderLifecycle.PROTOCOL_REQUIRED,
) -> ManualProviderCommandResult:
    return ManualProviderCommandResult(
        provider_id=provider_id if provider_id.startswith("manual_") else "unknown",
        status=status,
        lifecycle=lifecycle,
        error_category=error_category,
        message=message,
        observed_at=observed_at,
    )


def _manual_protocol_command_result(
    provider_id: str,
    status: ManualProviderProtocolCommandStatus,
    lifecycle: ManualProviderLifecycle,
    error_category: ManualProviderProtocolErrorCategory,
    message: str,
    observed_at: datetime,
) -> ManualProviderProtocolCommandResult:
    return ManualProviderProtocolCommandResult(
        provider_id=provider_id if provider_id.startswith("manual_") else "unknown",
        status=status,
        lifecycle=ManualProviderProtocolReadiness(lifecycle.value),
        error_category=error_category,
        message=message,
        observed_at=observed_at,
    )


def _manual_adapter_command_result(
    provider_id: str,
    status: ManualAdapterCommandStatus,
    diagnostics: tuple,
    spec: ManualAdapterSpec | None,
    message: str,
    observed_at: datetime,
) -> ManualAdapterCommandResult:
    return ManualAdapterCommandResult(
        provider_id=provider_id if provider_id.startswith("manual_") else "unknown",
        status=status,
        readiness=ManualAdapterReadiness.CONNECTION_TEST_REQUIRED,
        diagnostics=diagnostics,
        fingerprint=spec.fingerprint if spec is not None else "",
        revision=spec.revision if spec is not None else None,
        message=message,
        observed_at=observed_at,
    )


__all__ = [
    "CollectorProviderManager",
    "ProviderCheckRecord",
    "ProviderCheckLoadResult",
    "ProviderCheckLoadStatus",
    "ProviderCheckRepository",
    "ProviderDisplayState",
    "ProviderUiState",
]
