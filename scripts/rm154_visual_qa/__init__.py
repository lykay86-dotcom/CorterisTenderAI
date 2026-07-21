"""Test-only deterministic visual QA support for RM-154."""

from .contracts import (
    STRICT_RGB_V1,
    ComparisonMetrics,
    ComparisonPolicy,
    FontFingerprint,
    OutcomeReason,
    RendererFingerprint,
    VisualCase,
    VisualOutcome,
    VisualResult,
    Viewport,
)
from .core import (
    assess_environment,
    compare_rgb_png,
    normalize_png_bytes,
    normalized_png_sha256,
    pixel_sha256,
    privacy_findings,
    resolve_case_artifact_dir,
)

__all__ = [
    "STRICT_RGB_V1",
    "ComparisonMetrics",
    "ComparisonPolicy",
    "FontFingerprint",
    "OutcomeReason",
    "RendererFingerprint",
    "VisualCase",
    "VisualOutcome",
    "VisualResult",
    "Viewport",
    "assess_environment",
    "compare_rgb_png",
    "normalize_png_bytes",
    "normalized_png_sha256",
    "pixel_sha256",
    "privacy_findings",
    "resolve_case_artifact_dir",
]
