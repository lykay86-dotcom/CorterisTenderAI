"""Bounded native accessibility helpers for existing UI owners."""

from app.ui.accessibility.focus import is_valid_focus_target, restore_focus
from app.ui.accessibility.geometry import Rect, clamp_rect_to_screens
from app.ui.accessibility.native_matrix import validate_native_matrix
from app.ui.accessibility.semantics import require_accessible_name

__all__ = [
    "Rect",
    "clamp_rect_to_screens",
    "is_valid_focus_target",
    "require_accessible_name",
    "restore_focus",
    "validate_native_matrix",
]
