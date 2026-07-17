"""RM-136 SSRF and DNS policy contract."""

import pytest

from app.tenders.collector.manual_probe_transport import (
    ManualProbeTargetPolicy,
    ManualTargetPolicyError,
)
from app.tenders.collector.manual_provider_protocol import ManualProviderProtocolFamily


def test_https_target_accepts_only_global_all_answer_dns() -> None:
    policy = ManualProbeTargetPolicy()
    target = policy.validate_endpoint(
        "https://source.example.test/feed", ManualProviderProtocolFamily.RSS
    )
    resolved = policy.validate_resolved_addresses(target, ("93.184.216.34", "2606:2800:220:1::"))

    assert resolved.port == 443
    assert len(resolved.addresses) == 2
    assert "source.example.test" not in repr(resolved)


@pytest.mark.parametrize(
    "endpoint,addresses",
    (
        ("https://127.0.0.1/feed", ("127.0.0.1",)),
        ("https://source.example.test/feed", ("93.184.216.34", "10.0.0.1")),
        ("https://169.254.169.254/latest/meta-data", ("169.254.169.254",)),
        ("https://[::ffff:127.0.0.1]/feed", ("::ffff:127.0.0.1",)),
    ),
)
def test_private_metadata_and_mixed_answers_fail_closed(endpoint, addresses) -> None:
    policy = ManualProbeTargetPolicy()
    with pytest.raises(ManualTargetPolicyError):
        target = policy.validate_endpoint(endpoint, ManualProviderProtocolFamily.RSS)
        policy.validate_resolved_addresses(target, addresses)


def test_userinfo_control_characters_and_unsafe_ports_are_rejected() -> None:
    policy = ManualProbeTargetPolicy()
    for endpoint in (
        "https://user:pass@source.example.test/feed",
        "https://source.example.test:8080/feed",
        "https://source.example.test/feed%0d%0aInjected",
    ):
        with pytest.raises(ManualTargetPolicyError):
            policy.validate_endpoint(endpoint, ManualProviderProtocolFamily.RSS)
