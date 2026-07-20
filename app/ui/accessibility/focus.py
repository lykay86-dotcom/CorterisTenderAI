"""Live-target focus helpers that preserve existing navigation/dialog ownership."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
import shiboken6


def is_valid_focus_target(widget: QWidget | None) -> bool:
    """Return whether a live, visible, enabled QWidget may receive keyboard focus."""

    if widget is None or not shiboken6.isValid(widget):
        return False
    return (
        widget.isVisible() and widget.isEnabled() and widget.focusPolicy() != Qt.FocusPolicy.NoFocus
    )


def restore_focus(
    preferred: QWidget | None,
    fallback: QWidget | None = None,
    *,
    reason: Qt.FocusReason = Qt.FocusReason.OtherFocusReason,
) -> QWidget | None:
    """Focus the exact live target, otherwise one explicit logical fallback."""

    for candidate in (preferred, fallback):
        if is_valid_focus_target(candidate):
            assert candidate is not None
            candidate.setFocus(reason)
            return candidate
    return None


__all__ = ["is_valid_focus_target", "restore_focus"]
