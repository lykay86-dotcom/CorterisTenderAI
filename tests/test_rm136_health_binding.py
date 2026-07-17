"""RM-136 exact revision-aware health binding."""

from app.tenders.collector.manual_provider_health import build_health_check_binding


MANUAL_ID = f"manual_{'2' * 32}"


def test_binding_is_deterministic_and_changes_with_every_runtime_contract() -> None:
    values = dict(
        provider_id=MANUAL_ID,
        protocol_payload={"family": "api", "endpoint_url": "https://source.example.test/v1"},
        adapter_spec_version=1,
        adapter_revision=3,
        adapter_fingerprint="a" * 64,
        credential_marker="b" * 64,
    )
    baseline = build_health_check_binding(**values)
    assert baseline == build_health_check_binding(**values)
    assert "source.example.test" not in repr(baseline)

    for field, changed in (
        ("protocol_payload", {"family": "api", "endpoint_url": "https://other.example.test/v1"}),
        ("adapter_revision", 4),
        ("adapter_fingerprint", "c" * 64),
        ("credential_marker", "d" * 64),
    ):
        candidate = dict(values)
        candidate[field] = changed
        assert build_health_check_binding(**candidate) != baseline


def test_binding_contains_code_owned_policy_versions() -> None:
    binding = build_health_check_binding(
        provider_id=MANUAL_ID,
        protocol_payload={"family": "rss", "endpoint_url": "https://feed.example.test/rss"},
        adapter_spec_version=1,
        adapter_revision=1,
        adapter_fingerprint="e" * 64,
        credential_marker="none",
    )
    assert binding.target_policy_version == "manual-target-policy-v1"
    assert binding.transport_policy_version == "manual-probe-transport-v1"
    assert binding.contract_version == 1
