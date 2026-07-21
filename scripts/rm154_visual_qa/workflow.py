"""Candidate, comparison, validation, and explicit baseline-import workflow."""

from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
import json
import os
from pathlib import Path
import re
# Used only with fixed git argv and shell disabled.
import subprocess  # nosec B404
from typing import Any

from PIL import Image
from PySide6.QtWidgets import QApplication

from .catalog import VISUAL_CASES
from .contracts import FontFingerprint, RendererFingerprint, VisualCase, VisualOutcome
from .core import (
    assess_environment,
    compare_rgb_png,
    normalized_png_sha256,
    pixel_sha256,
    privacy_findings,
    resolve_case_artifact_dir,
    visual_diff_pngs,
)
from .environment import collect_renderer_fingerprint, is_canonical_ci
from .renderer import capture_case


CANDIDATE_SCHEMA = "rm154-visual-candidate-v1"
BASELINE_SCHEMA = "rm154-visual-baseline-v1"
APPROVAL_PHRASE = "RM-154-BASELINE-UPDATE"
REPEAT_COUNT = 3
REPOSITORY_PNG_BUDGET = 5_000_000
_REVIEWER_RE = re.compile(r"^[A-Za-z0-9_.-]{2,80}$")


class VisualWorkflowError(RuntimeError):
    """A governed visual workflow condition was not satisfied."""


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _git_head(root: Path) -> str:
    supplied = os.environ.get("RM154_SOURCE_COMMIT", "")
    if supplied:
        if re.fullmatch(r"[0-9a-f]{40}", supplied) is None:
            raise VisualWorkflowError("RM154_SOURCE_COMMIT must be a full lowercase SHA")
        return supplied
    # Constant git command; no user-controlled argv.
    return subprocess.run(  # nosec B603
        ("git", "rev-parse", "HEAD"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _case_record(case: VisualCase, png: bytes, repeats: tuple[str, ...]) -> dict[str, Any]:
    with Image.open(BytesIO(png)) as image:
        image.load()
        width, height = image.size
    return {
        "case_id": case.case_id,
        "comparison_policy_id": case.comparison_policy_id,
        "encoded_bytes": len(png),
        "file": f"images/{case.case_id}.png",
        "fixture_id": case.fixture_id,
        "height": height,
        "mask_policy_id": case.mask_policy_id,
        "native_evidence_required": case.native_evidence_required,
        "pixel_sha256": pixel_sha256(png),
        "png_sha256": normalized_png_sha256(png),
        "repeat_sha256": list(repeats),
        "surface_owner": case.surface_owner,
        "theme": case.theme,
        "viewport": [case.viewport.width, case.viewport.height],
        "width": width,
    }


def _write_bytes_below(root: Path, relative: str, payload: bytes) -> Path:
    resolved_root = root.resolve(strict=False)
    target = (resolved_root / relative).resolve(strict=False)
    if not target.is_relative_to(resolved_root):
        raise VisualWorkflowError("artifact target escapes root")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return target


def generate_candidate(
    *, root: Path, artifact_root: Path, repeats: int = REPEAT_COUNT
) -> dict[str, Any]:
    if repeats != REPEAT_COUNT:
        raise VisualWorkflowError(f"candidate mode requires exactly {REPEAT_COUNT} repeats")
    artifact_root = artifact_root.resolve(strict=False)
    artifact_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    renderer: RendererFingerprint | None = None

    for case in VISUAL_CASES:
        hashes: list[str] = []
        accepted_png: bytes | None = None
        for repeat in range(repeats):
            capture = capture_case(
                case,
                root=root,
                runtime_root=artifact_root / ".runtime" / case.case_id / str(repeat),
            )
            if renderer is None:
                renderer = capture.renderer
            else:
                environment = assess_environment(case.case_id, renderer, capture.renderer)
                if environment.outcome is not VisualOutcome.PASS:
                    raise VisualWorkflowError(environment.detail)
            digest = normalized_png_sha256(capture.png)
            hashes.append(digest)
            accepted_png = capture.png
        if len(set(hashes)) != 1 or accepted_png is None:
            raise VisualWorkflowError(f"repeatability drift: {case.case_id}: {hashes}")
        _write_bytes_below(artifact_root, f"images/{case.case_id}.png", accepted_png)
        records.append(_case_record(case, accepted_png, tuple(hashes)))

    if renderer is None:
        raise VisualWorkflowError("visual catalog is empty")
    total_bytes = sum(int(record["encoded_bytes"]) for record in records)
    if total_bytes > REPOSITORY_PNG_BUDGET:
        raise VisualWorkflowError(
            f"candidate PNG budget exceeded: {total_bytes} > {REPOSITORY_PNG_BUDGET}"
        )
    manifest = {
        "canonical_ci": is_canonical_ci(),
        "cases": records,
        "contract_version": "rm154-visual-contract-v1",
        "renderer": renderer.canonical_data(),
        "renderer_sha256": renderer.sha256,
        "repository_png_budget": REPOSITORY_PNG_BUDGET,
        "schema": CANDIDATE_SCHEMA,
        "source_commit": _git_head(root),
        "total_png_bytes": total_bytes,
    }
    serialized = _canonical_json_bytes(manifest)
    findings = privacy_findings((serialized.decode("utf-8"),))
    if findings:
        raise VisualWorkflowError("candidate manifest privacy violation: " + ", ".join(findings))
    _write_bytes_below(artifact_root, "candidate-manifest.json", serialized)
    validate_candidate(artifact_root)
    return manifest


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise VisualWorkflowError(f"manifest is not an object: {path.name}")
    return payload


def _renderer_from_data(payload: dict[str, Any]) -> RendererFingerprint:
    data = dict(payload)
    fonts = data.get("fonts")
    if not isinstance(fonts, list):
        raise VisualWorkflowError("renderer fonts must be a list")
    data["fonts"] = tuple(
        FontFingerprint(
            file_name=str(font["file_name"]),
            byte_size=int(font["byte_size"]),
            sha256=str(font["sha256"]),
            families=tuple(str(family) for family in font["families"]),
        )
        for font in fonts
    )
    try:
        return RendererFingerprint(**data)
    except (TypeError, ValueError) as exc:
        raise VisualWorkflowError("invalid renderer fingerprint") from exc


def _validate_case_files(bundle_root: Path, manifest: dict[str, Any]) -> None:
    records = manifest.get("cases")
    if not isinstance(records, list):
        raise VisualWorkflowError("manifest cases must be a list")
    expected_ids = tuple(case.case_id for case in VISUAL_CASES)
    actual_ids = tuple(record.get("case_id") for record in records if isinstance(record, dict))
    if actual_ids != expected_ids:
        raise VisualWorkflowError("manifest case list/order differs from closed catalog")
    expected_files: set[Path] = set()
    for case, record in zip(VISUAL_CASES, records, strict=True):
        relative = record.get("file")
        case_id = record.get("case_id")
        if relative != f"images/{case_id}.png":
            raise VisualWorkflowError(f"unsafe or unexpected baseline path: {case_id}")
        path = (bundle_root / relative).resolve(strict=True)
        if not path.is_relative_to(bundle_root.resolve(strict=False)):
            raise VisualWorkflowError(f"case file escapes bundle: {case_id}")
        png = path.read_bytes()
        with Image.open(BytesIO(png)) as image:
            image.load()
            if image.mode != "RGB":
                raise VisualWorkflowError(f"baseline is not RGB: {case_id}")
            if image.size != (record.get("width"), record.get("height")):
                raise VisualWorkflowError(f"baseline dimensions mismatch: {case_id}")
        governed = {
            "comparison_policy_id": case.comparison_policy_id,
            "fixture_id": case.fixture_id,
            "mask_policy_id": case.mask_policy_id,
            "native_evidence_required": case.native_evidence_required,
            "surface_owner": case.surface_owner,
            "theme": case.theme,
            "viewport": [case.viewport.width, case.viewport.height],
        }
        if any(record.get(key) != value for key, value in governed.items()):
            raise VisualWorkflowError(f"case governance metadata mismatch: {case_id}")
        if (record.get("width"), record.get("height")) != (
            case.viewport.width,
            case.viewport.height,
        ):
            raise VisualWorkflowError(f"case viewport dimensions mismatch: {case_id}")
        if normalized_png_sha256(png) != record.get("png_sha256"):
            raise VisualWorkflowError(f"PNG hash mismatch: {case_id}")
        if pixel_sha256(png) != record.get("pixel_sha256"):
            raise VisualWorkflowError(f"pixel hash mismatch: {case_id}")
        if len(png) != record.get("encoded_bytes"):
            raise VisualWorkflowError(f"encoded size mismatch: {case_id}")
        repeats = record.get("repeat_sha256")
        if repeats != [record.get("png_sha256")] * REPEAT_COUNT:
            raise VisualWorkflowError(f"repeatability evidence mismatch: {case_id}")
        expected_files.add(path)
    image_root = bundle_root / "images"
    actual_files = {path.resolve() for path in image_root.glob("*.png")}
    if actual_files != expected_files:
        raise VisualWorkflowError("bundle contains missing or extra PNG files")


def validate_candidate(bundle_root: Path) -> dict[str, Any]:
    bundle_root = bundle_root.resolve(strict=True)
    manifest = _load_json(bundle_root / "candidate-manifest.json")
    if manifest.get("schema") != CANDIDATE_SCHEMA:
        raise VisualWorkflowError("candidate schema mismatch")
    renderer = _renderer_from_data(manifest.get("renderer", {}))
    if renderer.sha256 != manifest.get("renderer_sha256"):
        raise VisualWorkflowError("renderer fingerprint hash mismatch")
    source_commit = manifest.get("source_commit", "")
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise VisualWorkflowError("candidate source commit is invalid")
    _validate_case_files(bundle_root, manifest)
    allowed_files = {
        (bundle_root / "candidate-manifest.json").resolve(),
        *((bundle_root / record["file"]).resolve() for record in manifest["cases"]),
    }
    actual_files = {path.resolve() for path in bundle_root.rglob("*") if path.is_file()}
    if actual_files != allowed_files:
        raise VisualWorkflowError("candidate bundle contains unexpected files")
    total = sum(int(record["encoded_bytes"]) for record in manifest["cases"])
    if total != manifest.get("total_png_bytes") or total > REPOSITORY_PNG_BUDGET:
        raise VisualWorkflowError("candidate repository budget record is invalid")
    findings = privacy_findings((_canonical_json_bytes(manifest).decode("utf-8"),))
    if findings:
        raise VisualWorkflowError("candidate privacy scan failed: " + ", ".join(findings))
    return manifest


def import_candidate(
    *,
    candidate_root: Path,
    baseline_root: Path,
    approval: str,
    reviewer: str,
    reason: str,
) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        raise VisualWorkflowError("baseline import is prohibited in CI")
    if approval != APPROVAL_PHRASE:
        raise VisualWorkflowError("explicit RM-154 approval phrase is required")
    if _REVIEWER_RE.fullmatch(reviewer) is None:
        raise VisualWorkflowError("reviewer must be a path-free identifier")
    if not reason.strip():
        raise VisualWorkflowError("baseline update reason must not be blank")
    findings = privacy_findings((reviewer, reason))
    if findings:
        raise VisualWorkflowError("review metadata privacy scan failed: " + ", ".join(findings))

    candidate = validate_candidate(candidate_root)
    if candidate.get("canonical_ci") is not True:
        raise VisualWorkflowError("only a canonical CI candidate can become a baseline")
    renderer = _renderer_from_data(candidate["renderer"])
    if renderer.profile_id != "windows-latest-python312":
        raise VisualWorkflowError("candidate renderer profile is not canonical")

    baseline_root = baseline_root.resolve(strict=False)
    baseline_root.mkdir(parents=True, exist_ok=True)
    for record in candidate["cases"]:
        source = (candidate_root / record["file"]).resolve(strict=True)
        _write_bytes_below(baseline_root, record["file"], source.read_bytes())
    baseline = {
        key: value for key, value in candidate.items() if key not in {"canonical_ci", "schema"}
    }
    baseline["schema"] = BASELINE_SCHEMA
    baseline["review"] = {
        "approval": APPROVAL_PHRASE,
        "reason": reason.strip(),
        "reviewer": reviewer,
    }
    serialized = _canonical_json_bytes(baseline)
    findings = privacy_findings((serialized.decode("utf-8"),))
    if findings:
        raise VisualWorkflowError("baseline manifest privacy scan failed: " + ", ".join(findings))
    _write_bytes_below(baseline_root, "manifest.json", serialized)
    validate_baseline(baseline_root)
    return baseline


def validate_baseline(baseline_root: Path) -> dict[str, Any]:
    baseline_root = baseline_root.resolve(strict=True)
    manifest = _load_json(baseline_root / "manifest.json")
    if manifest.get("schema") != BASELINE_SCHEMA:
        raise VisualWorkflowError("baseline schema mismatch")
    renderer = _renderer_from_data(manifest.get("renderer", {}))
    if renderer.sha256 != manifest.get("renderer_sha256"):
        raise VisualWorkflowError("baseline renderer fingerprint hash mismatch")
    review = manifest.get("review")
    if not isinstance(review, dict) or review.get("approval") != APPROVAL_PHRASE:
        raise VisualWorkflowError("baseline review authorization is missing")
    _validate_case_files(baseline_root, manifest)
    total = sum(int(record["encoded_bytes"]) for record in manifest["cases"])
    if total != manifest.get("total_png_bytes") or total > REPOSITORY_PNG_BUDGET:
        raise VisualWorkflowError("baseline repository budget record is invalid")
    if re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("source_commit", ""))) is None:
        raise VisualWorkflowError("baseline source commit is invalid")
    allowed_files = {
        (baseline_root / "manifest.json").resolve(),
        *((baseline_root / record["file"]).resolve() for record in manifest["cases"]),
    }
    actual_files = {path.resolve() for path in baseline_root.rglob("*") if path.is_file()}
    if actual_files != allowed_files:
        raise VisualWorkflowError("baseline directory contains unexpected files")
    findings = privacy_findings((_canonical_json_bytes(manifest).decode("utf-8"),))
    if findings:
        raise VisualWorkflowError("baseline privacy scan failed: " + ", ".join(findings))
    return manifest


