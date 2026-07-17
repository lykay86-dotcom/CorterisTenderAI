from __future__ import annotations

from app.tenders.providers.mos_supplier_api import MosSupplierApiConfig


def test_config_reads_token_and_endpoint_overrides() -> None:
    config = MosSupplierApiConfig.from_environment(
        {
            "CORTERIS_MOS_API_KEY": "secret-token-value",
            "CORTERIS_MOS_SEARCH_URL": "https://example.test/search",
            "CORTERIS_MOS_GET_URL": "https://example.test/get",
        }
    )

    assert config.configured
    assert config.search_url == "https://example.test/search"
    assert config.get_url == "https://example.test/get"
    assert not hasattr(config, "masked_token")
    assert "secret-token-value" not in repr(config)


def test_empty_token_is_not_configured() -> None:
    config = MosSupplierApiConfig.from_environment({})

    assert not config.configured
    assert config.get_url == ("https://api.zakupki.mos.ru/api/v2/auction/public/Get")
    assert not hasattr(config, "masked_token")


def test_explicit_environment_never_reads_host_credential_store(monkeypatch) -> None:
    requested_names: list[str] = []

    def unexpected_loader(name: str) -> str | None:
        requested_names.append(name)
        return "host-secret"

    monkeypatch.setattr(
        "app.tenders.providers.mos_supplier_config._load_keyring_secret_safely",
        unexpected_loader,
    )

    config = MosSupplierApiConfig.from_environment({})

    assert not config.configured
    assert requested_names == []


def test_config_reads_token_from_windows_credential_store() -> None:
    requested_names: list[str] = []

    def load_secret(name: str) -> str | None:
        requested_names.append(name)
        return "saved-secret-token"

    config = MosSupplierApiConfig.from_environment({}, secret_loader=load_secret)

    assert config.api_token == "saved-secret-token"
    assert requested_names == ["collector.mos_supplier.api_key"]


def test_environment_token_has_priority_over_credential_store() -> None:
    config = MosSupplierApiConfig.from_environment(
        {"CORTERIS_MOS_API_KEY": "environment-token"},
        secret_loader=lambda _name: "stored-token",
    )

    assert config.api_token == "environment-token"
