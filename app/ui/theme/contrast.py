"""WCAG-compatible sRGB contrast calculations and approved theme pairs."""

from __future__ import annotations

from dataclasses import dataclass

from app.ui.theme.colors import ThemePalette


def _rgb(color: str) -> tuple[float, float, float]:
    value = color.removeprefix("#")[:6]
    if len(value) != 6:
        raise ValueError(f"Expected #RRGGBB colour, got {color!r}")
    try:
        return tuple(int(value[index : index + 2], 16) / 255 for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError(f"Expected #RRGGBB colour, got {color!r}") from exc


def relative_luminance(color: str) -> float:
    """Return WCAG relative luminance for an sRGB colour."""

    channels = tuple(
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in _rgb(color)
    )
    return (0.2126 * channels[0]) + (0.7152 * channels[1]) + (0.0722 * channels[2])


def contrast_ratio(foreground: str, background: str) -> float:
    """Return the contrast ratio between two opaque sRGB colours."""

    first = relative_luminance(foreground)
    second = relative_luminance(background)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


@dataclass(frozen=True, slots=True)
class ContrastPair:
    pair_id: str
    foreground: str
    background: str
    minimum_ratio: float

    @property
    def ratio(self) -> float:
        return contrast_ratio(self.foreground, self.background)


def approved_contrast_pairs(palette: ThemePalette) -> tuple[ContrastPair, ...]:
    """Return audited text and non-text contrast pairs for a theme.

    Normal-size text uses 4.5:1. Disabled text and semantic/focus
    indicators use the WCAG non-text threshold of 3:1.
    """

    return (
        ContrastPair("text_primary_on_app", palette.text_primary, palette.app_background, 4.5),
        ContrastPair("text_secondary_on_panel", palette.text_secondary, palette.panel_background, 4.5),
        ContrastPair("text_muted_on_card", palette.text_muted, palette.card_background, 4.5),
        ContrastPair("text_on_brand", palette.text_on_brand, palette.brand_primary, 4.5),
        ContrastPair("text_on_danger", palette.text_on_danger, palette.danger, 4.5),
        ContrastPair("input_text", palette.text_primary, palette.input_background, 4.5),
        ContrastPair("disabled_text", palette.text_disabled, palette.input_background, 3.0),
        ContrastPair("selection_text", palette.text_primary, palette.selected_background, 4.5),
        ContrastPair("focus_ring", palette.focus_ring, palette.app_background, 3.0),
        ContrastPair("semantic_info", palette.info, palette.info_background, 3.0),
        ContrastPair("semantic_success", palette.success, palette.success_background, 3.0),
        ContrastPair("semantic_warning", palette.warning, palette.warning_background, 3.0),
        ContrastPair("semantic_danger", palette.danger, palette.danger_background, 3.0),
    )


__all__ = ["ContrastPair", "approved_contrast_pairs", "contrast_ratio", "relative_luminance"]
