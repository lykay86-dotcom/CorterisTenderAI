"""Small validation helpers for native Qt semantics."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
import shiboken6


def require_accessible_name(widget: QWidget) -> str:
    """Return a non-empty accessible name or reject the incomplete control."""

    if not shiboken6.isValid(widget):
        raise ValueError("accessible name cannot be read from a deleted control")
    name = widget.accessibleName().strip()
    if not name:
        raise ValueError("accessible name is required for an icon-only control")
    return name


__all__ = ["require_accessible_name"]
