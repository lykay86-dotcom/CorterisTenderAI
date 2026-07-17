"""RM-134 typed, inert and security-bounded protocol-selection contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.tenders.collector.manual_provider_protocol import (
    ManualProviderAuthenticationKind,
    ManualProviderPayloadFormat,
    ManualProviderProtocolDraft,
    ManualProviderProtocolFamily,
    ManualProviderTlsPolicy,
    create_manual_provider_protocol_selection,
    manual_provider_protocol_policies,
)


NOW = datetime(2026, 7, 17, 11, 0, tzinfo=timezone.utc)


def _draft(**changes: object) -> ManualProviderProtocolDraft:
    values: dict[str, object] = {
        "family": ManualProviderProtocolFamily.API,
        "endpoint_url": "HTTPS://API.Example.TEST:443/v1/",
        "payload_format": ManualProviderPayloadFormat.JSON,
        "authentication_kind": ManualProviderAuthenticationKind.NONE,
    }
    values.update(changes)
    return ManualProviderProtocolDraft(**values)


def test_policy_registry_is_closed_complete_and_non_executable() -> None:
    policies = manual_provider_protocol_policies()

    assert tuple(item.family for item in policies) == (
        ManualProviderProtocolFamily.API,
        ManualProviderProtocolFamily.RSS,
        ManualProviderProtocolFamily.FTP,
        ManualProviderProtocolFamily.FTPS,
    )
    assert policies[0].tls_policy is ManualProviderTlsPolicy.REQUIRED
    assert policies[2].tls_policy is ManualProviderTlsPolicy.PLAINTEXT_WARNING
    assert policies[3].tls_policy is ManualProviderTlsPolicy.REQUIRED
    assert not any(hasattr(item, name) for item in policies for name in ("run", "connect", "parse"))


@pytest.mark.parametrize(
    ("family", "endpoint", "payload", "authentication"),
    (
        ("api", "https://api.example.test/v1", "json", "api_key"),
        ("rss", "https://feeds.example.test/tenders.xml", "atom", "none"),
        ("ftp", "ftp://files.example.test/tenders", None, "username_password"),
        ("ftps", "ftps://files.example.test/tenders", None, "username_password"),
    ),
)
def test_allowed_family_combinations_are_normalized(
    family: str,
    endpoint: str,
    payload: str | None,
    authentication: str,
) -> None:
    draft = ManualProviderProtocolDraft(
        family=ManualProviderProtocolFamily(family),
        endpoint_url=endpoint,
        payload_format=(ManualProviderPayloadFormat(payload) if payload else None),
        authentication_kind=ManualProviderAuthenticationKind(authentication),
    )
    selection = create_manual_provider_protocol_selection(draft, timestamp=NOW)

    assert selection.family.value == family
    assert selection.endpoint_url == endpoint
    assert selection.selected_at == NOW
    assert selection.updated_at == NOW
    assert "endpoint_url" not in selection.public_payload()
    assert endpoint not in repr(selection)
    with pytest.raises(FrozenInstanceError):
        selection.endpoint_url = "https://other.test"  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    (
        {"endpoint_url": "http://api.example.test/v1"},
        {"endpoint_url": "https://user:password@api.example.test/v1"},
        {"endpoint_url": "https://api.example.test/v1?api_key=secret"},
        {"endpoint_url": "https://api.example.test/v1#fragment"},
        {"endpoint_url": "https://api.example.test/%ZZ"},
        {"endpoint_url": "https://localhost/v1"},
        {"endpoint_url": "https://127.0.0.1/v1"},
        {"endpoint_url": "https://10.0.0.1/v1"},
        {"endpoint_url": "https://169.254.1.2/v1"},
        {"endpoint_url": "https://2130706433/v1"},
        {"endpoint_url": "https://api.example.test:8443/v1"},
        {"endpoint_url": "https://api.example.test/access_token"},
        {"payload_format": ManualProviderPayloadFormat.RSS},
        {"authentication_kind": ManualProviderAuthenticationKind.USERNAME_PASSWORD},
    ),
)
def test_api_rejects_unsafe_or_family_incompatible_values(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="protocol selection") as captured:
        _draft(**changes)
    assert "secret" not in str(captured.value)


@pytest.mark.parametrize(
    "endpoint",
    (
        "https://files.example.test/tenders",
        "ftp://files.example.test/tenders/../private",
        "ftp://files.example.test/tenders\\private",
        "ftp://files.example.test/tenders/*",
        "ftp://files.example.test:2121/tenders",
        "ftp://user@files.example.test/tenders",
    ),
)
def test_ftp_rejects_scheme_path_port_and_userinfo_violations(endpoint: str) -> None:
    with pytest.raises(ValueError, match="protocol selection"):
        ManualProviderProtocolDraft(
            family=ManualProviderProtocolFamily.FTP,
            endpoint_url=endpoint,
            payload_format=None,
            authentication_kind=ManualProviderAuthenticationKind.NONE,
        )


def test_ftps_cannot_downgrade_and_selection_contains_no_secret_slots() -> None:
    with pytest.raises(ValueError, match="protocol selection"):
        ManualProviderProtocolDraft(
            family=ManualProviderProtocolFamily.FTPS,
            endpoint_url="ftp://files.example.test/tenders",
            authentication_kind=ManualProviderAuthenticationKind.USERNAME_PASSWORD,
        )

    selection = create_manual_provider_protocol_selection(
        ManualProviderProtocolDraft(
            family=ManualProviderProtocolFamily.FTPS,
            endpoint_url="ftps://files.example.test/tenders",
            authentication_kind=ManualProviderAuthenticationKind.USERNAME_PASSWORD,
        ),
        timestamp=NOW,
    )
    assert not any(
        hasattr(selection, name)
        for name in ("password", "username", "api_key", "token", "headers", "adapter")
    )
    assert selection.readiness_gaps() == ("adapter_required",)
