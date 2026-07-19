"""Pure RM-149 action validation and official-source URL policy."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from app.tenders.detail.contracts import (
    TenderActionSpec,
    TenderActionState,
    TenderActionValidation,
    TenderDetailState,
    TenderIdentity,
)


def validate_https_url(value: str) -> str | None:
    """Return a bounded canonical HTTPS URL, or ``None`` when unsafe."""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or len(candidate) > 2048:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        return None
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except (TypeError, ValueError):
        return None
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        return None
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        return None
    hostname = parsed.hostname.encode("idna").decode("ascii").casefold()
    if any(character.isspace() for character in hostname):
        return None
    netloc = hostname
    if ":" in hostname and not hostname.startswith("["):
        netloc = f"[{hostname}]"
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunsplit(("https", netloc, parsed.path or "/", parsed.query, ""))


def validate_action_request(
    action: TenderActionSpec,
    *,
    identity: TenderIdentity,
    current_snapshot_fingerprint: str,
    current_source_revision: str,
) -> TenderActionValidation:
    if action.identity != identity:
        return TenderActionValidation(False, "identity_mismatch", TenderDetailState.ERROR)
    if action.state is not TenderActionState.AVAILABLE:
        return TenderActionValidation(False, "action_unavailable", TenderDetailState.ERROR)
    if (
        action.snapshot_fingerprint != current_snapshot_fingerprint
        or action.source_revision != current_source_revision
    ):
        return TenderActionValidation(False, "action_stale", TenderDetailState.STALE)
    return TenderActionValidation(True, "", TenderDetailState.READY)


__all__ = ["validate_action_request", "validate_https_url"]
