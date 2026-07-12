"""TLS certificate support for source runs and PyInstaller builds.

The application always keeps certificate verification enabled. The context
starts with the operating-system trust store and augments it with certifi when
that package is available. A provider-specific CA bundle may be supplied
explicitly for corporate proxy or private PKI environments.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import ssl
from typing import Mapping


@dataclass(frozen=True, slots=True)
class SslContextInfo:
    """Safe diagnostic information about an SSL context."""

    ca_certificates: int
    explicit_ca_bundle: str = ""
    certifi_bundle: str = ""
    verify_mode: str = ""
    check_hostname: bool = True

    @property
    def verification_enabled(self) -> bool:
        return self.verify_mode != "CERT_NONE" and self.check_hostname


def build_ssl_context(
    ca_bundle_path: str | Path | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> ssl.SSLContext:
    """Create a verified client context using Windows/system roots + certifi.

    Precedence:
    1. An explicit ``ca_bundle_path`` supplied by application settings.
    2. ``SSL_CERT_FILE`` or ``CORTERIS_CA_BUNDLE`` from the environment.
    3. The operating-system/default Python trust store.
    4. certifi is loaded in addition to the system roots when available.

    ``verify=False`` is deliberately unsupported.
    """

    env = environment if environment is not None else os.environ
    requested = _resolve_requested_bundle(ca_bundle_path, env)

    if requested is not None:
        context = ssl.create_default_context(cafile=str(requested))
    else:
        context = ssl.create_default_context()

    # Add certifi roots without replacing enterprise/system roots. This also
    # makes one-file PyInstaller builds deterministic because hook-certifi
    # places cacert.pem inside the temporary bundle directory.
    certifi_path = _certifi_bundle()
    if certifi_path is not None and certifi_path != requested:
        context.load_verify_locations(cafile=str(certifi_path))

    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def describe_ssl_context(
    context: ssl.SSLContext,
    *,
    explicit_ca_bundle: str | Path | None = None,
) -> SslContextInfo:
    """Return non-secret diagnostics suitable for logs and support bundles."""

    try:
        count = len(context.get_ca_certs())
    except (ssl.SSLError, NotImplementedError):
        count = 0

    certifi_path = _certifi_bundle()
    return SslContextInfo(
        ca_certificates=count,
        explicit_ca_bundle=(
            str(Path(explicit_ca_bundle).expanduser().resolve())
            if explicit_ca_bundle
            else ""
        ),
        certifi_bundle=str(certifi_path) if certifi_path else "",
        verify_mode=getattr(context.verify_mode, "name", str(context.verify_mode)),
        check_hostname=bool(context.check_hostname),
    )


def _resolve_requested_bundle(
    value: str | Path | None,
    environment: Mapping[str, str],
) -> Path | None:
    raw = str(value).strip() if value is not None else ""
    if not raw:
        raw = str(environment.get("CORTERIS_CA_BUNDLE", "")).strip()
    if not raw:
        raw = str(environment.get("SSL_CERT_FILE", "")).strip()
    if not raw:
        return None

    candidate = Path(raw).expanduser().resolve()
    if not candidate.is_file():
        raise FileNotFoundError(f"CA bundle not found: {candidate}")
    return candidate


def _certifi_bundle() -> Path | None:
    try:
        import certifi
    except ImportError:
        return None

    try:
        candidate = Path(certifi.where()).resolve()
    except (OSError, RuntimeError, TypeError):
        return None
    return candidate if candidate.is_file() else None


__all__ = [
    "SslContextInfo",
    "build_ssl_context",
    "describe_ssl_context",
]
