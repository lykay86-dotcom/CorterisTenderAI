"""Tests for crash-report bootstrap integration."""

from __future__ import annotations

from app.bootstrap import _find_support_bundle_provider


class _Page:
    def create_diagnostic_support_bundle(self, target):
        return target


class _Window:
    def __init__(self, *, workflow=None):
        self.workflow_page = workflow


def test_bootstrap_prefers_canonical_workflow_support_provider() -> None:
    page = _Page()
    window = _Window(workflow=page)

    provider = _find_support_bundle_provider(window)

    assert provider is not None
    assert provider("support.ctsupport") == "support.ctsupport"


def test_bootstrap_returns_none_without_workflow_page() -> None:
    window = _Window()

    assert _find_support_bundle_provider(window) is None
