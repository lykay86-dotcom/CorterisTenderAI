"""RM-133 no-secret, no-execution and tamper-resistant registration guards."""

from __future__ import annotations

import asyncio
import json
import logging
import socket

import pytest

from app.tenders.collector.manual_provider_registration import (
    ManualProviderCommandStatus,
    ManualProviderDraft,
    ManualProviderExecutionError,
)
from app.tenders.collector.provider_control import CollectorProviderManager
from app.tenders.collector.provider_settings import ProviderEnablementRepository
from app.tenders.collector.run_session import CollectorRunSession
from app.tenders.provider_base import TenderSearchQuery


SECRET = "RM133_SECRET_SENTINEL_7f8739"
CRLF = "RM133_CRLF_SENTINEL_944c2a"


class _CredentialTripwire:
    def __getattr__(self, name: str):
        raise AssertionError(f"credential service must not be used: {name}")


def test_rejected_secret_url_is_not_persisted_logged_or_returned(tmp_path, caplog) -> None:
    manager = CollectorProviderManager(
        tmp_path,
        credential_service=_CredentialTripwire(),
        manual_provider_id_factory=lambda: f"manual_{'d' * 32}",
    )
    caplog.set_level(logging.DEBUG)

    result = manager.register_manual_provider(
        ManualProviderDraft.unvalidated(
            display_name="Площадка",
            homepage_url=f"https://user:{SECRET}@example.test/path?token={CRLF}",
            endpoint_url="",
        )
    )

    rendered = "\n".join((repr(result), result.message, caplog.text))
    assert result.status is ManualProviderCommandStatus.INVALID_INPUT
    assert SECRET not in rendered
    assert CRLF not in rendered
    assert not (tmp_path / "collector_provider_settings.json").exists()


def test_registration_and_snapshot_perform_zero_network_or_dns(tmp_path, monkeypatch) -> None:
    def fail_dns(*_args, **_kwargs):
        raise AssertionError("DNS must not run")

    monkeypatch.setattr(socket, "getaddrinfo", fail_dns)
    manager = CollectorProviderManager(
        tmp_path,
        credential_service=_CredentialTripwire(),
        manual_provider_id_factory=lambda: f"manual_{'e' * 32}",
    )

    result = manager.register_manual_provider(
        ManualProviderDraft(
            "Локальная metadata",
            "http://127.0.0.1",
            "http://169.254.169.254/metadata",
        )
    )

    assert result.status is ManualProviderCommandStatus.CREATED
    assert manager.settings_snapshot().get(result.provider_id).enabled is False


def test_enabled_true_json_tampering_does_not_make_manual_registration_runnable(tmp_path) -> None:
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: f"manual_{'f' * 32}",
    )
    created = manager.register_manual_provider(
        ManualProviderDraft("Площадка", "https://example.test")
    )
    path = tmp_path / "collector_provider_settings.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["providers"][created.provider_id] = True
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    repository = ProviderEnablementRepository(path)
    snapshot = manager.settings_snapshot()

    assert repository.load_result().get(created.provider_id).enabled is True
    assert snapshot.get(created.provider_id).enabled is False
    assert created.provider_id not in snapshot.enabled_provider_ids

    calls: list[str] = []
    session = CollectorRunSession(
        tmp_path,
        runtime_factory=lambda: calls.append("runtime"),  # type: ignore[arg-type]
        provider_settings_snapshot_factory=manager.settings_snapshot,
    )
    with pytest.raises(ManualProviderExecutionError):
        asyncio.run(session.run(TenderSearchQuery(), provider_ids=(created.provider_id,)))
    assert calls == []


def test_manual_metadata_is_not_exposed_by_public_settings_payload(tmp_path) -> None:
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: f"manual_{'1' * 32}",
    )
    created = manager.register_manual_provider(
        ManualProviderDraft(
            "Private endpoint",
            "https://example.test",
            "http://10.0.0.5/private",
        )
    )

    rendered = json.dumps(manager.settings_snapshot().public_payload(), ensure_ascii=False)

    assert created.provider_id in rendered
    assert "10.0.0.5" not in rendered
    assert "private" not in rendered.casefold()
