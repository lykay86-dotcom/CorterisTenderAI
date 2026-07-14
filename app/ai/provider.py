from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from http.client import HTTPMessage
import json
import socket
import ssl
from typing import Any
import urllib.error
import urllib.request


DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_RAW_RESPONSE_ID_LENGTH = 200
MAX_INPUT_CHARACTERS = 500_000


class AIProvider(ABC):
    @abstractmethod
    def analyze(self, prompt: str, documents: list[str]) -> dict[str, object]: ...


class DisabledProvider(AIProvider):
    def analyze(self, prompt: str, documents: list[str]) -> dict[str, object]:
        return {
            "status": "disabled",
            "message": "ИИ-провайдер не настроен. Использован локальный анализ правил.",
        }


class _RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep Authorization on the original request by refusing every redirect."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> None:
        return None


def _open_without_redirects(request: urllib.request.Request, *, timeout: float) -> object:
    opener = urllib.request.build_opener(_RejectRedirectHandler())
    return opener.open(request, timeout=timeout)


class OpenAICompatibleProvider(AIProvider):
    """Synchronous, bounded Responses API adapter with sanitized failures."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 120,
        *,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        store_response: bool | None = False,
        opener: Callable[..., object] | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = float(timeout)
        self.max_response_bytes = int(max_response_bytes)
        self.store_response = store_response
        self._opener = opener

    def __repr__(self) -> str:
        return "OpenAICompatibleProvider(<configuration redacted>)"

    def analyze(self, prompt: str, documents: list[str]) -> dict[str, object]:
        if not self.api_key.strip() or any(
            ord(char) < 32 or ord(char) == 127 for char in self.api_key
        ):
            return _error("authentication_error")
        source = "\n\n--- ДОКУМЕНТ ---\n".join(documents)
        payload: dict[str, object] = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": prompt}]},
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": source[:MAX_INPUT_CHARACTERS]}],
                },
            ],
            "stream": False,
        }
        if self.store_response is not None:
            payload["store"] = self.store_response
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/responses",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        opener = self._opener or _open_without_redirects
        try:
            response_context = opener(request, timeout=self.timeout)
            with response_context as response:  # type: ignore[attr-defined]
                raw = response.read(self.max_response_bytes + 1)
        except urllib.error.HTTPError as exc:
            return _http_error(int(exc.code))
        except (TimeoutError, socket.timeout):
            return _error("timeout", retryable=True)
        except urllib.error.URLError as exc:
            return _url_error(exc)
        except ssl.SSLError:
            return _error("tls_error")
        except OSError:
            return _error("network_error")
        except Exception:
            return _error("network_error")

        if not isinstance(raw, bytes):
            return _error("invalid_response")
        if len(raw) > self.max_response_bytes:
            return _error("response_too_large")
        try:
            decoded = raw.decode("utf-8")
            parsed = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _error("invalid_json")
        if not isinstance(parsed, Mapping):
            return _error("invalid_response")
        return _parse_response(parsed)


_ERROR_MESSAGES = {
    "authentication_error": "AI provider authentication failed.",
    "permission_error": "AI provider permission denied.",
    "invalid_request": "AI provider rejected the request.",
    "endpoint_not_supported": "AI provider endpoint is not supported.",
    "request_too_large": "AI provider request is too large.",
    "rate_limited": "AI provider rate limit was reached.",
    "provider_unavailable": "AI provider is temporarily unavailable.",
    "timeout": "AI provider request timed out.",
    "network_error": "AI provider network request failed.",
    "tls_error": "AI provider TLS verification failed.",
    "redirect_rejected": "AI provider redirect was rejected.",
    "response_too_large": "AI provider response is too large.",
    "invalid_json": "AI provider returned invalid JSON.",
    "invalid_response": "AI provider returned an invalid response.",
    "incomplete_response": "AI provider response is incomplete.",
    "refused": "AI provider refused the request.",
    "empty_output": "AI provider returned no output.",
}


def _error(error_code: str, *, retryable: bool = False) -> dict[str, object]:
    return {
        "status": "error",
        "error_code": error_code,
        "message": _ERROR_MESSAGES[error_code],
        "retryable": retryable,
    }


def _http_error(status_code: int) -> dict[str, object]:
    if 300 <= status_code < 400:
        return _error("redirect_rejected")
    mapping = {
        400: ("invalid_request", False),
        401: ("authentication_error", False),
        403: ("permission_error", False),
        404: ("endpoint_not_supported", False),
        408: ("timeout", True),
        413: ("request_too_large", False),
        422: ("invalid_request", False),
        429: ("rate_limited", True),
    }
    if status_code in mapping:
        code, retryable = mapping[status_code]
        return _error(code, retryable=retryable)
    if 500 <= status_code <= 599:
        return _error("provider_unavailable", retryable=True)
    if 400 <= status_code <= 499:
        return _error("invalid_request")
    return _error("provider_unavailable")


def _url_error(exc: urllib.error.URLError) -> dict[str, object]:
    reason = exc.reason
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return _error("timeout", retryable=True)
    if isinstance(reason, ssl.SSLError):
        return _error("tls_error")
    return _error("network_error")


def _parse_response(payload: Mapping[str, object]) -> dict[str, object]:
    if payload.get("error") is not None:
        return _error("provider_unavailable")

    status = payload.get("status")
    if status is not None:
        if status == "failed":
            return _error("provider_unavailable")
        if status in {"incomplete", "in_progress", "cancelled", "queued"}:
            return _error("incomplete_response")
        if status != "completed":
            return _error("invalid_response")

    text_parts: list[str] = []
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, Mapping) or part.get("type") != "output_text":
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text)

    rendered = "\n".join(text_parts).strip()
    if not rendered:
        fallback = payload.get("output_text")
        if isinstance(fallback, str):
            rendered = fallback.strip()
    if not rendered:
        if _contains_refusal(payload):
            return _error("refused")
        return _error("empty_output")

    return {
        "status": "ok",
        "text": rendered,
        "raw_id": _safe_response_id(payload.get("id")),
    }


def _contains_refusal(payload: Mapping[str, object]) -> bool:
    if payload.get("refusal") is not None:
        return True
    output = payload.get("output")
    if not isinstance(output, list):
        return False
    for item in output:
        if not isinstance(item, Mapping):
            continue
        if item.get("type") == "refusal" or item.get("refusal") is not None:
            return True
        content = item.get("content")
        if isinstance(content, list) and any(
            isinstance(part, Mapping)
            and (part.get("type") == "refusal" or part.get("refusal") is not None)
            for part in content
        ):
            return True
    return False


def _safe_response_id(value: object) -> str:
    if not isinstance(value, str):
        return ""
    rendered = value.strip()
    if any(ord(char) < 32 or ord(char) == 127 for char in rendered):
        return ""
    return rendered[:MAX_RAW_RESPONSE_ID_LENGTH]


__all__ = [
    "AIProvider",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "DisabledProvider",
    "MAX_INPUT_CHARACTERS",
    "MAX_RAW_RESPONSE_ID_LENGTH",
    "OpenAICompatibleProvider",
]
