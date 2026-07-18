"""Expected RM-143 immutable/versioned design-token root."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.ui.theme import DESIGN_SYSTEM_VERSION, DESIGN_TOKENS
from app.ui.theme.tokens import (
    BorderWidth,
    ControlSize,
    IconSize,
    MotionDuration,
    Radius,
    Spacing,
)


def test_design_system_root_is_versioned_frozen_and_complete() -> None:
    assert DESIGN_SYSTEM_VERSION == "corteris-design-v1"
    assert DESIGN_TOKENS.version == DESIGN_SYSTEM_VERSION
    assert DESIGN_TOKENS.migration_matrix_version == "rm143-style-matrix-v1"
    assert DESIGN_TOKENS.transparent == "transparent"
    assert DESIGN_TOKENS.layout.page_margin >= Spacing.L

    with pytest.raises(FrozenInstanceError):
        DESIGN_TOKENS.version = "changed"  # type: ignore[misc]


def test_typed_scales_are_monotonic_and_bounded() -> None:
    assert list(Spacing) == sorted(Spacing, key=int)
    assert list(IconSize) == sorted(IconSize, key=int)
    assert BorderWidth.DEFAULT < BorderWidth.FOCUS <= BorderWidth.EMPHASIS
    assert Radius.SMALL < Radius.MEDIUM < Radius.LARGE < Radius.PILL
    assert MotionDuration.INSTANT < MotionDuration.FAST < MotionDuration.STANDARD
    assert set(DESIGN_TOKENS.controls) == {size.value for size in ControlSize}
    assert all(metric.height > 0 and metric.icon_size > 0 for metric in DESIGN_TOKENS.controls.values())
