"""RM-136 legacy schema and startup no-I/O handoff."""

from datetime import datetime, timezone
import json

from app.tenders.collector.manual_provider_protocol import ManualProviderFtpsMode
from app.tenders.collector.provider_settings import (
    ProviderEnablementRepository,
    ProviderSettingsLoadStatus,
)


MANUAL_ID = f"manual_{'8' * 32}"


def test_v5_ftps_migrates_in_memory_to_implicit_and_first_write_backs_up(tmp_path) -> None:
    path = tmp_path / "collector_provider_settings.json"
    timestamp = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc).isoformat()
    payload = {
        "schema_version": 5,
        "updated_at": timestamp,
        "providers": {},
        "configuration": {},
        "manual_registrations": {
            MANUAL_ID: {
                "display_name": "FTPS",
                "homepage_url": "https://example.test",
                "endpoint_url": "",
                "lifecycle_state": "adapter_required",
                "protocol_selection": {
                    "family": "ftps",
                    "endpoint_url": "ftps://source.example.test/incoming",
                    "payload_format": None,
                    "authentication_kind": "username_password",
                    "tls_policy": "required",
                    "selected_at": timestamp,
                    "updated_at": timestamp,
                },
                "adapter_spec": None,
                "adapter_spec_history": [],
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        },
    }
    original = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    path.write_bytes(original)
    repository = ProviderEnablementRepository(path)

    loaded = repository.load_result()
    selection = loaded.manual_registrations[0].protocol_selection
    assert loaded.status is ProviderSettingsLoadStatus.MIGRATED_V5
    assert selection is not None and selection.ftps_mode is ManualProviderFtpsMode.IMPLICIT
    assert path.read_bytes() == original

    repository.set_enabled("eis", False)
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 7
    backups = tuple(tmp_path.glob("collector_provider_settings.json.v5-*.bak"))
    assert len(backups) == 1 and backups[0].read_bytes() == original
