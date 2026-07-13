"""Tests for transient HTTP retry handling."""

from __future__ import annotations

from email.message import Message
import ssl
from urllib.error import URLError

import pytest

from app.tenders.http_client import (
    HttpRetryPolicy,
    HttpTransportError,
    UrllibHttpTransport,
)


class FakeResponse:
    def __init__(self, body: bytes = b"ok") -> None:
        self.status = 200
        self.headers = Message()
        self.headers["Content-Type"] = "text/plain; charset=utf-8"
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, limit: int) -> bytes:
        return self._body[:limit]

    def geturl(self) -> str:
        return "https://zakupki.gov.ru/"


def test_transport_retries_ssl_handshake_timeout() -> None:
    timeouts: list[float] = []
    sleeps: list[float] = []

    def opener(request, *, timeout):
        del request
        timeouts.append(timeout)
        if len(timeouts) == 1:
            raise URLError(TimeoutError("_ssl.c:983: The handshake operation timed out"))
        return FakeResponse(b"success")

    transport = UrllibHttpTransport(
        retry_policy=HttpRetryPolicy(
            max_attempts=3,
            backoff_seconds=0.25,
            timeout_multiplier=1.5,
            max_attempt_timeout_seconds=25,
        ),
        opener=opener,
        sleep_fn=sleeps.append,
    )

    response = transport.get(
        "https://zakupki.gov.ru/",
        timeout_seconds=10,
    )

    assert response.body == b"success"
    assert timeouts == [10.0, 15.0]
    assert sleeps == [0.25]


def test_transport_reports_attempt_count_after_retries() -> None:
    calls = 0

    def opener(request, *, timeout):
        nonlocal calls
        del request, timeout
        calls += 1
        raise URLError(TimeoutError("_ssl.c:983: The handshake operation timed out"))

    transport = UrllibHttpTransport(
        retry_policy=HttpRetryPolicy(
            max_attempts=3,
            backoff_seconds=0,
        ),
        opener=opener,
        sleep_fn=lambda _delay: None,
    )

    with pytest.raises(HttpTransportError) as captured:
        transport.get(
            "https://zakupki.gov.ru/",
            timeout_seconds=2,
        )

    assert calls == 3
    assert captured.value.attempts == 3
    assert captured.value.transient
    assert "SSL handshake timed out" in str(captured.value)


def test_certificate_verification_error_is_not_retried() -> None:
    calls = 0

    def opener(request, *, timeout):
        nonlocal calls
        del request, timeout
        calls += 1
        raise URLError(ssl.SSLCertVerificationError("certificate verify failed"))

    transport = UrllibHttpTransport(
        retry_policy=HttpRetryPolicy(
            max_attempts=3,
            backoff_seconds=0,
        ),
        opener=opener,
        sleep_fn=lambda _delay: None,
    )

    with pytest.raises(HttpTransportError) as captured:
        transport.get("https://example.org/")

    assert calls == 1
    assert not captured.value.transient
