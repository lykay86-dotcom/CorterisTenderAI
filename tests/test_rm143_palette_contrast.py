"""Expected RM-143 palette parity and sRGB contrast contract."""

from __future__ import annotations

import pytest

from app.ui.theme.colors import DARK_PALETTE, LIGHT_PALETTE
from app.ui.theme.contrast import approved_contrast_pairs, contrast_ratio, relative_luminance


def test_relative_luminance_and_ratio_use_srgb_math() -> None:
    assert relative_luminance("#000000") == 0.0
    assert relative_luminance("#FFFFFF") == 1.0
    assert contrast_ratio("#000000", "#FFFFFF") == 21.0
    assert contrast_ratio("#777777", "#FFFFFF") == pytest.approx(4.478, abs=0.002)


@pytest.mark.parametrize("palette", (DARK_PALETTE, LIGHT_PALETTE))
def test_every_approved_pair_meets_its_documented_threshold(palette) -> None:
    pairs = approved_contrast_pairs(palette)
    required = {
        "text_primary_on_app",
        "text_secondary_on_panel",
        "text_muted_on_card",
        "text_on_brand",
        "text_on_danger",
        "input_text",
        "disabled_text",
        "selection_text",
        "focus_ring",
        "semantic_info",
        "semantic_success",
        "semantic_warning",
        "semantic_danger",
    }
    assert required <= {pair.pair_id for pair in pairs}
    assert all(pair.ratio >= pair.minimum_ratio for pair in pairs)
