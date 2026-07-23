"""Canonical contractor identity values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Self


class ContractorInnKind(StrEnum):
    ORGANIZATION = "organization"
    INDIVIDUAL = "individual"


@dataclass(frozen=True, slots=True, init=False)
class ContractorInn:
    value: str

    def __init__(self, value: object) -> None:
        object.__setattr__(self, "value", _canonical_inn(value))

    @classmethod
    def parse(cls, value: object) -> Self:
        return cls(value)

    @property
    def kind(self) -> ContractorInnKind:
        if len(self.value) == 10:
            return ContractorInnKind.ORGANIZATION
        return ContractorInnKind.INDIVIDUAL


def _canonical_inn(value: object) -> str:
    if type(value) is not str:
        raise TypeError("contractor INN must be a string")
    rendered = value.strip()
    if re.fullmatch(r"[0-9]{10}|[0-9]{12}", rendered) is None:
        raise ValueError("contractor INN must contain exactly 10 or 12 ASCII digits")
    digits = tuple(int(character) for character in rendered)
    if len(digits) == 10:
        expected = _check_digit(digits[:9], (2, 4, 10, 3, 5, 9, 4, 6, 8))
        valid = digits[9] == expected
    else:
        first = _check_digit(digits[:10], (7, 2, 4, 10, 3, 5, 9, 4, 6, 8))
        second = _check_digit(digits[:11], (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8))
        valid = digits[10] == first and digits[11] == second
    if not valid:
        raise ValueError("contractor INN checksum is invalid")
    return rendered


def _check_digit(digits: tuple[int, ...], weights: tuple[int, ...]) -> int:
    return sum(digit * weight for digit, weight in zip(digits, weights, strict=True)) % 11 % 10


__all__ = ["ContractorInn", "ContractorInnKind"]
