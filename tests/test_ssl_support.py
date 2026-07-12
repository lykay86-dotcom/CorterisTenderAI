"""Tests for verified TLS context construction."""

from __future__ import annotations

from pathlib import Path
import ssl

import certifi
import pytest

from app.core.ssl_support import build_ssl_context, describe_ssl_context


def test_default_context_keeps_verification_enabled() -> None:
    context = build_ssl_context(environment={})
    info = describe_ssl_context(context)

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    assert info.verification_enabled
    assert info.ca_certificates > 0


def test_explicit_ca_bundle_is_accepted() -> None:
    context = build_ssl_context(
        Path(certifi.where()),
        environment={},
    )
    info = describe_ssl_context(
        context,
        explicit_ca_bundle=certifi.where(),
    )

    assert info.verification_enabled
    assert info.explicit_ca_bundle.endswith("cacert.pem")


def test_missing_ca_bundle_fails_closed(tmp_path) -> None:
    missing = tmp_path / "missing.pem"

    with pytest.raises(FileNotFoundError):
        build_ssl_context(missing, environment={})
