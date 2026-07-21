"""Expected-red seams replaced by the next RM-154 implementation commit."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .contracts import (
    STRICT_RGB_V1,
    ComparisonPolicy,
    OutcomeReason,
    RendererFingerprint,
    VisualOutcome,
    VisualResult,
)


def compare_rgb_png(
    case_id: str,
    expected_png: bytes,
    actual_png: bytes,
    policy: ComparisonPolicy = STRICT_RGB_V1,
) -> VisualResult:
    del expected_png, actual_png, policy
    return VisualResult(
        outcome=VisualOutcome.BLOCKED,
        reason=OutcomeReason.IMPLEMENTATION_PENDING,
        case_id=case_id,
        detail="strict RGB comparator is not implemented",
    )


def assess_environment(
    case_id: str,
    expected: RendererFingerprint,
    actual: RendererFingerprint,
) -> VisualResult:
    del expected, actual
    return VisualResult(
        outcome=VisualOutcome.BLOCKED,
        reason=OutcomeReason.IMPLEMENTATION_PENDING,
        case_id=case_id,
        detail="renderer fingerprint comparison is not implemented",
    )


def resolve_case_artifact_dir(root: Path, case_id: str) -> Path:
    del root, case_id
    raise NotImplementedError("safe artifact path resolution is not implemented")


def privacy_findings(values: Iterable[str]) -> tuple[str, ...]:
    del values
    return ("privacy scanner is not implemented",)
