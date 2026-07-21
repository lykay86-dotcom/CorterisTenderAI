"""Closed, typed RM-154 visual case catalog."""

from __future__ import annotations

from .contracts import VisualCase, Viewport


SHELL_VIEWPORT = Viewport(1540, 940)
GALLERY_VIEWPORT = Viewport(1200, 900)
DIALOG_VIEWPORT = Viewport(1000, 800)


def _paired(
    base: str,
    *,
    surface_owner: str,
    fixture_id: str,
    viewport: Viewport,
    native_evidence_required: bool = False,
) -> tuple[VisualCase, VisualCase]:
    return tuple(
        VisualCase(
            case_id=f"{base}.{theme}.canonical",
            surface_owner=surface_owner,
            fixture_id=fixture_id,
            theme=theme,
            viewport=viewport,
            native_evidence_required=native_evidence_required,
        )
        for theme in ("dark", "light")
    )  # type: ignore[return-value]


VISUAL_CASES = tuple(
    sorted(
        (
            *_paired(
                "component.gallery.core",
                surface_owner="ComponentGallery",
                fixture_id="component-gallery-core-v1",
                viewport=GALLERY_VIEWPORT,
            ),
            *_paired(
                "dashboard.ready",
                surface_owner="DashboardPage",
                fixture_id="shell-dashboard-ready-v1",
                viewport=SHELL_VIEWPORT,
            ),
            *_paired(
                "dialog.participation.critical-stop",
                surface_owner="TenderParticipationScoreDialog",
                fixture_id="participation-critical-stop-v1",
                viewport=DIALOG_VIEWPORT,
                native_evidence_required=True,
            ),
            *_paired(
                "shell.analytics.empty",
                surface_owner="ModernMainWindow",
                fixture_id="shell-analytics-empty-v1",
                viewport=SHELL_VIEWPORT,
            ),
            *_paired(
                "shell.dashboard.empty",
                surface_owner="ModernMainWindow",
                fixture_id="shell-dashboard-empty-v1",
                viewport=SHELL_VIEWPORT,
            ),
            *_paired(
                "shell.tenders.empty",
                surface_owner="ModernMainWindow",
                fixture_id="shell-tenders-empty-v1",
                viewport=SHELL_VIEWPORT,
            ),
            *_paired(
                "shell.workflow.empty",
                surface_owner="ModernMainWindow",
                fixture_id="shell-workflow-empty-v1",
                viewport=SHELL_VIEWPORT,
            ),
        ),
        key=lambda case: case.case_id,
    )
)


def case_by_id(case_id: str) -> VisualCase:
    matches = tuple(case for case in VISUAL_CASES if case.case_id == case_id)
    if len(matches) != 1:
        raise KeyError(case_id)
    return matches[0]
