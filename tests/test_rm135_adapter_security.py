"""RM-135 forbidden-mechanism and private-payload regression contract."""

from __future__ import annotations

import inspect

import app.tenders.collector.manual_adapter as manual_adapter


def test_manual_adapter_domain_has_no_dynamic_execution_or_import_path() -> None:
    source = inspect.getsource(manual_adapter)
    forbidden = (
        "eval(",
        "exec(",
        "pickle.loads",
        "marshal.loads",
        "import_module(",
        "entry_points(",
        "subprocess.",
        "os.system(",
    )
    assert not any(marker in source for marker in forbidden)


def test_manual_adapter_module_does_not_import_legacy_tester_or_keyring() -> None:
    source = inspect.getsource(manual_adapter)
    assert "ManualConnectorTester" not in source
    assert "load_secret" not in source
    assert "keyring" not in source
