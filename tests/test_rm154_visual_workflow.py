"""Governance tests for RM-154 candidate and baseline workflow."""

from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
import pytest

from scripts.rm154_visual_qa.catalog import VISUAL_CASES
from scripts.rm154_visual_qa.contracts import FontFingerprint, RendererFingerprint
from scripts.rm154_visual_qa.core import (
    normalized_png_sha256,
    pixel_sha256,
    visual_diff_pngs,
)
from scripts.rm154_visual_qa.workflow import (
    APPROVAL_PHRASE,
    CANDIDATE_SCHEMA,
    REPOSITORY_PNG_BUDGET,
    VisualWorkflowError,
    import_candidate,
    validate_baseline,
)


@pytest.fixture(autouse=True)
def _local_import_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Import tests exercise local authorization unless a test opts into CI."""

    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


def _png(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (3, 2), color)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _candidate_bundle(root: Path, *, canonical: bool = True) -> Path:
    images = root / "images"
    images.mkdir(parents=True)
    renderer = RendererFingerprint(
        profile_id="windows-latest-python312",
        platform="Windows",
        platform_release="2022Server",
        platform_version="10.0.20348",
        ci_image="win22:20260720.1",
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
        fonts=(FontFingerprint("segoeui.ttf", 100, "a" * 64, ("Segoe UI",)),),
        icon_manifest_sha256="b" * 64,
        design_system_version="corteris-design-v1",
    )
    records = []
    total = 0
    for index, case in enumerate(VISUAL_CASES):
        png = _png_for_size(
            case.viewport.width,
            case.viewport.height,
            (index + 1, 20, 30),
        )
        path = images / f"{case.case_id}.png"
        path.write_bytes(png)
        digest = normalized_png_sha256(png)
        records.append(
            {
                "case_id": case.case_id,
                "comparison_policy_id": case.comparison_policy_id,
                "encoded_bytes": len(png),
                "file": f"images/{case.case_id}.png",
                "fixture_id": case.fixture_id,
                "height": case.viewport.height,
                "mask_policy_id": case.mask_policy_id,
                "native_evidence_required": case.native_evidence_required,
                "pixel_sha256": pixel_sha256(png),
                "png_sha256": digest,
                "repeat_sha256": [digest, digest, digest],
                "surface_owner": case.surface_owner,
                "theme": case.theme,
                "viewport": [case.viewport.width, case.viewport.height],
                "width": case.viewport.width,
            }
        )
        total += len(png)
    manifest = {
        "canonical_ci": canonical,
        "cases": records,
        "contract_version": "rm154-visual-contract-v1",
        "renderer": renderer.canonical_data(),
        "renderer_sha256": renderer.sha256,
        "repository_png_budget": REPOSITORY_PNG_BUDGET,
        "schema": CANDIDATE_SCHEMA,
        "source_commit": "c" * 40,
        "total_png_bytes": total,
    }
    (root / "candidate-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return root


def _png_for_size(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (width, height), color)
    output = BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def test_diff_artifacts_are_deterministic_visible_and_metadata_free() -> None:
    first = visual_diff_pngs(_png((10, 20, 30)), _png((11, 20, 30)))
    second = visual_diff_pngs(_png((10, 20, 30)), _png((11, 20, 30)))

    assert first == second
    for png in first:
        with Image.open(BytesIO(png)) as image:
            image.load()
            assert image.mode == "RGB"
            assert image.info == {}
            assert image.getbbox() is not None


def test_import_requires_explicit_approval_before_reading_candidate(tmp_path: Path) -> None:
    with pytest.raises(VisualWorkflowError, match="approval phrase"):
        import_candidate(
            candidate_root=tmp_path / "missing",
            baseline_root=tmp_path / "baseline",
            approval="yes",
            reviewer="rm154-reviewer",
            reason="Initial reviewed baseline",
        )


def test_import_is_prohibited_in_ci(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(VisualWorkflowError, match="prohibited in CI"):
        import_candidate(
            candidate_root=tmp_path / "missing",
            baseline_root=tmp_path / "baseline",
            approval=APPROVAL_PHRASE,
            reviewer="rm154-reviewer",
            reason="Initial reviewed baseline",
        )


def test_reviewed_canonical_candidate_imports_and_validates(tmp_path: Path) -> None:
    candidate = _candidate_bundle(tmp_path / "candidate")
    baseline_root = tmp_path / "baseline"

    manifest = import_candidate(
        candidate_root=candidate,
        baseline_root=baseline_root,
        approval=APPROVAL_PHRASE,
        reviewer="rm154-reviewer",
        reason="Initial reviewed synthetic baseline",
    )

    assert manifest["review"]["reviewer"] == "rm154-reviewer"
    assert validate_baseline(baseline_root)["renderer_sha256"] == manifest["renderer_sha256"]
    assert len(tuple((baseline_root / "images").glob("*.png"))) == len(VISUAL_CASES)


def test_noncanonical_candidate_cannot_be_imported(tmp_path: Path) -> None:
    candidate = _candidate_bundle(tmp_path / "candidate", canonical=False)

    with pytest.raises(VisualWorkflowError, match="canonical CI candidate"):
        import_candidate(
            candidate_root=candidate,
            baseline_root=tmp_path / "baseline",
            approval=APPROVAL_PHRASE,
            reviewer="rm154-reviewer",
            reason="Must not be accepted",
        )


def test_result_json_shape_never_requires_absolute_paths() -> None:
    payload = {"case_id": "shell.dashboard.empty.dark.canonical", "outcome": "FAIL"}
    serialized = json.dumps(payload, sort_keys=True)

    assert "C:\\" not in serialized
    assert "/home/" not in serialized
