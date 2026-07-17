"""Pure declarative protocol selection for registration-only tender providers.

This module deliberately has no transport, DNS, credential or adapter imports.
Endpoint validation is syntactic and policy-based; it never claims reachability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import ipaddress
import re
import unicodedata
from urllib.parse import unquote, urlsplit, urlunsplit


_MALFORMED_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_PERCENT_ESCAPE = re.compile(r"%([0-9A-Fa-f]{2})")
_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_AMBIGUOUS_NUMERIC_HOST = re.compile(r"(?:[0-9.]+|0x[0-9a-f]+)\Z", re.IGNORECASE)
_SECRET_LIKE = re.compile(
    r"(?:api[_-]?key|access[_-]?token|password|passwd|secret|authorization|bearer)",
    re.IGNORECASE,
)
_UNSAFE_FTP_PATH = re.compile(r"[\\*?\[\]{}|;`$<>]")
_MAX_ENDPOINT_LENGTH = 2048


class ManualProviderProtocolFamily(StrEnum):
    API = "api"
    RSS = "rss"
    FTP = "ftp"
    FTPS = "ftps"


class ManualProviderPayloadFormat(StrEnum):
    JSON = "json"
    XML = "xml"
    RSS = "rss"
    ATOM = "atom"


class ManualProviderAuthenticationKind(StrEnum):
    NONE = "none"
    API_KEY = "api_key"
    USERNAME_PASSWORD = "username_password"


class ManualProviderTlsPolicy(StrEnum):
    REQUIRED = "required"
    PLAINTEXT_WARNING = "plaintext_warning"


class ManualProviderProtocolCommandStatus(StrEnum):
    SAVED = "saved"
    CHANGED = "changed"
    CLEARED = "cleared"
    STALE = "stale"
    NOT_FOUND = "not_found"
    UNSUPPORTED_TARGET = "unsupported_target"
    INVALID_INPUT = "invalid_input"
    PERSISTENCE_UNAVAILABLE = "persistence_unavailable"
    OPERATION_FAILED_SAFE = "operation_failed_safe"


class ManualProviderProtocolErrorCategory(StrEnum):
    NONE = "none"
    STALE_EDIT = "stale_edit"
    NOT_FOUND = "not_found"
    UNSUPPORTED_TARGET = "unsupported_target"
    INVALID_INPUT = "invalid_input"
    PERSISTENCE_UNAVAILABLE = "persistence_unavailable"
    OPERATION_FAILED = "operation_failed"


class ManualProviderProtocolReadiness(StrEnum):
    PROTOCOL_REQUIRED = "protocol_required"
    ADAPTER_REQUIRED = "adapter_required"


@dataclass(frozen=True, slots=True)
class ManualProviderProtocolPolicy:
    family: ManualProviderProtocolFamily
    display_name: str
    allowed_schemes: tuple[str, ...]
    allowed_payload_formats: tuple[ManualProviderPayloadFormat, ...]
    allowed_authentication_kinds: tuple[ManualProviderAuthenticationKind, ...]
    tls_policy: ManualProviderTlsPolicy
    default_port: int
    endpoint_placeholder: str
    warning: str


_POLICIES = (
    ManualProviderProtocolPolicy(
        family=ManualProviderProtocolFamily.API,
        display_name="API",
        allowed_schemes=("https",),
        allowed_payload_formats=(
            ManualProviderPayloadFormat.JSON,
            ManualProviderPayloadFormat.XML,
        ),
        allowed_authentication_kinds=(
            ManualProviderAuthenticationKind.NONE,
            ManualProviderAuthenticationKind.API_KEY,
        ),
        tls_policy=ManualProviderTlsPolicy.REQUIRED,
        default_port=443,
        endpoint_placeholder="https://api.example.ru/v1",
        warning="Разрешён только HTTPS; доступность endpoint не проверяется.",
    ),
    ManualProviderProtocolPolicy(
        family=ManualProviderProtocolFamily.RSS,
        display_name="RSS/Atom",
        allowed_schemes=("https",),
        allowed_payload_formats=(
            ManualProviderPayloadFormat.RSS,
            ManualProviderPayloadFormat.ATOM,
        ),
        allowed_authentication_kinds=(ManualProviderAuthenticationKind.NONE,),
        tls_policy=ManualProviderTlsPolicy.REQUIRED,
        default_port=443,
        endpoint_placeholder="https://example.ru/feed.xml",
        warning="Разрешён только HTTPS; содержимое feed не загружается.",
    ),
    ManualProviderProtocolPolicy(
        family=ManualProviderProtocolFamily.FTP,
        display_name="FTP",
        allowed_schemes=("ftp",),
        allowed_payload_formats=(),
        allowed_authentication_kinds=(
            ManualProviderAuthenticationKind.NONE,
            ManualProviderAuthenticationKind.USERNAME_PASSWORD,
        ),
        tls_policy=ManualProviderTlsPolicy.PLAINTEXT_WARNING,
        default_port=21,
        endpoint_placeholder="ftp://files.example.ru/tenders",
        warning="FTP передаёт данные без TLS; секреты в endpoint запрещены.",
    ),
    ManualProviderProtocolPolicy(
        family=ManualProviderProtocolFamily.FTPS,
        display_name="FTPS",
        allowed_schemes=("ftps",),
        allowed_payload_formats=(),
        allowed_authentication_kinds=(
            ManualProviderAuthenticationKind.NONE,
            ManualProviderAuthenticationKind.USERNAME_PASSWORD,
        ),
        tls_policy=ManualProviderTlsPolicy.REQUIRED,
        default_port=990,
        endpoint_placeholder="ftps://files.example.ru/tenders",
        warning="TLS обязателен; downgrade до FTP запрещён.",
    ),
)


def manual_provider_protocol_policies() -> tuple[ManualProviderProtocolPolicy, ...]:
    return _POLICIES


def manual_provider_protocol_policy(
    family: ManualProviderProtocolFamily,
) -> ManualProviderProtocolPolicy:
    if not isinstance(family, ManualProviderProtocolFamily):
        raise ValueError("manual provider protocol selection is invalid")
    for policy in _POLICIES:
        if policy.family is family:
            return policy
    raise ValueError("manual provider protocol selection is invalid")


@dataclass(frozen=True, slots=True)
class ManualProviderProtocolDraft:
    family: ManualProviderProtocolFamily
    endpoint_url: str = field(repr=False)
    payload_format: ManualProviderPayloadFormat | None = None
    authentication_kind: ManualProviderAuthenticationKind = ManualProviderAuthenticationKind.NONE

    def __post_init__(self) -> None:
        policy = manual_provider_protocol_policy(self.family)
        if self.payload_format not in policy.allowed_payload_formats:
            if self.payload_format is not None or policy.allowed_payload_formats:
                raise ValueError("manual provider protocol selection is invalid")
        if self.authentication_kind not in policy.allowed_authentication_kinds:
            raise ValueError("manual provider protocol selection is invalid")
        object.__setattr__(
            self,
            "endpoint_url",
            normalize_manual_protocol_endpoint(self.endpoint_url, policy=policy),
        )

    @classmethod
    def unvalidated(
        cls,
        *,
        family: object,
        endpoint_url: object,
        payload_format: object = None,
        authentication_kind: object = ManualProviderAuthenticationKind.NONE,
    ) -> "ManualProviderProtocolDraft":
        value = object.__new__(cls)
        object.__setattr__(value, "family", family)
        object.__setattr__(value, "endpoint_url", endpoint_url)
        object.__setattr__(value, "payload_format", payload_format)
        object.__setattr__(value, "authentication_kind", authentication_kind)
        return value


@dataclass(frozen=True, slots=True)
class ManualProviderProtocolSelection:
    family: ManualProviderProtocolFamily
    endpoint_url: str = field(repr=False)
    payload_format: ManualProviderPayloadFormat | None = None
    authentication_kind: ManualProviderAuthenticationKind = ManualProviderAuthenticationKind.NONE
    selected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        validated = ManualProviderProtocolDraft(
            family=self.family,
            endpoint_url=self.endpoint_url,
            payload_format=self.payload_format,
            authentication_kind=self.authentication_kind,
        )
        _validate_aware_timestamp(self.selected_at)
        _validate_aware_timestamp(self.updated_at)
        if self.updated_at < self.selected_at:
            raise ValueError("manual provider protocol selection timestamp is invalid")
        object.__setattr__(self, "endpoint_url", validated.endpoint_url)

    def public_payload(self) -> dict[str, object]:
        return {
            "family": self.family.value,
            "payload_format": self.payload_format.value if self.payload_format else None,
            "authentication_kind": self.authentication_kind.value,
            "tls_policy": manual_provider_protocol_policy(self.family).tls_policy.value,
            "selected_at": self.selected_at.astimezone(timezone.utc).isoformat(
                timespec="microseconds"
            ),
            "updated_at": self.updated_at.astimezone(timezone.utc).isoformat(
                timespec="microseconds"
            ),
        }

    def persisted_payload(self) -> dict[str, object]:
        return {
            **self.public_payload(),
            "endpoint_url": self.endpoint_url,
        }

    def readiness_gaps(self) -> tuple[str, ...]:
        return ("adapter_required",)


@dataclass(frozen=True, slots=True)
class ManualProviderProtocolCommandResult:
    provider_id: str
    status: ManualProviderProtocolCommandStatus
    lifecycle: ManualProviderProtocolReadiness
    error_category: ManualProviderProtocolErrorCategory
    message: str
    observed_at: datetime

    def __post_init__(self) -> None:
        _validate_aware_timestamp(self.observed_at)


def create_manual_provider_protocol_selection(
    draft: ManualProviderProtocolDraft,
    *,
    timestamp: datetime,
    selected_at: datetime | None = None,
) -> ManualProviderProtocolSelection:
    validated = ManualProviderProtocolDraft(
        family=draft.family,
        endpoint_url=draft.endpoint_url,
        payload_format=draft.payload_format,
        authentication_kind=draft.authentication_kind,
    )
    return ManualProviderProtocolSelection(
        family=validated.family,
        endpoint_url=validated.endpoint_url,
        payload_format=validated.payload_format,
        authentication_kind=validated.authentication_kind,
        selected_at=selected_at or timestamp,
        updated_at=timestamp,
    )


def normalize_manual_protocol_endpoint(
    value: object,
    *,
    policy: ManualProviderProtocolPolicy,
) -> str:
    if not isinstance(value, str):
        raise ValueError("manual provider protocol selection is invalid")
    raw = value.strip(" ")
    if (
        not raw
        or len(raw) > _MAX_ENDPOINT_LENGTH
        or _MALFORMED_PERCENT.search(raw)
        or any(character.isspace() or _forbidden_character(character) for character in raw)
    ):
        raise ValueError("manual provider protocol selection is invalid")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        raise ValueError("manual provider protocol selection is invalid") from None
    scheme = parsed.scheme.casefold()
    if scheme not in policy.allowed_schemes or not parsed.hostname:
        raise ValueError("manual provider protocol selection is invalid")
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("manual provider protocol selection is invalid")
    if port is not None and port != policy.default_port:
        raise ValueError("manual provider protocol selection is invalid")

    hostname, is_ip = _normalize_safe_hostname(parsed.hostname)
    decoded_path = unquote(parsed.path)
    if _SECRET_LIKE.search(decoded_path):
        raise ValueError("manual provider protocol selection is invalid")
    if policy.family in {ManualProviderProtocolFamily.FTP, ManualProviderProtocolFamily.FTPS}:
        _validate_ftp_path(decoded_path)

    netloc = f"[{hostname}]" if is_ip and ":" in hostname else hostname
    path = parsed.path.rstrip("/")
    path = _PERCENT_ESCAPE.sub(lambda match: f"%{match.group(1).upper()}", path)
    return urlunsplit((scheme, netloc, path, "", ""))


def _normalize_safe_hostname(value: str) -> tuple[str, bool]:
    raw = value.rstrip(".").casefold()
    if not raw or raw == "localhost" or raw.endswith(".localhost"):
        raise ValueError("manual provider protocol selection is invalid")
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        if _AMBIGUOUS_NUMERIC_HOST.fullmatch(raw):
            raise ValueError("manual provider protocol selection is invalid") from None
        try:
            hostname = raw.encode("idna").decode("ascii").casefold()
        except UnicodeError:
            raise ValueError("manual provider protocol selection is invalid") from None
        labels = hostname.split(".")
        if (
            len(hostname) > 253
            or len(labels) < 2
            or any(not _HOST_LABEL.fullmatch(label) for label in labels)
        ):
            raise ValueError("manual provider protocol selection is invalid")
        return hostname, False
    if not address.is_global:
        raise ValueError("manual provider protocol selection is invalid")
    return address.compressed.casefold(), True


def _validate_ftp_path(path: str) -> None:
    if _UNSAFE_FTP_PATH.search(path):
        raise ValueError("manual provider protocol selection is invalid")
    if any(segment in {".", ".."} for segment in path.split("/")):
        raise ValueError("manual provider protocol selection is invalid")


def _forbidden_character(character: str) -> bool:
    return unicodedata.category(character) in {"Cc", "Cf", "Cs"}


def _validate_aware_timestamp(value: object) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("manual provider protocol selection timestamp is invalid")


__all__ = [
    "ManualProviderAuthenticationKind",
    "ManualProviderPayloadFormat",
    "ManualProviderProtocolDraft",
    "ManualProviderProtocolCommandResult",
    "ManualProviderProtocolCommandStatus",
    "ManualProviderProtocolErrorCategory",
    "ManualProviderProtocolFamily",
    "ManualProviderProtocolPolicy",
    "ManualProviderProtocolReadiness",
    "ManualProviderProtocolSelection",
    "ManualProviderTlsPolicy",
    "create_manual_provider_protocol_selection",
    "manual_provider_protocol_policies",
    "manual_provider_protocol_policy",
    "normalize_manual_protocol_endpoint",
]
