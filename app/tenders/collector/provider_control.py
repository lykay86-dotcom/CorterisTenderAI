"""Source management and connection diagnostics for the collector UI."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import json
from pathlib import Path
from threading import RLock

from app.tenders.collector.async_provider_factory import (
    create_default_async_providers,
)
from app.tenders.collector.network_runtime import (
    create_collector_network_runtime,
)
from app.tenders.collector.provider_settings import (
    ProviderConfiguration,
    ProviderEnablementRepository,
    ProviderSettingOrigin,
    ProviderSettingsRecord,
    ProviderSettingsLoadStatus,
    ProviderSettingsSnapshot,
    create_provider_settings_snapshot,
)
from app.tenders.provider_base import (
    ProviderDescriptor,
    ProviderHealth,
    ProviderHealthStatus,
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


class ProviderCheckRepository:
    """Persist only public provider diagnostics, never secrets."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = RLock()

    def load(self) -> dict[str, ProviderCheckRecord]:
        with self._lock:
            if not self.path.is_file():
                return {}
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError):
                return {}
            if not isinstance(payload, dict):
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

    def save(
        self,
        records: Mapping[str, ProviderCheckRecord],
    ) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": self.SCHEMA_VERSION,
                "providers": {
                    provider_id: {
                        "status": record.status.value,
                        "checked_at": record.checked_at,
                        "last_success_at": (record.last_success_at),
                        "message": record.message,
                        "last_error": record.last_error,
                        "latency_ms": record.latency_ms,
                    }
                    for provider_id, record in sorted(records.items())
                },
            }
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary.replace(self.path)

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

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")


@dataclass(frozen=True, slots=True)
class _ProviderDefinitionView:
    descriptor: ProviderDescriptor
    connection_mode: str
    configuration_details: tuple[str, ...]


HealthChecker = Callable[
    [tuple[str, ...]],
    Awaitable[Mapping[str, ProviderHealth]],
]


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
        vertical_verification_repository: (VerticalSourceVerificationRepository | None) = None,
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
            )
            for definition in definitions
        )

    def enabled_provider_ids(self) -> tuple[str, ...]:
        return self.settings_snapshot().enabled_provider_ids

    def settings_snapshot(self) -> ProviderSettingsSnapshot:
        return create_provider_settings_snapshot(
            self.settings_repository,
            environment=self.environment,
        )

    def resolve_provider_ids(self, provider_ids: Iterable[str]) -> tuple[str, ...]:
        return self.settings_snapshot().resolve_provider_ids(tuple(provider_ids))

    def set_enabled(
        self,
        provider_id: str,
        enabled: bool,
    ) -> ProviderDisplayState:
        normalized = self.resolve_provider_ids((provider_id,))[0]
        definitions = {
            item.descriptor.id.casefold(): item
            for item in self._definitions(self.settings_snapshot())
        }
        if normalized not in definitions:
            raise KeyError(provider_id)
        current = self.settings_snapshot().get(normalized)
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

    async def check_providers(
        self,
        provider_ids: Iterable[str],
    ) -> tuple[ProviderDisplayState, ...]:
        normalized_ids = tuple(
            dict.fromkeys(item.strip().casefold() for item in provider_ids if item.strip())
        )
        known = {state.provider_id: state for state in self.states()}
        unknown = [provider_id for provider_id in normalized_ids if provider_id not in known]
        if unknown:
            raise KeyError(", ".join(unknown))

        selected = tuple(
            provider_id for provider_id in normalized_ids if known[provider_id].enabled
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
        mos_config = MosSupplierApiConfig.from_environment(self.environment)
        result = [
            _ProviderDefinitionView(
                descriptor=AsyncEisTenderProvider.descriptor,
                connection_mode="public_html_async",
                configuration_details=(
                    "Публичный HTML-интерфейс ЕИС.",
                    "Резервный режим, не официальный API.",
                    "CAPTCHA и ограничения сайта не обходятся.",
                ),
            ),
            _ProviderDefinitionView(
                descriptor=(AsyncMosSupplierTenderProvider.descriptor),
                connection_mode="official_api_bearer",
                configuration_details=(
                    (
                        "Bearer-токен настроен."
                        if mos_config.configured
                        else ("Требуется CORTERIS_MOS_API_KEY.")
                    ),
                    "Официальный API Портала поставщиков.",
                ),
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
    ) -> ProviderDisplayState:
        descriptor = definition.descriptor
        enabled = bool(settings.enabled)
        details = definition.configuration_details

        if settings_status is ProviderSettingsLoadStatus.CORRUPT:
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
            last_checked_at=(record.checked_at if record else ""),
            last_success_at=(record.last_success_at if record else ""),
            last_error=(record.last_error if record else ""),
            latency_ms=(record.latency_ms if record else None),
            configuration_details=details,
            configuration=settings.configuration,
            enabled_origin=settings.enabled_origin,
            configuration_origin=settings.configuration_origin,
            enabled_editable=(
                settings.enabled_origin is not ProviderSettingOrigin.ENVIRONMENT
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
            config = MosSupplierApiConfig.from_environment(self.environment)
            if not config.configured:
                return (
                    ProviderUiState.NOT_CONFIGURED,
                    "Требуется bearer-токен",
                )
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
    }.get(value, value or "Не указан")


def _commercial_configuration_message(configuration: ProviderConfiguration) -> str:
    if not configuration.access_confirmed:
        return "Не подтверждён разрешённый способ доступа. Проверьте договор и право использования API."
    if not configuration.api_base_url:
        return "Разрешённый доступ подтверждён, но проверенный API endpoint не задан."
    return "Non-secret настройки доступа заполнены."


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "CollectorProviderManager",
    "ProviderCheckRecord",
    "ProviderCheckRepository",
    "ProviderDisplayState",
    "ProviderUiState",
]
