"""Safe selection of an existing AI provider from canonical user settings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from urllib.parse import urlsplit

from app.ai.provider import AIProvider, DisabledProvider, OpenAICompatibleProvider

OPENAI_API_KEY_SECRET = "openai_api_key"
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_AI_MODEL = "gpt-4.1-mini"


class AiProviderId(StrEnum):
    """Stable provider identifiers stored in canonical configuration."""

    DISABLED = "disabled"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"


@dataclass(frozen=True, slots=True)
class AiProviderSettings:
    provider_id: AiProviderId
    model: str = DEFAULT_AI_MODEL
    base_url: str = OPENAI_DEFAULT_BASE_URL


@dataclass(frozen=True, slots=True)
class LegacyAiProviderSettings:
    provider_label: str = ""
    model: str = ""
    base_url: str = ""


@dataclass(frozen=True, slots=True)
class AiProviderResolution:
    requested_provider_id: str
    effective_provider_id: AiProviderId
    provider: AIProvider
    available: bool
    warnings: tuple[str, ...] = ()
    requires_restart: bool = False


class AiConfigStore(Protocol):
    def get(self, dotted_key: str, default: Any = None) -> Any: ...

    def update(self, values: Mapping[str, Any], *, save: bool = True) -> None: ...


class AiSecretStore(Protocol):
    def load(self, name: str) -> str | None: ...

    def save(self, name: str, value: str) -> None: ...

    def delete(self, name: str) -> None: ...


class AiKeyringSecretStore:
    """Production secret adapter over the existing keyring functions."""

    def load(self, name: str) -> str | None:
        from app.security.secrets import load_secret

        return load_secret(name)

    def save(self, name: str, value: str) -> None:
        from app.security.secrets import save_secret

        save_secret(name, value)

    def delete(self, name: str) -> None:
        from app.security.secrets import delete_secret

        delete_secret(name)


class AiProviderSelectionService:
    """Load, migrate, validate and resolve AI provider configuration safely."""

    def __init__(
        self,
        config: AiConfigStore,
        secret_store: AiSecretStore,
        *,
        environment_override: AiProviderSettings | None = None,
    ) -> None:
        self.config = config
        self.secret_store = secret_store
        self.environment_override = environment_override

    def load_settings(self) -> AiProviderSettings:
        if self.environment_override is not None:
            return self.environment_override
        requested, model, base_url = self._load_raw_settings()
        return AiProviderSettings(
            provider_id=_provider_id(requested) or AiProviderId.DISABLED,
            model=model,
            base_url=base_url,
        )

    def validate_settings(self, settings: AiProviderSettings) -> tuple[str, ...]:
        warnings: list[str] = []
        if settings.provider_id is AiProviderId.DISABLED:
            return ()
        if not _valid_model(settings.model):
            warnings.append("AI-модель не задана или некорректна.")
        if settings.provider_id is AiProviderId.OPENAI_COMPATIBLE and not _valid_base_url(
            settings.base_url
        ):
            warnings.append("Base URL AI-провайдера некорректен.")
        return tuple(warnings)

    def migrate_legacy_settings(self, legacy: LegacyAiProviderSettings | None) -> bool:
        """Migrate non-secret drafts while keeping the effective provider disabled."""

        if legacy is None or self.environment_override is not None:
            return False
        requested, current_model, current_base_url = self._load_raw_settings()
        normalized = requested.strip().casefold()
        if normalized not in {"", "none"}:
            return False

        model = _bounded_setting(legacy.model) or current_model
        base_url = _bounded_setting(legacy.base_url) or current_base_url
        self._save_settings(
            AiProviderSettings(
                provider_id=AiProviderId.DISABLED,
                model=model,
                base_url=base_url,
            )
        )
        return True

    def save_selection(
        self,
        settings: AiProviderSettings,
        *,
        credential: str | None = None,
    ) -> AiProviderResolution:
        warnings = self.validate_settings(settings)
        if warnings:
            return _disabled_resolution(
                settings.provider_id.value,
                warnings,
                requires_restart=True,
            )

        if settings.provider_id is AiProviderId.DISABLED:
            self._save_settings(settings)
            return _disabled_resolution(
                settings.provider_id.value,
                (),
                available=True,
                requires_restart=True,
            )

        new_credential = credential.strip() if credential is not None else ""
        if new_credential:
            try:
                self.secret_store.save(OPENAI_API_KEY_SECRET, new_credential)
            except Exception:
                return _disabled_resolution(
                    settings.provider_id.value,
                    ("API-ключ не сохранён; AI-провайдер остался отключён.",),
                    requires_restart=True,
                )

        candidate = self._resolve(
            settings,
            requested_provider_id=settings.provider_id.value,
            requires_restart=True,
        )
        if not candidate.available:
            return candidate
        self._save_settings(settings)
        return candidate

    def resolve_provider(self) -> AiProviderResolution:
        if self.environment_override is not None:
            settings = self.environment_override
            requested = settings.provider_id.value
        else:
            requested, model, base_url = self._load_raw_settings()
            provider_id = _provider_id(requested)
            if provider_id is None:
                return _disabled_resolution(
                    "unknown",
                    ("AI-провайдер не распознан и безопасно отключён.",),
                )
            settings = AiProviderSettings(provider_id, model, base_url)
        return self._resolve(settings, requested_provider_id=requested)

    def credential_available(self, provider_id: AiProviderId) -> bool:
        if provider_id is AiProviderId.DISABLED:
            return False
        credential, _warning = self._load_credential()
        return bool(credential)

    def delete_credential(self) -> bool:
        try:
            self.secret_store.delete(OPENAI_API_KEY_SECRET)
        except Exception:
            return False
        return True

    def _resolve(
        self,
        settings: AiProviderSettings,
        *,
        requested_provider_id: str,
        requires_restart: bool = False,
    ) -> AiProviderResolution:
        validation_warnings = self.validate_settings(settings)
        if validation_warnings:
            return _disabled_resolution(
                requested_provider_id,
                validation_warnings,
                requires_restart=requires_restart,
            )
        if settings.provider_id is AiProviderId.DISABLED:
            return _disabled_resolution(
                requested_provider_id,
                (),
                available=True,
                requires_restart=requires_restart,
            )

        credential, warning = self._load_credential()
        if not credential:
            return _disabled_resolution(
                requested_provider_id,
                (warning or "API-ключ AI-провайдера не найден.",),
                requires_restart=requires_restart,
            )

        base_url = (
            OPENAI_DEFAULT_BASE_URL
            if settings.provider_id is AiProviderId.OPENAI
            else settings.base_url.strip().rstrip("/")
        )
        provider = OpenAICompatibleProvider(
            credential,
            base_url,
            settings.model.strip(),
        )
        return AiProviderResolution(
            requested_provider_id=requested_provider_id,
            effective_provider_id=settings.provider_id,
            provider=provider,
            available=True,
            warnings=(),
            requires_restart=requires_restart,
        )

    def _load_credential(self) -> tuple[str, str]:
        try:
            credential = str(self.secret_store.load(OPENAI_API_KEY_SECRET) or "").strip()
        except Exception:
            return (
                "",
                "Хранилище API-ключа недоступно; AI-провайдер отключён.",
            )
        return credential, ""

    def _load_raw_settings(self) -> tuple[str, str, str]:
        try:
            requested = _bounded_setting(self.config.get("ai.provider", "disabled"))
            model = _bounded_setting(self.config.get("ai.model", DEFAULT_AI_MODEL))
            base_url = _bounded_setting(self.config.get("ai.base_url", OPENAI_DEFAULT_BASE_URL))
        except Exception:
            return "disabled", DEFAULT_AI_MODEL, OPENAI_DEFAULT_BASE_URL
        return (
            requested,
            model or DEFAULT_AI_MODEL,
            base_url or OPENAI_DEFAULT_BASE_URL,
        )

    def _save_settings(self, settings: AiProviderSettings) -> None:
        base_url = (
            OPENAI_DEFAULT_BASE_URL
            if settings.provider_id is AiProviderId.OPENAI
            else settings.base_url.strip()
        )
        self.config.update(
            {
                "ai": {
                    "provider": settings.provider_id.value,
                    "model": settings.model.strip(),
                    "base_url": base_url,
                }
            }
        )


def _provider_id(value: str) -> AiProviderId | None:
    normalized = value.strip().casefold()
    if normalized == "none":
        return AiProviderId.DISABLED
    try:
        return AiProviderId(normalized)
    except ValueError:
        return None


def _valid_model(value: str) -> bool:
    rendered = value.strip()
    return bool(rendered) and len(rendered) <= 200 and not any(ord(char) < 32 for char in rendered)


def _valid_base_url(value: str) -> bool:
    rendered = value.strip()
    if not rendered or len(rendered) > 2_000:
        return False
    try:
        parsed = urlsplit(rendered)
        _ = parsed.port
    except (TypeError, ValueError):
        return False
    return bool(
        parsed.scheme in {"http", "https"}
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )


def _bounded_setting(value: object) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return ""
    try:
        rendered = str(value).strip()
    except Exception:
        return ""
    return rendered[:2_000]


def _disabled_resolution(
    requested_provider_id: str,
    warnings: tuple[str, ...],
    *,
    available: bool = False,
    requires_restart: bool = False,
) -> AiProviderResolution:
    return AiProviderResolution(
        requested_provider_id=requested_provider_id,
        effective_provider_id=AiProviderId.DISABLED,
        provider=DisabledProvider(),
        available=available,
        warnings=warnings,
        requires_restart=requires_restart,
    )


__all__ = [
    "AiKeyringSecretStore",
    "AiProviderId",
    "AiProviderResolution",
    "AiProviderSelectionService",
    "AiProviderSettings",
    "AiSecretStore",
    "DEFAULT_AI_MODEL",
    "LegacyAiProviderSettings",
    "OPENAI_API_KEY_SECRET",
    "OPENAI_DEFAULT_BASE_URL",
]
