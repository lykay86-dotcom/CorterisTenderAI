from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.tenders.detail import (
    TenderActionRole,
    TenderActionSpec,
    TenderActionState,
    TenderDetailState,
    TenderIdentity,
    TenderIdentityKind,
    validate_action_request,
    validate_https_url,
)
from app.ui.navigation.contracts import RouteContext


NOW = datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc)


def test_typed_identity_keeps_registry_and_legacy_namespaces_distinct() -> None:
    registry = TenderIdentity(TenderIdentityKind.REGISTRY, "same-looking-id")
    legacy = TenderIdentity(TenderIdentityKind.LEGACY_ORM, "same-looking-id")

    assert registry != legacy
    assert registry.public_id == "registry:same-looking-id"
    assert legacy.public_id == "legacy_orm:same-looking-id"


@pytest.mark.parametrize(
    "value",
    ["", "   ", "bad\x00id", "bad\u202eid", "x" * 257],
)
def test_tender_identity_rejects_ambiguous_or_hostile_values(value: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        TenderIdentity(TenderIdentityKind.REGISTRY, value)


def test_route_context_carries_and_validates_tender_identity_kind() -> None:
    context = RouteContext(
        tender_id="registry-key",
        tender_identity_kind=TenderIdentityKind.REGISTRY.value,
    )

    assert context.tender_identity_kind == "registry"
    assert context.public_mapping()["tender_identity_kind"] == "registry"
    with pytest.raises(ValueError, match="tender_identity_kind"):
        RouteContext(tender_id="registry-key", tender_identity_kind="guessed")


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///C:/secrets.txt",
        "data:text/html,unsafe",
        "http://example.test/tender",
        "https://user:password@example.test/tender",
        "https://example.test/line\nbreak",
    ],
)
def test_official_source_url_rejects_unsafe_or_non_https_values(url: str) -> None:
    assert validate_https_url(url) is None


def test_action_execution_rejects_a_stale_snapshot_fingerprint() -> None:
    identity = TenderIdentity(TenderIdentityKind.REGISTRY, "registry-key")
    action = TenderActionSpec(
        action_id="archive_tender",
        label="Archive",
        state=TenderActionState.AVAILABLE,
        reason="",
        identity=identity,
        required_capability="registry.archive",
        role=TenderActionRole.PRIMARY,
        destructive=True,
        snapshot_fingerprint="old-fingerprint",
        source_revision="revision-1",
        focus_return_token="detail:registry-key",
        accessible_description="Archive this exact tender",
    )

    result = validate_action_request(
        action,
        identity=identity,
        current_snapshot_fingerprint="new-fingerprint",
        current_source_revision="revision-1",
    )

    assert result.allowed is False
    assert result.reason_code == "action_stale"
    assert result.state is TenderDetailState.STALE
    assert validate_action_request(
        replace(action, snapshot_fingerprint="new-fingerprint"),
        identity=identity,
        current_snapshot_fingerprint="new-fingerprint",
        current_source_revision="revision-1",
    ).allowed
