"""Configuration and readiness catalog for commercial tender platforms.

The module deliberately does not pretend that a working API integration exists.
It stores non-secret enablement settings, resolves secrets from environment or
Windows keyring and reports the exact reason why a provider cannot yet be used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import json
import os
from pathlib import Path
from typing import Callable, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

from app.tenders.models import TenderSource
from app.tenders.provider_base import ProviderCapabilities, ProviderDescriptor


class CommercialAccessRequirement(StrEnum):
    """High-level access requirement declared for a future connector."""

    CONTRACT_AND_API = "contract_and_api"
    API_CREDENTIALS = "api_credentials"
    CONTRACT_CONFIRMATION = "contract_confirmation"


class CommercialProviderState(StrEnum):
    """Honest readiness states shown to the user and diagnostics."""

    DISABLED = "disabled"
    CONTRACT_REQUIRED = "contract_required"
    CREDENTIALS_REQUIRED = "credentials_required"
    ENDPOINT_REQUIRED = "endpoint_required"
    READY_FOR_VERIFICATION = "ready_for_verification"


@dataclass(frozen=True, slots=True)
class CommercialProviderDefinition:
    provider_id: str
    display_name: str
    source: TenderSource
    homepage_url: str
    priority: int
    access_requirement: CommercialAccessRequirement
    enabled_environment_variable: str
    access_confirmed_environment_variable: str
    api_key_environment_variable: str
    api_base_url_environment_variable: str
    keyring_secret_name: str
    implementation_status: str = "commercial_access_pending"
    notes: str = (
        "Требуется подтвердить разрешённый способ интеграции и формат "
        "ответов площадки до включения сетевого адаптера."
    )

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            id=self.provider_id,
            display_name=self.display_name,
            source=self.source,
            homepage_url=self.homepage_url,
            capabilities=ProviderCapabilities(
                search=True,
                tender_details=True,
                documents=True,
                authentication=True,
                public_api=False,
                incremental_updates=False,
            ),
            enabled_by_default=False,
            priority=self.priority,
            implementation_status=self.implementation_status,
        )


@dataclass(frozen=True, slots=True)
class CommercialProviderUserSettings:
    """Non-secret settings that may safely be persisted as JSON."""

    enabled: bool = False
    access_confirmed: bool = False
    api_base_url: str = ""


@dataclass(frozen=True, slots=True)
class CommercialProviderResolvedSettings:
    definition: CommercialProviderDefinition
    enabled: bool
    access_confirmed: bool
    api_base_url: str
    api_key: str = field(default="", repr=False, compare=False)

    @property
    def masked_api_key(self) -> str:
        value = self.api_key.strip()
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}…{value[-4:]}"

    @property
    def state(self) -> CommercialProviderState:
        if not self.enabled:
            return CommercialProviderState.DISABLED
        if not self.access_confirmed:
            return CommercialProviderState.CONTRACT_REQUIRED
        if not self.api_key.strip():
            return CommercialProviderState.CREDENTIALS_REQUIRED
        if not self.api_base_url.strip():
            return CommercialProviderState.ENDPOINT_REQUIRED
        return CommercialProviderState.READY_FOR_VERIFICATION

    @property
    def message(self) -> str:
        state = self.state
        if state == CommercialProviderState.DISABLED:
            return "Источник отключён пользователем."
        if state == CommercialProviderState.CONTRACT_REQUIRED:
            return (
                "Не подтверждён разрешённый способ доступа. "
                "Проверьте договор, условия площадки и право использования API."
            )
        if state == CommercialProviderState.CREDENTIALS_REQUIRED:
            return "Доступ подтверждён, но API-ключ или учётные данные не заданы."
        if state == CommercialProviderState.ENDPOINT_REQUIRED:
            return (
                "Ключ найден, но проверенный API endpoint не настроен. "
                "Не используйте предполагаемый или недокументированный адрес."
            )
        return (
            "Настройки заполнены. API-контракт и реальный разрешённый ответ "
            "ещё не проверены; рабочим источник не считается."
        )

    @property
    def can_register_in_search_engine(self) -> bool:
        return self.enabled

    @property
    def is_working(self) -> bool:
        # No commercial connector in C6 has a verified response contract yet.
        return False

    def public_payload(self) -> dict[str, object]:
        return {
            "provider_id": self.definition.provider_id,
            "display_name": self.definition.display_name,
            "state": self.state.value,
            "message": self.message,
            "enabled": self.enabled,
            "access_confirmed": self.access_confirmed,
            "api_base_url": _public_endpoint(self.api_base_url),
            "api_key_configured": bool(self.api_key.strip()),
            "masked_api_key": self.masked_api_key,
            "implementation_status": self.definition.implementation_status,
            "working": self.is_working,
        }


SecretLoader = Callable[[str], str | None]


class CommercialSecretResolver:
    """Resolve production secrets without leaking host keyring into tests."""

    def __init__(
        self,
        *,
        environment: Mapping[str, str] | None = None,
        keyring_loader: SecretLoader | None = None,
    ) -> None:
        self.environment = environment if environment is not None else os.environ
        self._keyring_loader = (
            keyring_loader
            if keyring_loader is not None
            else (_load_keyring_secret_safely if environment is None else None)
        )
        self.last_error = ""

    def resolve(
        self,
        environment_variable: str,
        keyring_name: str,
    ) -> str:
        from_environment = str(self.environment.get(environment_variable, "")).strip()
        if from_environment:
            return from_environment

        loader = self._keyring_loader
        if loader is None:
            self.last_error = ""
            return ""
        try:
            self.last_error = ""
            return str(loader(keyring_name) or "").strip()
        except Exception as exc:
            # A broken keyring backend must not prevent application startup.
            # Keep a non-secret diagnostic instead of silently discarding it.
            self.last_error = f"{type(exc).__name__}: {exc}"
            return ""


class CommercialProviderSettingsRepository:
    """Persist only non-secret provider settings in an atomic JSON file."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def load(self) -> dict[str, CommercialProviderUserSettings]:
        if not self.path.is_file():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        providers = payload.get("providers", {})
        if not isinstance(providers, dict):
            return {}

        result: dict[str, CommercialProviderUserSettings] = {}
        for provider_id, raw in providers.items():
            if not isinstance(raw, dict):
                continue
            result[str(provider_id).strip().casefold()] = CommercialProviderUserSettings(
                enabled=bool(raw.get("enabled", False)),
                access_confirmed=bool(raw.get("access_confirmed", False)),
                api_base_url=_normalize_api_base_url(str(raw.get("api_base_url", ""))),
            )
        return result

    def save(
        self,
        settings: Mapping[str, CommercialProviderUserSettings],
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "providers": {
                provider_id: {
                    "enabled": value.enabled,
                    "access_confirmed": value.access_confirmed,
                    "api_base_url": _normalize_api_base_url(value.api_base_url),
                }
                for provider_id, value in sorted(settings.items())
            },
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def update(
        self,
        provider_id: str,
        value: CommercialProviderUserSettings,
    ) -> None:
        settings = self.load()
        settings[provider_id.strip().casefold()] = value
        self.save(settings)


class CommercialProviderCatalog:
    """Resolve readiness for all commercial platforms without network I/O."""

    def __init__(
        self,
        definitions: Iterable[CommercialProviderDefinition],
        *,
        repository: CommercialProviderSettingsRepository | None = None,
        secret_resolver: CommercialSecretResolver | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        ordered = tuple(sorted(definitions, key=lambda item: item.priority))
        ids = [item.provider_id.casefold() for item in ordered]
        if len(ids) != len(set(ids)):
            raise ValueError("commercial provider ids must be unique")
        self.definitions = ordered
        self.repository = repository
        self.environment = environment if environment is not None else os.environ
        self.secret_resolver = secret_resolver or CommercialSecretResolver(
            environment=self.environment
        )

    def resolve_all(self) -> tuple[CommercialProviderResolvedSettings, ...]:
        persisted = self.repository.load() if self.repository else {}
        return tuple(
            self._resolve(definition, persisted.get(definition.provider_id))
            for definition in self.definitions
        )

    def get(self, provider_id: str) -> CommercialProviderResolvedSettings:
        normalized = provider_id.strip().casefold()
        for item in self.resolve_all():
            if item.definition.provider_id.casefold() == normalized:
                return item
        raise KeyError(provider_id)

    def public_payload(self) -> list[dict[str, object]]:
        return [item.public_payload() for item in self.resolve_all()]

    def _resolve(
        self,
        definition: CommercialProviderDefinition,
        persisted: CommercialProviderUserSettings | None,
    ) -> CommercialProviderResolvedSettings:
        persisted = persisted or CommercialProviderUserSettings()
        enabled = _environment_bool(
            self.environment,
            definition.enabled_environment_variable,
            default=persisted.enabled,
        )
        access_confirmed = _environment_bool(
            self.environment,
            definition.access_confirmed_environment_variable,
            default=persisted.access_confirmed,
        )
        api_base_url = _normalize_api_base_url(
            str(
                self.environment.get(
                    definition.api_base_url_environment_variable,
                    persisted.api_base_url,
                )
            )
        )
        api_key = self.secret_resolver.resolve(
            definition.api_key_environment_variable,
            definition.keyring_secret_name,
        )
        return CommercialProviderResolvedSettings(
            definition=definition,
            enabled=enabled,
            access_confirmed=access_confirmed,
            api_base_url=api_base_url,
            api_key=api_key,
        )


def default_commercial_provider_definitions() -> tuple[CommercialProviderDefinition, ...]:
    """Return planned commercial connectors with no assumed API endpoint."""

    return (
        _definition(
            "b2b_center",
            "B2B-Center",
            TenderSource.B2B_CENTER,
            "https://www.b2b-center.ru/",
            50,
            "B2B",
        ),
        _definition(
            "gazprombank",
            "ЭТП ГПБ",
            TenderSource.GAZPROMBANK,
            "https://etpgpb.ru/",
            60,
            "GPB",
        ),
        _definition(
            "fabrikant",
            "Фабрикант",
            TenderSource.FABRIKANT,
            "https://www.fabrikant.ru/",
            70,
            "FABRIKANT",
        ),
        _definition(
            "tek_torg",
            "ТЭК-Торг",
            TenderSource.TEK_TORG,
            "https://www.tektorg.ru/",
            80,
            "TEK_TORG",
        ),
        _definition(
            "otc",
            "OTC",
            TenderSource.OTC,
            "https://otc.ru/",
            90,
            "OTC",
        ),
        _definition(
            "sber_commercial",
            "Сбер А — коммерческие закупки",
            TenderSource.SBER_A,
            "https://www.sberbank-ast.ru/",
            100,
            "SBER_COMMERCIAL",
        ),
        _definition(
            "rts_commercial",
            "РТС-тендер — коммерческие закупки",
            TenderSource.RTS_TENDER,
            "https://www.rts-tender.ru/",
            110,
            "RTS_COMMERCIAL",
        ),
        _definition(
            "roseltorg_commercial",
            "Росэлторг — коммерческие закупки",
            TenderSource.ROSELTORG,
            "https://www.roseltorg.ru/",
            120,
            "ROSELTORG_COMMERCIAL",
        ),
    )


def create_commercial_provider_catalog(
    *,
    settings_path: str | Path | None = None,
    environment: Mapping[str, str] | None = None,
    keyring_loader: SecretLoader | None = None,
) -> CommercialProviderCatalog:
    repository = (
        CommercialProviderSettingsRepository(settings_path) if settings_path is not None else None
    )
    resolver = CommercialSecretResolver(
        environment=environment,
        keyring_loader=keyring_loader,
    )
    return CommercialProviderCatalog(
        default_commercial_provider_definitions(),
        repository=repository,
        secret_resolver=resolver,
        environment=environment,
    )


def _definition(
    provider_id: str,
    display_name: str,
    source: TenderSource,
    homepage_url: str,
    priority: int,
    prefix: str,
) -> CommercialProviderDefinition:
    return CommercialProviderDefinition(
        provider_id=provider_id,
        display_name=display_name,
        source=source,
        homepage_url=homepage_url,
        priority=priority,
        access_requirement=CommercialAccessRequirement.CONTRACT_AND_API,
        enabled_environment_variable=f"CORTERIS_{prefix}_ENABLED",
        access_confirmed_environment_variable=(f"CORTERIS_{prefix}_ACCESS_CONFIRMED"),
        api_key_environment_variable=f"CORTERIS_{prefix}_API_KEY",
        api_base_url_environment_variable=(f"CORTERIS_{prefix}_API_BASE_URL"),
        keyring_secret_name=f"collector.{provider_id}.api_key",
    )


def _environment_bool(
    environment: Mapping[str, str],
    key: str,
    *,
    default: bool,
) -> bool:
    raw = environment.get(key)
    if raw is None:
        return default
    normalized = str(raw).strip().casefold()
    if normalized in {"1", "true", "yes", "on", "да"}:
        return True
    if normalized in {"0", "false", "no", "off", "нет", ""}:
        return False
    return default


def _normalize_api_base_url(value: str) -> str:
    """Accept only an HTTP(S) endpoint without embedded credentials/query."""

    raw = value.strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return ""
    hostname = parsed.hostname
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, hostname + port, path, "", ""))


def _public_endpoint(value: str) -> str:
    """Render an endpoint without user-info, query parameters or fragment."""

    raw = value.strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return "configured"
    if not parsed.scheme or not parsed.netloc:
        return "configured"
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit((parsed.scheme, hostname + port, parsed.path, "", ""))


def _load_keyring_secret_safely(name: str) -> str | None:
    try:
        from app.security.secrets import load_secret
    except Exception:
        return None
    return load_secret(name)


__all__ = [
    "CommercialAccessRequirement",
    "CommercialProviderCatalog",
    "CommercialProviderDefinition",
    "CommercialProviderResolvedSettings",
    "CommercialProviderSettingsRepository",
    "CommercialProviderState",
    "CommercialProviderUserSettings",
    "CommercialSecretResolver",
    "create_commercial_provider_catalog",
    "default_commercial_provider_definitions",
]
