"""Small dependency-free HTTP transport for tender providers."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from typing import Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HttpTransportError(RuntimeError):
    """Raised when a provider HTTP request cannot be completed."""


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
        return self.body.decode(default_charset, errors="replace")


class HttpTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 20.0,
    ) -> HttpResponse:
        ...


class UrllibHttpTransport:
    """Production transport based only on the Python standard library."""

    def __init__(self, *, max_response_bytes: int = 20 * 1024 * 1024) -> None:
        if max_response_bytes < 1024:
            raise ValueError("max_response_bytes must be at least 1024")
        self.max_response_bytes = int(max_response_bytes)

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 20.0,
    ) -> HttpResponse:
        request = Request(
            url,
            method="GET",
            headers=dict(headers or {}),
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read(self.max_response_bytes + 1)
                if len(body) > self.max_response_bytes:
                    raise HttpTransportError(
                        "HTTP response exceeds the configured size limit"
                    )
                return HttpResponse(
                    url=response.geturl(),
                    status_code=int(response.status),
                    headers=_headers_to_dict(response.headers),
                    body=body,
                )
        except HTTPError as exc:
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
        except (URLError, TimeoutError, OSError) as exc:
            raise HttpTransportError(str(exc)) from exc


def _headers_to_dict(headers: Message | None) -> dict[str, str]:
    if headers is None:
        return {}
    return {
        str(key).casefold(): str(value)
        for key, value in headers.items()
    }


def _charset_from_content_type(value: str) -> str:
    for part in value.split(";")[1:]:
        key, separator, raw = part.strip().partition("=")
        if separator and key.casefold() == "charset":
            return raw.strip().strip('"')
    return ""


__all__ = [
    "HttpResponse",
    "HttpTransport",
    "HttpTransportError",
    "UrllibHttpTransport",
]
