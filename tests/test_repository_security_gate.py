from __future__ import annotations

from scripts.check_repository_secrets import scan_repository, scan_text


def test_secret_scanner_detects_supported_formats_without_returning_values() -> None:
    github_token = "ghp_" + "a" * 36
    openai_key = "sk-" + "b" * 32

    findings = scan_text(f"first={github_token}\nsecond={openai_key}")

    assert findings == ("github-token", "openai-key")
    assert github_token not in repr(findings)
    assert openai_key not in repr(findings)


def test_tracked_repository_contains_no_high_confidence_secrets() -> None:
    assert scan_repository() == ()
