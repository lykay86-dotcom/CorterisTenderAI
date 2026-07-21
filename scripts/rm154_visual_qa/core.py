"""Pure comparison, normalization, environment, path, and privacy primitives."""

from __future__ import annotations

from dataclasses import fields
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from typing import Iterable

from PIL import Image, UnidentifiedImageError

from .contracts import (
    CASE_ID_RE,
    STRICT_RGB_V1,
    ComparisonMetrics,
    ComparisonPolicy,
    OutcomeReason,
    RendererFingerprint,
    VisualOutcome,
    VisualResult,
)


_WINDOWS_ABSOLUTE_RE = re.compile(r"(?i)(?:^|[\s=\"'])(?:[a-z]:\\|\\\\)[^\s\"']+")
_POSIX_PRIVATE_RE = re.compile(r"(?:^|[\s=\"'])/(?:home|users|tmp|private|var/tmp)/[^\s\"']+")
_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_SECRET_RES = (
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mssql)://\S+"),
)


def normalize_png_bytes(source: bytes) -> bytes:
    """Return a deterministic metadata-free RGB PNG."""

    try:
        with Image.open(BytesIO(source)) as opened:
            opened.load()
            image = opened.convert("RGB")
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("source is not a readable image") from exc

    output = BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    normalized = output.getvalue()
    with Image.open(BytesIO(normalized)) as verified:
        verified.load()
        if verified.mode != "RGB" or verified.size != image.size:
            raise ValueError("normalized PNG verification failed")
    return normalized


def normalized_png_sha256(png: bytes) -> str:
    return sha256(normalize_png_bytes(png)).hexdigest()


def pixel_sha256(png: bytes) -> str:
    normalized = normalize_png_bytes(png)
    with Image.open(BytesIO(normalized)) as image:
        image.load()
        width, height = image.size
        payload = width.to_bytes(4, "big") + height.to_bytes(4, "big") + image.tobytes()
    return sha256(payload).hexdigest()


def compare_rgb_png(
    case_id: str,
    expected_png: bytes,
    actual_png: bytes,
    policy: ComparisonPolicy = STRICT_RGB_V1,
) -> VisualResult:
    """Compare two images using the explicit numeric RGB policy."""

    expected_bytes = normalize_png_bytes(expected_png)
    actual_bytes = normalize_png_bytes(actual_png)
    with Image.open(BytesIO(expected_bytes)) as expected_image:
        expected_image.load()
        expected = expected_image.copy()
    with Image.open(BytesIO(actual_bytes)) as actual_image:
        actual_image.load()
        actual = actual_image.copy()

    expected_width, expected_height = expected.size
    actual_width, actual_height = actual.size
    if expected.size != actual.size:
        metrics = ComparisonMetrics(
            expected_width=expected_width,
            expected_height=expected_height,
            actual_width=actual_width,
            actual_height=actual_height,
            changed_pixels=0,
            changed_percent=0.0,
            max_channel_delta=0,
            mean_absolute_delta=0.0,
            bounding_box=None,
        )
        return VisualResult(
            outcome=VisualOutcome.FAIL,
            reason=OutcomeReason.DIMENSION_MISMATCH,
            case_id=case_id,
            metrics=metrics,
            detail=(
                f"expected {expected_width}x{expected_height}, "
                f"actual {actual_width}x{actual_height}"
            ),
        )

    expected_raw = expected.tobytes()
    actual_raw = actual.tobytes()
    delta = bytearray(len(expected_raw))
    changed_pixels = 0
    max_channel_delta = 0
    absolute_total = 0
    left = expected_width
    top = expected_height
    right = -1
    bottom = -1
    for index in range(0, len(expected_raw), 3):
        d0 = abs(expected_raw[index] - actual_raw[index])
        d1 = abs(expected_raw[index + 1] - actual_raw[index + 1])
        d2 = abs(expected_raw[index + 2] - actual_raw[index + 2])
        delta[index] = d0
        delta[index + 1] = d1
        delta[index + 2] = d2
        pixel_max = max(d0, d1, d2)
        if pixel_max:
            changed_pixels += 1
            pixel_index = index // 3
            x = pixel_index % expected_width
            y = pixel_index // expected_width
            left = min(left, x)
            top = min(top, y)
            right = max(right, x)
            bottom = max(bottom, y)
        max_channel_delta = max(max_channel_delta, pixel_max)
        absolute_total += d0 + d1 + d2

    total_pixels = expected_width * expected_height
    mean_delta = absolute_total / len(expected_raw) if expected_raw else 0.0
    bounding_box = None if right < 0 else (left, top, right + 1, bottom + 1)
    metrics = ComparisonMetrics(
        expected_width=expected_width,
        expected_height=expected_height,
        actual_width=actual_width,
        actual_height=actual_height,
        changed_pixels=changed_pixels,
        changed_percent=(changed_pixels / total_pixels * 100.0 if total_pixels else 0.0),
        max_channel_delta=max_channel_delta,
        mean_absolute_delta=mean_delta,
        bounding_box=bounding_box,
    )
    passed = (
        changed_pixels <= policy.max_changed_pixels
        and max_channel_delta <= policy.max_channel_delta
        and mean_delta <= policy.max_mean_delta
    )
    return VisualResult(
        outcome=VisualOutcome.PASS if passed else VisualOutcome.FAIL,
        reason=OutcomeReason.MATCH if passed else OutcomeReason.PIXEL_MISMATCH,
        case_id=case_id,
        metrics=metrics,
        detail=(
            "pixels match approved policy"
            if passed
            else (
                f"changed={changed_pixels}, max_delta={max_channel_delta}, "
                f"mean_delta={mean_delta:.6f}"
            )
        ),
    )


def assess_environment(
    case_id: str,
    expected: RendererFingerprint,
    actual: RendererFingerprint,
) -> VisualResult:
    """Fail closed before pixels when any fingerprint field differs."""

    differences = tuple(
        field.name
        for field in fields(RendererFingerprint)
        if getattr(expected, field.name) != getattr(actual, field.name)
    )
    if differences:
        return VisualResult(
            outcome=VisualOutcome.BLOCKED,
            reason=OutcomeReason.ENVIRONMENT_MISMATCH,
            case_id=case_id,
            detail="renderer fields differ: " + ", ".join(differences),
        )
    return VisualResult(
        outcome=VisualOutcome.PASS,
        reason=OutcomeReason.MATCH,
        case_id=case_id,
        detail="renderer fingerprint matches",
    )


def resolve_case_artifact_dir(root: Path, case_id: str) -> Path:
    """Resolve a case directory without allowing traversal outside the artifact root."""

    if CASE_ID_RE.fullmatch(case_id) is None:
        raise ValueError(f"invalid visual case id: {case_id!r}")
    resolved_root = root.resolve(strict=False)
    resolved = (resolved_root / case_id).resolve(strict=False)
    if not resolved.is_relative_to(resolved_root):
        raise ValueError("case artifact path escapes artifact root")
    return resolved


def privacy_findings(values: Iterable[str]) -> tuple[str, ...]:
    """Return sanitized finding codes without echoing private source values."""

    findings: list[str] = []
    for index, value in enumerate(values):
        if _WINDOWS_ABSOLUTE_RE.search(value) or _POSIX_PRIVATE_RE.search(value):
            findings.append(f"absolute-path:{index}")
        if _EMAIL_RE.search(value):
            findings.append(f"email:{index}")
        if any(pattern.search(value) for pattern in _SECRET_RES):
            findings.append(f"secret:{index}")
    return tuple(findings)