def compare_baseline(*, root: Path, baseline_root: Path, artifact_root: Path) -> dict[str, Any]:
    baseline = validate_baseline(baseline_root)
    expected_renderer = _renderer_from_data(baseline["renderer"])
    app = QApplication.instance() or QApplication([])
    if app is None:  # pragma: no cover - Qt constructor either returns or raises
        raise VisualWorkflowError("QApplication initialization failed")
    actual_renderer = collect_renderer_fingerprint(root)
    environment = assess_environment(
        "renderer.profile.dark.canonical", expected_renderer, actual_renderer
    )
    if environment.outcome is not VisualOutcome.PASS:
        _write_bytes_below(
            artifact_root,
            "environment-result.json",
            _canonical_json_bytes(
                {
                    "actual_sha256": actual_renderer.sha256,
                    "detail": environment.detail,
                    "expected_sha256": expected_renderer.sha256,
                    "outcome": environment.outcome.value,
                    "reason": environment.reason.value,
                }
            ),
        )
        raise VisualWorkflowError(environment.detail)

    records = {record["case_id"]: record for record in baseline["cases"]}
    results: list[dict[str, Any]] = []
    failed = 0
    for case in VISUAL_CASES:
        capture = capture_case(
            case,
            root=root,
            runtime_root=artifact_root / ".runtime" / case.case_id,
        )
        expected = (baseline_root / records[case.case_id]["file"]).read_bytes()
        result = compare_rgb_png(case.case_id, expected, capture.png)
        results.append(
            {
                "case_id": case.case_id,
                "detail": result.detail,
                "metrics": asdict(result.metrics) if result.metrics else None,
                "outcome": result.outcome.value,
                "reason": result.reason.value,
            }
        )
        if result.outcome is VisualOutcome.PASS:
            continue
        failed += 1
        case_root = resolve_case_artifact_dir(artifact_root, case.case_id)
        _write_bytes_below(case_root, "actual.png", capture.png)
        _write_bytes_below(case_root, "expected.png", expected)
        if result.metrics and result.metrics.bounding_box is not None:
            diff, overlay = visual_diff_pngs(expected, capture.png)
            _write_bytes_below(case_root, "diff.png", diff)
            _write_bytes_below(case_root, "overlay.png", overlay)
        _write_bytes_below(case_root, "result.json", _canonical_json_bytes(results[-1]))

    report = {
        "case_count": len(results),
        "failed": failed,
        "passed": len(results) - failed,
        "renderer_sha256": actual_renderer.sha256,
        "results": results,
        "schema": "rm154-visual-result-v1",
    }
    _write_bytes_below(artifact_root, "comparison-result.json", _canonical_json_bytes(report))
    if failed:
        raise VisualWorkflowError(f"{failed} visual case(s) failed")
    return report
