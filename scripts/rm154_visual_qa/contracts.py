"""Pure schemas for the RM-154 visual QA workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Any


CONTRACT_VERSION = "rm154-visual-contract-v1"
CASE_SCHEMA_VERSION = "rm154-visual-case-v1"
FINGERPRINT_SCHEMA_VERSION = "rm154-renderer-fingerprint-v1"
CASE_ID_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*\.(?:dark|light)\.(?:canonical|compact)$")


class VisualOutcome(StrEnum):
    """Machine-readable result state."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class OutcomeReason(StrEnum):
    """Stable result reason for automation and diagnostics."""

    MATCH = "match"
    PIXEL_MISMATCH = "pixel_mismatch"
    DIMENSION_MISMATCH = "dimension_mismatch"
    ENVIRONMENT_MISMATCH = "environment_mismatch"
    BASELINE_MISSING = "baseline_missing"
    FIXTURE_NOT_READY = "fixture_not_ready"
    NONCANONICAL_LEG = "noncanonical_leg"
    PRIVACY_VIOLATION = "privacy_violation"
    IMPLEMENTATION_PENDING = "implementation_pending"


@dataclass(frozen=True, slots=True)
class Viewport:
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("viewport dimensions must be positive")


@dataclass(frozen=True, slots=True)
class VisualCase:
    case_id: str
    surface_owner: str
    fixture_id: str
    theme: str
    viewport: Viewport
    comparison_policy_id: str = "strict-rgb-v1"
    mask_policy_id: str = "none-v1"
    native_evidence_required: bool = False
    schema_version: str = CASE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if CASE_ID_RE.fullmatch(self.case_id) is None:
            raise ValueError(f"invalid visual case id: {self.case_id!r}")
        if self.theme not in {"dark", "light"}:
            raise ValueError("theme must be dark or light")
        if f".{self.theme}." not in self.case_id:
            raise ValueError("case id theme must match case theme")
        for field_name in ("surface_owner", "fixture_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be blank")


@dataclass(frozen=True, slots=True)
class ComparisonPolicy:
    policy_id: str
    exact_size: bool
    max_changed_pixels: int
    max_channel_delta: int
    max_mean_delta: float
    mask_policy_id: str

    def __post_init__(self) -> None:
        if self.max_changed_pixels < 0:
            raise ValueError("max_changed_pixels must be nonnegative")
        if not 0 <= self.max_channel_delta <= 255:
            raise ValueError("max_channel_delta must be between 0 and 255")
        if self.max_mean_delta < 0:
            raise ValueError("max_mean_delta must be nonnegative")


STRICT_RGB_V1 = ComparisonPolicy(
    policy_id="strict-rgb-v1",
    exact_size=True,
    max_changed_pixels=0,
    max_channel_delta=0,
    max_mean_delta=0.0,
    mask_policy_id="none-v1",
)


@dataclass(frozen=True, slots=True)
class ComparisonMetrics:
    expected_width: int
    expected_height: int
    actual_width: int
    actual_height: int
    changed_pixels: int
    changed_percent: float
    max_channel_delta: int
    mean_absolute_delta: float
    bounding_box: tuple[int, int, int, int] | None


@dataclass(frozen=True, slots=True)
class VisualResult:
    outcome: VisualOutcome
    reason: OutcomeReason
    case_id: str
    metrics: ComparisonMetrics | None = None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class FontFingerprint:
    file_name: str
    byte_size: int
    sha256: str
    families: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.file_name or PathToken.is_unsafe(self.file_name):
            raise ValueError("font fingerprint must contain a safe filename")
        if self.byte_size <= 0:
            raise ValueError("font byte_size must be positive")
        if re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise ValueError("font sha256 must be lowercase hexadecimal")
        if not self.families or any(not family.strip() for family in self.families):
            raise ValueError("font families must not be empty")


class PathToken:
    """Tiny pure helper that keeps committed fingerprint values path-free."""

    @staticmethod
    def is_unsafe(value: str) -> bool:
        return "/" in value or "\\" in value or value in {".", ".."}


@dataclass(frozen=True, slots=True)
class RendererFingerprint:
    """Sanitized renderer facts that are safe to commit."""

    profile_id: str
    platform: str
    platform_release: str
    platform_version: str
    ci_image: str
    python: str
    pyside: str
    qt: str
    pillow: str
    qpa_platform: str
    qt_style: str
    qt_locale: str
    timezone: str
    logical_dpi: float
    device_pixel_ratio: float
    color_depth: int
    fonts: tuple[FontFingerprint, ...]
    icon_manifest_sha256: str
    design_system_version: str
    schema_version: str = FINGERPRINT_SCHEMA_VERSION

    def canonical_data(self) -> dict[str, Any]:
        return asdict(self)

    def canonical_bytes(self) -> bytes:
        return (
            json.dumps(
                self.canonical_data(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()
