"""Small dependency-free HTTP transport for tender providers."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
import errno
import socket
import ssl
from time import sleep
from typing import Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HttpTransportError(RuntimeError):
    """Raised when a provider HTTP request cannot be completed."""

    def __init__(
        self,
        message: str,
        *,
        attempts: int = 1,
        transient: bool = False,
    ) -> None:
        super().__init__(message)
        self.attempts = max(1, int(attempts))
        self.transient = bool(transient)


@dataclass(frozen=True, slots=True)
class HttpRetryPolicy:
    """Retry configuration for transient network failures."""

    max_attempts: int = 1
    backoff_seconds: float = 0.75
    backoff_multiplier: float = 2.0
    timeout_multiplier: float = 1.5
    max_attempt_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least 1")
        if self.timeout_multiplier < 1:
            raise ValueError("timeout_multiplier must be at least 1")
        if self.max_attempt_timeout_seconds <= 0:
            raise ValueError("max_attempt_timeout_seconds must be positive")


@dataclass(frozen=True, slots=True)
class HttpResponse:
    url: str
    status_code: int
    headers: Mapping[str, str]
    body: bytes

    def text(self, *, default_charset: str = "utf-8") -> str:
        content_type = self.headers.get("content-type", "")
        charset = _charset_from_content_type(content_type)
        candidates = (charset, default_charset, "windows-1251")
        for candidate in candidates:
            if not candidate:
                continue
            try:
                return self.body.decode(candidate)
            except (LookupError, UnicodeDecodeError):
                continue
        return self.body.decode(
            default_charset,
            errors="replace",
        )


class HttpTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 20.0,
    ) -> HttpResponse: ...


class UrllibHttpTransport:
    """Production transport based only on the Python standard library.

    Retries are disabled by default. Providers that need them must pass an
    explicit ``HttpRetryPolicy``. TLS certificate verification always remains
    enabled; this transport never falls back to an insecure SSL context.
    """

    def __init__(
        self,
        *,
        max_response_bytes: int = 20 * 1024 * 1024,
        retry_policy: HttpRetryPolicy | None = None,
        opener: Callable[..., object] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        if max_response_bytes < 1024:
            raise ValueError("max_response_bytes must be at least 1024")
        self.max_response_bytes = int(max_response_bytes)
        self.retry_policy = retry_policy or HttpRetryPolicy()
        self._opener = opener or urlopen
        self._sleep = sleep_fn or sleep

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 20.0,
    ) -> HttpResponse:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        request = Request(
            url,
            method="GET",
            headers=dict(headers or {}),
        )
        last_error: BaseException | None = None

        for attempt in range(
            1,
            self.retry_policy.max_attempts + 1,
        ):
            attempt_timeout = min(
                float(timeout_seconds) * (self.retry_policy.timeout_multiplier ** (attempt - 1)),
                max(
                    float(timeout_seconds),
                    self.retry_policy.max_attempt_timeout_seconds,
                ),
            )
            try:
                return self._get_once(
                    request,
                    timeout_seconds=attempt_timeout,
                )
            except HTTPError as exc:
                return self._http_error_response(exc)
            except HttpTransportError:
                raise
            except (
                URLError,
                TimeoutError,
                socket.timeout,
                ssl.SSLError,
                OSError,
            ) as exc:
                last_error = exc
                transient = _is_transient_network_error(exc)
                if not transient or attempt >= self.retry_policy.max_attempts:
                    root = _root_network_error(exc)
                    raise HttpTransportError(
                        _network_error_message(
                            root,
                            attempts=attempt,
                        ),
                        attempts=attempt,
                        transient=transient,
                    ) from exc

                delay = self.retry_policy.backoff_seconds * (
                    self.retry_policy.backoff_multiplier ** (attempt - 1)
                )
                if delay > 0:
                    self._sleep(delay)

        # Defensive fallback; the loop always returns or raises.
        root = _root_network_error(last_error or RuntimeError("unknown network error"))
        raise HttpTransportError(
            _network_error_message(
                root,
                attempts=self.retry_policy.max_attempts,
            ),
            attempts=self.retry_policy.max_attempts,
            transient=True,
        )

    def _get_once(
        self,
        request: Request,
        *,
        timeout_seconds: float,
    ) -> HttpResponse:
        with self._opener(
            request,
            timeout=timeout_seconds,
        ) as response:
            body = response.read(self.max_response_bytes + 1)
            if len(body) > self.max_response_bytes:
                raise HttpTransportError("HTTP response exceeds the configured size limit")
            return HttpResponse(
                url=response.geturl(),
                status_code=int(response.status),
                headers=_headers_to_dict(response.headers),
                body=body,
            )

    def _http_error_response(
        self,
        exc: HTTPError,
    ) -> HttpResponse:
        try:
            body = exc.read(self.max_response_bytes)
        except OSError:
            body = b""
        return HttpResponse(
            url=exc.geturl(),
            status_code=int(exc.code),
            headers=_headers_to_dict(exc.headers),
            body=body,
        )


def _root_network_error(
    error: BaseException,
) -> BaseException:
    current = error
    visited: set[int] = set()
    while isinstance(current, URLError):
        identity = id(current)
        if identity in visited:
            break
        visited.add(identity)
        reason = current.reason
        if not isinstance(reason, BaseException):
            break
        current = reason
    return current


def _is_transient_network_error(
    error: BaseException,
) -> bool:
    root = _root_network_error(error)

    if isinstance(root, ssl.SSLCertVerificationError):
        return False

    if isinstance(
        root,
        (
            TimeoutError,
            socket.timeout,
            ConnectionResetError,
            ConnectionAbortedError,
            BrokenPipeError,
        ),
    ):
        return True

    if isinstance(root, ssl.SSLError):
        message = str(root).casefold()
        return not any(
            marker in message
            for marker in (
                "certificate verify failed",
                "hostname mismatch",
                "unknown ca",
            )
        )

    if isinstance(root, OSError):
        if root.errno in {
            errno.ETIMEDOUT,
            errno.ECONNRESET,
            errno.ECONNABORTED,
            errno.EHOSTUNREACH,
            errno.ENETUNREACH,
            errno.ENETDOWN,
            errno.EPIPE,
        }:
            return True

        message = str(root).casefold()
        return any(
            marker in message
            for marker in (
                "timed out",
                "timeout",
                "temporarily unavailable",
                "connection reset",
                "connection aborted",
                "handshake operation timed out",
            )
        )

    return False


def _network_error_message(
    error: BaseException,
    *,
    attempts: int,
) -> str:
    detail = str(error).strip() or type(error).__name__
    folded = detail.casefold()
    if "handshake operation timed out" in folded:
        reason = "SSL handshake timed out"
    elif "timed out" in folded or "timeout" in folded:
        reason = "connection timed out"
    elif isinstance(error, ssl.SSLCertVerificationError):
        reason = "TLS certificate verification failed"
    else:
        reason = detail

    suffix = "attempt" if attempts == 1 else "attempts"
    return f"HTTP request failed after {attempts} {suffix}: {reason}"


def _headers_to_dict(
    headers: Message | None,
) -> dict[str, str]:
    if headers is None:
        return {}
    return {str(key).casefold(): str(value) for key, value in headers.items()}


def _charset_from_content_type(value: str) -> str:
    for part in value.split(";")[1:]:
        key, separator, raw = part.strip().partition("=")
        if separator and key.casefold() == "charset":
            return raw.strip().strip('"')
    return ""


__all__ = [
    "HttpResponse",
    "HttpRetryPolicy",
    "HttpTransport",
    "HttpTransportError",
    "UrllibHttpTransport",
]
