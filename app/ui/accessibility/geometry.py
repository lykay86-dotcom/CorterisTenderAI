"""Qt-free deterministic screen-geometry recovery contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("rectangle dimensions must be positive")

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def intersection_area(self, other: Rect) -> int:
        width = max(0, min(self.right, other.right) - max(self.x, other.x))
        height = max(0, min(self.bottom, other.bottom) - max(self.y, other.y))
        return width * height


def clamp_rect_to_screens(
    rect: Rect,
    *,
    screens: tuple[Rect, ...],
    minimum_size: tuple[int, int],
) -> Rect:
    """Clamp saved logical geometry to the best currently available screen."""

    if not screens:
        raise ValueError("at least one available screen is required")
    minimum_width, minimum_height = minimum_size
    if minimum_width <= 0 or minimum_height <= 0:
        raise ValueError("minimum size must be positive")

    screen = max(screens, key=lambda candidate: rect.intersection_area(candidate))
    width = min(max(rect.width, min(minimum_width, screen.width)), screen.width)
    height = min(max(rect.height, min(minimum_height, screen.height)), screen.height)
    maximum_x = screen.right - width
    maximum_y = screen.bottom - height
    x = min(max(rect.x, screen.x), maximum_x)
    y = min(max(rect.y, screen.y), maximum_y)
    return Rect(x, y, width, height)


__all__ = ["Rect", "clamp_rect_to_screens"]
