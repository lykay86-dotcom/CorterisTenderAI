"""Expected RM-142 closed, exact and fail-closed route context."""

from __future__ import annotations

import pytest

from app.ui.navigation import RouteContext


def test_context_accepts_only_named_allowlisted_fields() -> None:
    context = RouteContext.from_mapping(
        {
            "tender_id": "  000123  ",
            "workflow_kind": "proposal",
            "workflow_record_id": "record-001",
            "search_query": "  камеры   IP  ",
            "focus_token": "TenderFeedTable",
        }
    )

    assert context.tender_id == "000123"
    assert context.workflow_kind == "proposal"
    assert context.workflow_record_id == "record-001"
    assert context.search_query == "камеры IP"
    assert context.focus_token == "TenderFeedTable"


def test_unknown_or_runtime_context_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unknown route context"):
        RouteContext.from_mapping({"repository": "not allowed"})
    with pytest.raises((TypeError, ValueError)):
        RouteContext.from_mapping({"tender_id": object()})
    with pytest.raises(ValueError, match="focus"):
        RouteContext(focus_token="secret\ntext")


def test_identity_is_not_guessed_or_converted() -> None:
    context = RouteContext(tender_id="0373100000126000007", workflow_record_id="0000-a")

    assert context.tender_id == "0373100000126000007"
    assert context.workflow_record_id == "0000-a"
    assert isinstance(context.tender_id, str)
