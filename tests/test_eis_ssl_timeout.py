"""Tests for clear EIS SSL-timeout diagnostics."""

from __future__ import annotations

import pytest

from app.tenders.http_client import HttpTransportError
from app.tenders.provider_base import (
    TenderProviderError,
    TenderSearchQuery,
)
from app.tenders.providers.eis import (
    EisProviderConfig,
    EisTenderProvider,
)


class TimeoutTransport:
    def get(
        self,
        url,
        *,
        headers=None,
        timeout_seconds=20.0,
    ):
        del url, headers, timeout_seconds
        raise HttpTransportError(
            "HTTP request failed after 3 attempts: "
            "SSL handshake timed out",
            attempts=3,
            transient=True,
        )


def test_eis_provider_renders_ssl_timeout_in_russian() -> None:
    provider = EisTenderProvider(
        transport=TimeoutTransport(),
    )

    with pytest.raises(TenderProviderError) as captured:
        provider.search(
            TenderSearchQuery(
                keywords=("видеонаблюдение",)
            )
        )

    message = str(captured.value)
    assert "SSL-рукопожатие" in message
    assert "3 попыток" in message


def test_default_eis_config_has_bounded_retries() -> None:
    config = EisProviderConfig()

    assert config.timeout_seconds == 10.0
    assert config.retry_attempts == 3
    assert config.max_attempt_timeout_seconds == 25.0
