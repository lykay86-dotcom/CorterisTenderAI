"""Typography system for Corteris Tender AI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Final


class FontWeight(IntEnum):
    LIGHT = 300
    REGULAR = 400
    MEDIUM = 500
    SEMIBOLD = 600
    BOLD = 700


@dataclass(frozen=True, slots=True)
class FontToken:
    family: str
    size: int
    weight: FontWeight
    line_height: int

    def css(self) -> str:
        return (
            f"font-family:'{self.family}';font-size:{self.size}pt;font-weight:{int(self.weight)};"
        )


class Typography:
    FAMILY: Final[str] = "Segoe UI"

    DISPLAY = FontToken(FAMILY, 28, FontWeight.BOLD, 36)
    H1 = FontToken(FAMILY, 22, FontWeight.BOLD, 30)
    H2 = FontToken(FAMILY, 18, FontWeight.SEMIBOLD, 26)
    H3 = FontToken(FAMILY, 16, FontWeight.SEMIBOLD, 24)

    BODY_L = FontToken(FAMILY, 12, FontWeight.REGULAR, 20)
    BODY_M = FontToken(FAMILY, 11, FontWeight.REGULAR, 18)
    BODY_S = FontToken(FAMILY, 10, FontWeight.REGULAR, 16)

    CAPTION = FontToken(FAMILY, 9, FontWeight.REGULAR, 14)
    BUTTON = FontToken(FAMILY, 11, FontWeight.SEMIBOLD, 18)
    CODE = FontToken("Consolas", 10, FontWeight.REGULAR, 16)

    @staticmethod
    def scale(token: FontToken, factor: float) -> FontToken:
        if factor <= 0:
            raise ValueError("factor must be > 0")
        return FontToken(
            family=token.family,
            size=max(1, round(token.size * factor)),
            weight=token.weight,
            line_height=max(1, round(token.line_height * factor)),
        )


__all__ = ["FontToken", "FontWeight", "Typography"]
