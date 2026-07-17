"""RM-131 canonical provider identity and explicit alias contract."""

from __future__ import annotations

import pytest

from app.tenders.collector.provider_definitions import (
    canonical_provider_definitions,
    canonical_provider_id,
    provider_aliases,
    resolve_provider_ids,
)


def test_canonical_catalog_contains_one_async_identity_per_source() -> None:
    definitions = canonical_provider_definitions()
    ids = tuple(item.id for item in definitions)

    assert ids == (
        "eis",
        "mos_supplier",
        "b2b_center",
        "gazprombank",
        "fabrikant",
        "tek_torg",
        "otc",
        "sber_commercial",
        "rts_commercial",
        "roseltorg_commercial",
    )
    assert len(ids) == len(set(ids))
    assert len({item.source for item in definitions}) == len(definitions)


def test_only_audited_sync_aliases_are_accepted() -> None:
    assert provider_aliases() == {
        "sber_a": "sber_commercial",
        "rts_tender": "rts_commercial",
        "roseltorg": "roseltorg_commercial",
    }
    assert canonical_provider_id(" SBER_A ") == "sber_commercial"
    assert canonical_provider_id("rts_commercial") == "rts_commercial"
    with pytest.raises(KeyError):
        canonical_provider_id("commercial")
    with pytest.raises(KeyError):
        canonical_provider_id("unknown")


def test_alias_resolution_is_ordered_deduplicated_and_canonical() -> None:
    assert resolve_provider_ids(("sber_a", "eis", "SBER_COMMERCIAL", "roseltorg")) == (
        "sber_commercial",
        "eis",
        "roseltorg_commercial",
    )

    with pytest.raises(KeyError):
        resolve_provider_ids(("eis", "commercial"))
