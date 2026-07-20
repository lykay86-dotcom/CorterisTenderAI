"""Machine-readable RM-152 semantic contrast inventory."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.ui.theme.colors import ThemePalette
from app.ui.theme.contrast import contrast_ratio


@dataclass(frozen=True, slots=True)
class ContrastAuditSpec:
    pair_id: str
    foreground_token: str
    background_token: str
    minimum_ratio: float | None
    surface: str
    alternative: str


CONTRAST_AUDIT_SPECS = (
    ContrastAuditSpec(
        "text_primary_on_app", "text_primary", "app_background", 4.5, "shell", "text"
    ),
    ContrastAuditSpec(
        "text_secondary_on_panel", "text_secondary", "panel_background", 4.5, "panel", "text"
    ),
    ContrastAuditSpec("text_muted_on_card", "text_muted", "card_background", 4.5, "card", "text"),
    ContrastAuditSpec(
        "text_on_brand", "text_on_brand", "brand_primary", 4.5, "primary_action", "text"
    ),
    ContrastAuditSpec(
        "text_on_danger", "text_on_danger", "danger", 4.5, "destructive_action", "text"
    ),
    ContrastAuditSpec(
        "input_text", "text_primary", "input_background", 4.5, "form_control", "label"
    ),
    ContrastAuditSpec(
        "placeholder_text",
        "text_muted",
        "input_background",
        None,
        "form_control",
        "advisory hint only; persistent label and accessible name carry meaning",
    ),
    ContrastAuditSpec(
        "disabled_text",
        "text_disabled",
        "input_background",
        3.0,
        "disabled_control",
        "disabled state",
    ),
    ContrastAuditSpec(
        "selection_text",
        "text_primary",
        "selected_background",
        4.5,
        "selection",
        "selected state",
    ),
    ContrastAuditSpec(
        "focus_on_app", "focus_ring", "app_background", 3.0, "shell", "keyboard focus state"
    ),
    ContrastAuditSpec(
        "focus_on_panel", "focus_ring", "panel_background", 3.0, "panel", "keyboard focus state"
    ),
    ContrastAuditSpec(
        "focus_on_card", "focus_ring", "card_background", 3.0, "card", "keyboard focus state"
    ),
    ContrastAuditSpec(
        "focus_on_input",
        "focus_ring",
        "input_background",
        3.0,
        "form_control",
        "keyboard focus state",
    ),
    ContrastAuditSpec(
        "focus_on_selection",
        "focus_ring",
        "selected_background",
        3.0,
        "selected_row",
        "selection and keyboard focus states",
    ),
    ContrastAuditSpec(
        "focus_on_danger",
        "focus_ring",
        "danger_background",
        3.0,
        "danger_status",
        "keyboard focus and danger text",
    ),
    ContrastAuditSpec(
        "focus_on_warning",
        "focus_ring",
        "warning_background",
        3.0,
        "warning_status",
        "keyboard focus and warning text",
    ),
    ContrastAuditSpec(
        "invalid_boundary",
        "danger",
        "input_background",
        3.0,
        "invalid_control",
        "error text and invalid state",
    ),
    ContrastAuditSpec(
        "semantic_info", "info", "info_background", 3.0, "status", "info text and icon"
    ),
    ContrastAuditSpec(
        "semantic_success",
        "success",
        "success_background",
        3.0,
        "status",
        "success text and icon",
    ),
    ContrastAuditSpec(
        "semantic_warning",
        "warning",
        "warning_background",
        3.0,
        "status",
        "warning text and icon",
    ),
    ContrastAuditSpec(
        "semantic_danger",
        "danger",
        "danger_background",
        3.0,
        "status",
        "danger text and icon",
    ),
    ContrastAuditSpec(
        "semantic_neutral",
        "neutral",
        "neutral_background",
        3.0,
        "status",
        "neutral text and icon",
    ),
    ContrastAuditSpec(
        "chart_axis",
        "chart_axis",
        "card_background",
        3.0,
        "chart",
        "axis labels and full data table",
    ),
    ContrastAuditSpec(
        "chart_grid",
        "chart_grid",
        "card_background",
        None,
        "chart",
        "decorative grid; axis labels and full data table carry meaning",
    ),
)


def build_contrast_inventory(palette: ThemePalette) -> tuple[dict[str, object], ...]:
    """Serialize audited pairs while keeping advisory pairs distinct from passes."""

    rows: list[dict[str, object]] = []
    for spec in CONTRAST_AUDIT_SPECS:
        foreground = getattr(palette, spec.foreground_token)
        background = getattr(palette, spec.background_token)
        ratio = contrast_ratio(foreground, background)
        result = (
            "ADVISORY"
            if spec.minimum_ratio is None
            else "PASS"
            if ratio >= spec.minimum_ratio
            else "FAIL"
        )
        row = asdict(spec)
        row.update(
            theme=palette.name.value,
            foreground=foreground,
            background=background,
            measured_ratio=round(ratio, 3),
            result=result,
        )
        rows.append(row)
    return tuple(rows)


__all__ = ["CONTRAST_AUDIT_SPECS", "ContrastAuditSpec", "build_contrast_inventory"]
