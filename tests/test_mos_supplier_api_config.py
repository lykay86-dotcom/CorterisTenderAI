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
    assert config.masked_token == "secr…alue"
    assert "secret-token-value" not in repr(config)


def test_empty_token_is_not_configured() -> None:
    config = MosSupplierApiConfig.from_environment({})

    assert not config.configured
    assert config.get_url == (
        "https://api.zakupki.mos.ru/api/v2/auction/public/Get"
    )
    assert config.masked_token == ""
