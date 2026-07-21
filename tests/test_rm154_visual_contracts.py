"""Expected-red behavioral contract for the RM-154 visual core."""

from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from pathlib import Path

from PIL import Image
import pytest

from scripts.rm154_visual_qa.contracts import (
    STRICT_RGB_V1,
    OutcomeReason,
    RendererFingerprint,
    VisualCase,
    VisualOutcome,
    Viewport,
)
from scripts.rm154_visual_qa.pending import (
    assess_environment,
    compare_rgb_png,
    privacy_findings,
    resolve_case_artifact_dir,
)


def _png(width: int = 4, height: int = 3, color: tuple[int, int, int] = (10, 20, 30)) -> bytes:
    image = Image.new("RGB", (width, height), color)
    output = BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _fingerprint() -> RendererFingerprint:
    return RendererFingerprint(
        profile_id="windows-latest-python312-qt6111",
        platform="Windows",
        platform_release="2022Server",
        python="3.12.7",
        pyside="6.11.1",
        qt="6.11.1",
        pillow="12.3.0",
        qpa_platform="offscreen",
        qt_style="fusion",
        qt_locale="ru_RU",
        timezone="Europe/Moscow",
        logical_dpi=96.0,
        device_pixel_ratio=1.0,
        color_depth=32,
        font_hashes=(("segoeui.ttf", "a" * 64),),
        icon_manifest_sha256="b" * 64,
        design_system_version="corteris-design-v1",
    )


def test_case_contract_is_typed_immutable_and_theme_bound() -> None:
    case = VisualCase(
        case_id="shell.dashboard.empty.dark.canonical",
        surface_owner="ModernMainWindow",
        fixture_id="shell-empty-v1",
        theme="dark",
        viewport=Viewport(1540, 940),
    )

    assert case.comparison_policy_id == STRICT_RGB_V1.policy_id
    with pytest.raises((AttributeError, TypeError)):
        case.theme = "light"  # type: ignore[misc]
    with pytest.raises(ValueError, match="theme"):
        replace(case, theme="light")


def test_case_contract_rejects_unsafe_identity() -> None:
    with pytest.raises(ValueError, match="invalid visual case id"):
        VisualCase(
            case_id="../private.dark.canonical",
            surface_owner="ModernMainWindow",
            fixture_id="unsafe",
            theme="dark",
            viewport=Viewport(10, 10),
        )


def test_strict_comparator_accepts_identical_normalized_png() -> None:
    png = _png()
    result = compare_rgb_png("component.gallery.dark.canonical", png, png)

    assert result.outcome is VisualOutcome.PASS
    assert result.reason is OutcomeReason.MATCH
    assert result.metrics is not None
    assert result.metrics.changed_pixels == 0


def test_deliberate_token_mutation_fails_strict_comparison() -> None:
    result = compare_rgb_png(
        "component.gallery.dark.canonical",
        _png(color=(10, 20, 30)),
        _png(color=(11, 20, 30)),
    )

    assert result.outcome is VisualOutcome.FAIL
    assert result.reason is OutcomeReason.PIXEL_MISMATCH
    assert result.metrics is not None
    assert result.metrics.changed_pixels == 12
    assert result.metrics.max_channel_delta == 1


def test_deliberate_layout_mutation_fails_before_pixel_threshold() -> None:
    result = compare_rgb_png(
        "shell.dashboard.empty.light.canonical",
        _png(width=4),
        _png(width=5),
    )

    assert result.outcome is VisualOutcome.FAIL
    assert result.reason is OutcomeReason.DIMENSION_MISMATCH


def test_environment_drift_is_typed_block_not_pixel_pass() -> None:
    expected = _fingerprint()
    actual = replace(expected, qt="6.12.0")

    result = assess_environment("shell.dashboard.empty.dark.canonical", expected, actual)

    assert result.outcome is VisualOutcome.BLOCKED
    assert result.reason is OutcomeReason.ENVIRONMENT_MISMATCH
    assert "qt" in result.detail


def test_artifact_directory_is_contained_and_case_scoped(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    resolved = resolve_case_artifact_dir(root, "shell.dashboard.empty.dark.canonical")

    assert resolved == root.resolve() / "shell.dashboard.empty.dark.canonical"
    assert resolved.is_relative_to(root.resolve())
    with pytest.raises(ValueError, match="case id"):
        resolve_case_artifact_dir(root, "../escape")


def test_privacy_scanner_rejects_absolute_paths_and_secret_patterns() -> None:
    findings = privacy_findings(
        (
            r"C:\Users\PrivateUser\Downloads\customer.png",
            "OPENAI_API_KEY=sk-test-secret",
            "VISUAL-001",
        )
    )

    assert any("absolute-path" in item for item in findings)
    assert any("secret" in item for item in findings)
    assert not any("VISUAL-001" in item for item in findings)


def test_fingerprint_is_stable_and_sanitized() -> None:
    fingerprint = _fingerprint()

    assert fingerprint.canonical_bytes().endswith(b"\n")
    assert len(fingerprint.sha256) == 64
    assert b"PrivateUser" not in fingerprint.canonical_bytes()
