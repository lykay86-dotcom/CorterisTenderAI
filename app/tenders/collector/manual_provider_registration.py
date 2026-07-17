"""Pure registration-only contract for manually declared tender sources.

The metadata in this module is inert. It cannot select a protocol, construct an
adapter, access credentials or initiate network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from app.tenders.collector.manual_provider_protocol import (
    ManualProviderProtocolSelection,
)


_MANUAL_ID_PATTERN = re.compile(r"manual_[0-9a-f]{32}\Z")
_MALFORMED_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_PERCENT_ESCAPE = re.compile(r"%([0-9A-Fa-f]{2})")
_MAX_DISPLAY_NAME_LENGTH = 160
_MAX_URL_LENGTH = 2048


class ManualProviderLifecycle(StrEnum):
    PROTOCOL_REQUIRED = "protocol_required"
    ADAPTER_REQUIRED = "adapter_required"


class ManualProviderCommandStatus(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"
    INVALID_INPUT = "invalid_input"
    PERSISTENCE_UNAVAILABLE = "persistence_unavailable"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    OPERATION_FAILED_SAFE = "operation_failed_safe"


class ManualProviderErrorCategory(StrEnum):
    NONE = "none"
    DUPLICATE_NAME = "duplicate_name"
    DUPLICATE_ENDPOINT = "duplicate_endpoint"
    IDENTITY_COLLISION = "identity_collision"
    INVALID_INPUT = "invalid_input"
    PERSISTENCE_UNAVAILABLE = "persistence_unavailable"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    OPERATION_FAILED = "operation_failed"
    PROTOCOL_REQUIRED = "protocol_required"
    ADAPTER_REQUIRED = "adapter_required"


class ManualProviderConflictError(ValueError):
    """A bounded catalog conflict that never contains user metadata."""

    def __init__(self, category: ManualProviderErrorCategory) -> None:
        self.category = category
        super().__init__("manual provider conflict")


class ManualProviderExecutionError(RuntimeError):
    """Raised before runtime creation for a registration-only provider."""

    def __init__(
        self,
        lifecycle: ManualProviderLifecycle = ManualProviderLifecycle.PROTOCOL_REQUIRED,
    ) -> None:
        self.lifecycle = lifecycle
        self.category = (
            ManualProviderErrorCategory.PROTOCOL_REQUIRED
            if lifecycle is ManualProviderLifecycle.PROTOCOL_REQUIRED
            else ManualProviderErrorCategory.ADAPTER_REQUIRED
        )
        super().__init__(
            "Источник требует выбор протокола."
            if lifecycle is ManualProviderLifecycle.PROTOCOL_REQUIRED
            else "Для источника ещё не создан адаптер."
        )


@dataclass(frozen=True, slots=True)
class ManualProviderDraft:
    display_name: str
    homepage_url: str
    endpoint_url: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "display_name", normalize_manual_display_name(self.display_name))
        object.__setattr__(
            self,
            "homepage_url",
            normalize_manual_url(self.homepage_url, required=True),
        )
        object.__setattr__(
            self,
            "endpoint_url",
            normalize_manual_url(self.endpoint_url, required=False),
        )

    @classmethod
    def unvalidated(
        cls,
        *,
        display_name: str,
        homepage_url: str,
        endpoint_url: str = "",
    ) -> "ManualProviderDraft":
        """Create an ingress object for application-boundary rejection tests.

        Production UI uses the normal validated constructor. Manager commands
        always reconstruct and validate a received draft before persistence.
        """

        value = object.__new__(cls)
        object.__setattr__(value, "display_name", display_name)
        object.__setattr__(value, "homepage_url", homepage_url)
        object.__setattr__(value, "endpoint_url", endpoint_url)
        return value


@dataclass(frozen=True, slots=True)
class ManualProviderRegistration:
    provider_id: str
    display_name: str
    homepage_url: str
    endpoint_url: str = field(default="", repr=False)
    lifecycle_state: ManualProviderLifecycle = ManualProviderLifecycle.PROTOCOL_REQUIRED
    protocol_selection: ManualProviderProtocolSelection | None = field(
        default=None,
        repr=False,
    )
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        normalized_id = str(self.provider_id).strip()
        if not _MANUAL_ID_PATTERN.fullmatch(normalized_id):
            raise ValueError("manual provider id must use the canonical namespace")
        if self.protocol_selection is None:
            if self.lifecycle_state is not ManualProviderLifecycle.PROTOCOL_REQUIRED:
                raise ValueError("manual provider lifecycle is inconsistent")
        elif (
            not isinstance(self.protocol_selection, ManualProviderProtocolSelection)
            or self.lifecycle_state is not ManualProviderLifecycle.ADAPTER_REQUIRED
        ):
            raise ValueError("manual provider lifecycle is inconsistent")
        _validate_aware_timestamp(self.created_at, field_name="created timestamp")
        _validate_aware_timestamp(self.updated_at, field_name="updated timestamp")
        if self.updated_at < self.created_at:
            raise ValueError("updated timestamp must not precede created timestamp")
        object.__setattr__(self, "provider_id", normalized_id)
        object.__setattr__(self, "display_name", normalize_manual_display_name(self.display_name))
        object.__setattr__(
            self,
            "homepage_url",
            normalize_manual_url(self.homepage_url, required=True),
        )
        object.__setattr__(
            self,
            "endpoint_url",
            normalize_manual_url(self.endpoint_url, required=False),
        )

    @property
    def enabled(self) -> bool:
        return False

    @property
    def registration_only(self) -> bool:
        return True

    @property
    def display_name_key(self) -> str:
        return manual_display_name_key(self.display_name)

    @property
    def endpoint_identity(self) -> str:
        return self.endpoint_url

    def public_payload(self) -> dict[str, object]:
        """Return only metadata safe for generic display/export boundaries."""

        payload: dict[str, object] = {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "homepage_url": self.homepage_url,
            "lifecycle_state": self.lifecycle_state.value,
            "enabled": False,
            "registration_only": True,
        }
        if self.protocol_selection is not None:
            payload["protocol_selection"] = self.protocol_selection.public_payload()
        return payload

    def persisted_payload(self) -> dict[str, object]:
        return {
            "display_name": self.display_name,
            "homepage_url": self.homepage_url,
            "endpoint_url": self.endpoint_url,
            "lifecycle_state": self.lifecycle_state.value,
            "protocol_selection": (
                self.protocol_selection.persisted_payload()
                if self.protocol_selection is not None
                else None
            ),
            "created_at": self.created_at.astimezone(timezone.utc).isoformat(
                timespec="microseconds"
            ),
            "updated_at": self.updated_at.astimezone(timezone.utc).isoformat(
                timespec="microseconds"
            ),
        }


@dataclass(frozen=True, slots=True)
class ManualProviderCommandResult:
    provider_id: str
    status: ManualProviderCommandStatus
    lifecycle: ManualProviderLifecycle
    error_category: ManualProviderErrorCategory
    message: str
    observed_at: datetime

    def __post_init__(self) -> None:
        _validate_aware_timestamp(self.observed_at, field_name="operation timestamp")


def create_manual_provider_id() -> str:
    return f"manual_{uuid4().hex}"


def create_manual_provider_registration(
    draft: ManualProviderDraft,
    *,
    provider_id: str,
    timestamp: datetime,
) -> ManualProviderRegistration:
    validated = ManualProviderDraft(
        display_name=draft.display_name,
        homepage_url=draft.homepage_url,
        endpoint_url=draft.endpoint_url,
    )
    return ManualProviderRegistration(
        provider_id=provider_id,
        display_name=validated.display_name,
        homepage_url=validated.homepage_url,
        endpoint_url=validated.endpoint_url,
        lifecycle_state=ManualProviderLifecycle.PROTOCOL_REQUIRED,
        protocol_selection=None,
        created_at=timestamp,
        updated_at=timestamp,
    )


def normalize_manual_display_name(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("manual provider display name is invalid")
    if any(_forbidden_text_character(character) for character in value):
        raise ValueError("manual provider display name is invalid")
    normalized = unicodedata.normalize("NFKC", value)
    normalized = " ".join(normalized.strip().split())
    if not normalized or len(normalized) > _MAX_DISPLAY_NAME_LENGTH:
        raise ValueError("manual provider display name is invalid")
    return normalized


def manual_display_name_key(value: str) -> str:
    return normalize_manual_display_name(value).casefold()


def normalize_manual_url(value: object, *, required: bool) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise ValueError("manual provider URL is invalid")
    raw = value.strip(" ")
    if not raw:
        if required:
            raise ValueError("manual provider URL is invalid")
        return ""
    if len(raw) > _MAX_URL_LENGTH:
        raise ValueError("manual provider URL is invalid")
    if any(character.isspace() or _forbidden_text_character(character) for character in raw):
        raise ValueError("manual provider URL is invalid")
    if _MALFORMED_PERCENT.search(raw):
        raise ValueError("manual provider URL is invalid")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        raise ValueError("manual provider URL is invalid") from None
    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("manual provider URL is invalid")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("manual provider URL is invalid")
    if parsed.query or parsed.fragment:
        raise ValueError("manual provider URL is invalid")
    try:
        hostname = parsed.hostname.encode("idna").decode("ascii").casefold()
    except UnicodeError:
        raise ValueError("manual provider URL is invalid") from None
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    path = parsed.path.rstrip("/")
    path = _PERCENT_ESCAPE.sub(lambda match: f"%{match.group(1).upper()}", path)
    return urlunsplit((scheme, netloc, path, "", ""))


def validate_manual_registration_uniqueness(
    registrations: tuple[ManualProviderRegistration, ...],
) -> None:
    ids: set[str] = set()
    names: set[str] = set()
    endpoints: set[str] = set()
    for registration in registrations:
        if registration.provider_id in ids:
            raise ManualProviderConflictError(ManualProviderErrorCategory.IDENTITY_COLLISION)
        ids.add(registration.provider_id)
        if registration.display_name_key in names:
            raise ManualProviderConflictError(ManualProviderErrorCategory.DUPLICATE_NAME)
        names.add(registration.display_name_key)
        if registration.endpoint_identity:
            if registration.endpoint_identity in endpoints:
                raise ManualProviderConflictError(ManualProviderErrorCategory.DUPLICATE_ENDPOINT)
            endpoints.add(registration.endpoint_identity)


def _forbidden_text_character(character: str) -> bool:
    return unicodedata.category(character) in {"Cc", "Cf", "Cs"}


def _validate_aware_timestamp(value: object, *, field_name: str) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


__all__ = [
    "ManualProviderCommandResult",
    "ManualProviderCommandStatus",
    "ManualProviderConflictError",
    "ManualProviderDraft",
    "ManualProviderErrorCategory",
    "ManualProviderExecutionError",
    "ManualProviderLifecycle",
    "ManualProviderRegistration",
    "create_manual_provider_id",
    "create_manual_provider_registration",
    "manual_display_name_key",
    "normalize_manual_display_name",
    "normalize_manual_url",
    "validate_manual_registration_uniqueness",
]
