"""Configuration for the official Moscow Supplier Portal API."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Callable, Mapping

from app.security.secrets import load_secret


SecretLoader = Callable[[str], str | None]
MOS_SUPPLIER_KEYRING_SECRET = "collector.mos_supplier.api_key"


@dataclass(frozen=True, slots=True)
class MosSupplierApiConfig:
    """Connection settings for the documented Portal API."""

    api_token: str = field(default="", repr=False, compare=False)
    search_url: str = "https://api.zakupki.mos.ru/api/v2/auction/public/Search"
    get_url: str = "https://api.zakupki.mos.ru/api/v2/auction/public/Get"
    homepage_url: str = "https://zakupki.mos.ru/"
    auction_url_template: str = "https://zakupki.mos.ru/auction/{id}"
    file_download_url_template: str = (
        "https://zakupki.mos.ru/newapi/api/FileStorage/Download?id={id}"
    )
    token_environment_variable: str = "CORTERIS_MOS_API_KEY"
    search_url_environment_variable: str = "CORTERIS_MOS_SEARCH_URL"
    get_url_environment_variable: str = "CORTERIS_MOS_GET_URL"

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        secret_loader: SecretLoader | None = None,
    ) -> "MosSupplierApiConfig":
        """Build config without consulting keyring for an explicit environment.

        Production callers omit ``environment`` and retain the environment →
        Windows Credential Manager fallback. Tests and offline tools pass an
        explicit mapping; that mapping is a complete, hermetic configuration
        unless a ``secret_loader`` is deliberately injected.
        """

        env = environment if environment is not None else os.environ
        defaults = cls()
        raw_token = env.get(defaults.token_environment_variable, "")
        api_token = raw_token if isinstance(raw_token, str) else ""
        if not _credential_configured(api_token) and (
            environment is None or secret_loader is not None
        ):
            loader = secret_loader or _load_keyring_secret_safely
            loaded = loader(MOS_SUPPLIER_KEYRING_SECRET)
            api_token = loaded if isinstance(loaded, str) else ""
        return cls(
            api_token=api_token,
            search_url=str(
                env.get(
                    defaults.search_url_environment_variable,
                    defaults.search_url,
                )
            ).strip(),
            get_url=str(
                env.get(
                    defaults.get_url_environment_variable,
                    defaults.get_url,
                )
            ).strip(),
        )

    @property
    def configured(self) -> bool:
        return _credential_configured(self.api_token)


def _load_keyring_secret_safely(name: str) -> str | None:
    """Do not prevent startup when the OS credential backend is unavailable."""
    try:
        return load_secret(name)
    except Exception:
        return None


def _credential_configured(value: str) -> bool:
    return (
        bool(value)
        and bool(value.strip())
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


__all__ = [
    "MOS_SUPPLIER_KEYRING_SECRET",
    "MosSupplierApiConfig",
]
