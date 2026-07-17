"""RM-132 adversarial error, repr and export guards."""

from __future__ import annotations

from dataclasses import asdict
import json

from app.tenders.provider_credentials import (
    CredentialCommandStatus,
    CredentialErrorCategory,
    ProviderCredentialService,
)
from app.tenders.providers.commercial_catalog import create_commercial_provider_catalog
from app.tenders.providers.mos_supplier_config import MosSupplierApiConfig


class FailingBackend:
    def __init__(self, sentinel: str) -> None:
        self.sentinel = sentinel

    def has(self, _name: str) -> bool:
        raise RuntimeError(f"private C:/Users/account token={self.sentinel}")

    def save(self, _name: str, _value: str) -> None:
        raise RuntimeError(f"Authorization: Bearer {self.sentinel}")

    def delete(self, _name: str) -> None:
        raise PermissionError(f"password={self.sentinel}")


def test_backend_exceptions_are_bounded_and_sentinel_free(caplog) -> None:
    sentinel = "RM132_SECRET_SENTINEL_BACKEND"
    service = ProviderCredentialService(FailingBackend(sentinel), environment={})

    state = service.has_secret("mos_supplier", "api_key")
    saved = service.save_secret("mos_supplier", "api_key", "new-value")
    deleted = service.delete_secret("mos_supplier", "api_key")
    rendered = json.dumps(
        [asdict(state), asdict(saved), asdict(deleted)],
        ensure_ascii=False,
        default=str,
    )

    assert saved.status is CredentialCommandStatus.OPERATION_FAILED
    assert deleted.error_category is CredentialErrorCategory.ACCESS_DENIED
    assert sentinel not in rendered
    assert sentinel not in repr((state, saved, deleted))
    assert sentinel not in caplog.text
    assert "Users" not in rendered


def test_runtime_models_have_no_masked_secret_export() -> None:
    sentinel = "RM132_SECRET_SENTINEL_EXPORT"
    commercial = create_commercial_provider_catalog(
        environment={
            "CORTERIS_B2B_ENABLED": "true",
            "CORTERIS_B2B_ACCESS_CONFIRMED": "true",
            "CORTERIS_B2B_API_BASE_URL": "https://api.example.test",
            "CORTERIS_B2B_API_KEY": sentinel,
        }
    ).get("b2b_center")
    payload = commercial.public_payload()
    mos = MosSupplierApiConfig(api_token=sentinel)

    assert payload["api_key_configured"] is True
    assert "masked_api_key" not in payload
    assert not hasattr(commercial, "masked_api_key")
    assert not hasattr(mos, "masked_token")
    assert sentinel not in json.dumps(payload, ensure_ascii=False)
    assert sentinel not in repr(commercial)
    assert sentinel not in repr(mos)
