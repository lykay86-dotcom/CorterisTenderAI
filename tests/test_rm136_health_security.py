"""RM-136 source and serialization security tripwires."""

from dataclasses import asdict
from pathlib import Path

from app.tenders.collector.manual_provider_health import HealthCheckBinding


ROOT = Path(__file__).resolve().parents[1]


def test_health_modules_do_not_import_legacy_tester_or_keyring() -> None:
    health = (ROOT / "app/tenders/collector/manual_provider_health.py").read_text(encoding="utf-8")
    transport = (ROOT / "app/tenders/collector/manual_probe_transport.py").read_text(
        encoding="utf-8"
    )
    source = f"{health}\n{transport}".casefold()
    assert "manualconnectortester" not in source
    assert "app.connectors.manual" not in source
    assert "import keyring" not in source


def test_binding_serialization_contains_no_endpoint_or_secret_value() -> None:
    sentinel = "RM136_SECRET_SENTINEL"
    binding = HealthCheckBinding(
        f"manual_{'7' * 32}", "a" * 64, 1, 1, "b" * 64, "credential-marker"
    )
    assert sentinel not in repr(asdict(binding))
    assert "endpoint" not in repr(asdict(binding)).casefold()
