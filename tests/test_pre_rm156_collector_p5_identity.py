"""Strict P5 provider identity, migration, and export contract."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path

import httpx
import pytest

from app.tenders.collector.async_provider_factory import create_default_async_providers
from app.tenders.collector.manual_provider_registration import (
    ManualProviderLifecycle,
    ManualProviderRegistration,
)
from app.tenders.collector.network_runtime import create_collector_network_runtime
from app.tenders.collector.network_settings import default_collector_network_settings
from app.tenders.collector.provider_definitions import (
    canonical_provider_definitions,
    canonical_provider_id,
    provider_aliases,
    resolved_provider_catalog,
    resolve_provider_ids,
)
from app.tenders.collector.provider_settings import (
    ProviderEnablementRepository,
    ProviderSettingsLoadStatus,
)
from app.tenders.collector.schema import COLLECTOR_SCHEMA_VERSION
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.models import TenderSource
from app.tenders.provider_credentials import provider_credential_descriptors
from app.tenders.provider_factory import create_default_provider_registry
from app.tenders.providers.commercial_catalog import (
    CommercialProviderSettingsRepository,
    default_commercial_provider_definitions,
)
from app.tenders.providers.eis import EisTenderProvider
from app.tenders.providers.placeholders import PlaceholderTenderProvider


EXPECTED_IDS = (
    "eis",
    "mos_supplier",
    "zakaz_rf",
    "roseltorg",
    "rad",
    "tek_torg",
    "ets_nep",
    "sber_a",
    "rts_tender",
    "gazprombank",
    "b2b_center",
    "fabrikant",
    "otc",
)
EXPECTED_ALIASES = {
    "sber_commercial": "sber_a",
    "rts_commercial": "rts_tender",
    "roseltorg_commercial": "roseltorg",
}


class _NoNetworkTransport:
    def get(self, *_args, **_kwargs):
        raise AssertionError("P5 identity construction must not perform network I/O")


def test_p5_catalog_has_exact_thirteen_unique_identities_and_sources() -> None:
    definitions = canonical_provider_definitions()

    assert tuple(item.id for item in definitions) == EXPECTED_IDS
    assert tuple(item.value for item in TenderSource if item.value in EXPECTED_IDS) == EXPECTED_IDS
    assert len({item.id for item in definitions}) == len(EXPECTED_IDS)
    assert len({item.source for item in definitions}) == len(EXPECTED_IDS)
    assert (
        tuple(item.provider_id for item in default_commercial_provider_definitions())
        == (EXPECTED_IDS[2:])
    )


def test_p5_legacy_commercial_ids_are_aliases_not_canonical_platforms() -> None:
    assert provider_aliases() == EXPECTED_ALIASES
    for alias, canonical in EXPECTED_ALIASES.items():
        assert canonical_provider_id(alias.upper()) == canonical
        assert canonical_provider_id(canonical) == canonical
    assert resolve_provider_ids(("sber_commercial", "sber_a", "roseltorg_commercial", "eis")) == (
        "sber_a",
        "roseltorg",
        "eis",
    )
    with pytest.raises(KeyError):
        canonical_provider_id("commercial")


def test_p5_async_catalog_projects_all_identities_without_network() -> None:
    async def scenario() -> None:
        raw = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _request: (_ for _ in ()).throw(
                    AssertionError("P5 construction must not perform network I/O")
                )
            )
        )
        runtime = create_collector_network_runtime(client=raw)
        providers = create_default_async_providers(
            runtime,
            include_commercial_catalog=True,
            include_disabled=True,
            environment={},
        )

        assert tuple(item.descriptor.id for item in providers) == EXPECTED_IDS
        by_id = {item.descriptor.id: item.descriptor for item in providers}
        for provider_id in ("zakaz_rf", "rad", "ets_nep"):
            assert by_id[provider_id].enabled_by_default is False
            assert by_id[provider_id].implementation_status == "commercial_access_pending"
        await raw.aclose()

    asyncio.run(scenario())


def test_p5_legacy_sync_registry_is_a_canonical_inert_projection() -> None:
    registry = create_default_provider_registry(http_transport=_NoNetworkTransport())

    assert tuple(item.id for item in registry.list_registered()) == EXPECTED_IDS
    assert isinstance(registry.get("eis"), EisTenderProvider)
    for provider_id in EXPECTED_IDS[1:]:
        assert isinstance(registry.get(provider_id), PlaceholderTenderProvider)
        assert registry.is_enabled(provider_id) is False


def test_p5_manual_catalog_rejects_new_builtin_name_collision() -> None:
    now = datetime(2026, 7, 22, 18, 0, tzinfo=timezone.utc)
    registration = ManualProviderRegistration(
        provider_id=f"manual_{'a' * 32}",
        display_name="  росэлторг рад  ",
        homepage_url="https://manual.example.test",
        endpoint_url="https://manual.example.test/api",
        lifecycle_state=ManualProviderLifecycle.PROTOCOL_REQUIRED,
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(ValueError, match="manual provider conflict"):
        resolved_provider_catalog((registration,))


def test_p5_schema6_settings_migrate_to_schema7_with_canonical_priority(
    tmp_path: Path,
) -> None:
    path = tmp_path / "collector_provider_settings.json"
    original = json.dumps(
        {
            "schema_version": 6,
            "updated_at": "2026-07-22T18:00:00+00:00",
            "providers": {
                "sber_commercial": False,
                "sber_a": True,
                "rad": False,
            },
            "configuration": {},
            "manual_registrations": {},
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    path.write_bytes(original)
    repository = ProviderEnablementRepository(path)

    migrated = repository.load_result()

    assert ProviderEnablementRepository.SCHEMA_VERSION == 7
    assert migrated.status is ProviderSettingsLoadStatus.MIGRATED_V6
    assert migrated.get("sber_a").enabled is True
    assert any("sber_commercial" in item for item in migrated.warnings)

    repository.set_enabled("rad", True)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 7
    assert payload["providers"]["sber_a"] is True
    assert "sber_commercial" not in payload["providers"]
    backups = tuple(tmp_path.glob("collector_provider_settings.json.v6-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == original
    assert repository.load_result().status is ProviderSettingsLoadStatus.CURRENT


def test_p5_legacy_commercial_settings_are_read_as_canonical_ids(tmp_path: Path) -> None:
    path = tmp_path / "commercial_provider_settings.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "providers": {
                    "sber_commercial": {
                        "enabled": True,
                        "access_confirmed": False,
                        "api_base_url": "",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    settings = CommercialProviderSettingsRepository(path).load()

    assert tuple(settings) == ("sber_a",)
    assert settings["sber_a"].enabled is True


def test_p5_schema15_db_migrates_alias_registry_without_rewriting_history(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tender_registry.sqlite3"
    seed = CollectorStateRepository(database)
    seed.initialize()
    with seed._connect() as connection:
        connection.execute("DROP TABLE IF EXISTS collector_provider_identity_aliases")
        connection.execute(
            "UPDATE tender_registry_meta SET value='15' WHERE key='collector_schema_version'"
        )
        connection.execute(
            """
            INSERT INTO collector_runs(
                run_id, status, started_at, completed_at, query_json,
                requested_provider_ids_json
            ) VALUES('legacy-run', 'completed', '2026-07-22T18:00:00+00:00',
                     '2026-07-22T18:01:00+00:00', '{}',
                     '["sber_commercial","legacy_unknown"]')
            """
        )
        connection.executemany(
            """
            INSERT INTO collector_run_providers(run_id, provider_id, status)
            VALUES('legacy-run', ?, 'success')
            """,
            (("sber_commercial",), ("legacy_unknown",)),
        )
        connection.commit()

    repository = CollectorStateRepository(database)
    repository.initialize()

    assert COLLECTOR_SCHEMA_VERSION == 16
    with repository._connect() as connection:
        version = connection.execute(
            "SELECT value FROM tender_registry_meta WHERE key='collector_schema_version'"
        ).fetchone()[0]
        aliases = connection.execute(
            "SELECT alias_id, canonical_id FROM collector_provider_identity_aliases "
            "ORDER BY alias_id"
        ).fetchall()
        raw_ids = connection.execute(
            "SELECT provider_id FROM collector_run_providers ORDER BY provider_id"
        ).fetchall()
    assert version == "16"
    assert tuple((row[0], row[1]) for row in aliases) == tuple(sorted(EXPECTED_ALIASES.items()))
    assert tuple(row[0] for row in raw_ids) == ("legacy_unknown", "sber_commercial")
    backups = tuple((tmp_path / "backups").glob("collector-v15-to-v16-*.sqlite3"))
    assert len(backups) == 1

    run = repository.get_run("legacy-run")
    assert run is not None
    assert run.requested_provider_ids == ("sber_a", "legacy_unknown")
    assert tuple(item.provider_id for item in repository.list_provider_outcomes("sber_a")) == (
        "sber_a",
    )
    assert any(item.provider_id == "legacy_unknown" for item in repository.list_provider_outcomes())


def test_p5_network_and_credentials_use_canonical_ids_with_legacy_accounts() -> None:
    network = default_collector_network_settings()
    assert network.get("sber_a").provider_id == "sber_a"
    assert network.get("sber_commercial") is network.get("sber_a")

    descriptors = {item.provider_id: item for item in provider_credential_descriptors()}
    assert tuple(descriptors) == ("mos_supplier", *EXPECTED_IDS[2:])
    assert descriptors["sber_a"].keyring_name == "collector.sber_commercial.api_key"
    assert descriptors["sber_a"].environment_variable == "CORTERIS_SBER_COMMERCIAL_API_KEY"
    assert descriptors["rts_tender"].keyring_name == "collector.rts_commercial.api_key"
    assert descriptors["roseltorg"].keyring_name == "collector.roseltorg_commercial.api_key"
