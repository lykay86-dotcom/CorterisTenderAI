from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from app.equipment.catalog import EquipmentItem


@dataclass(slots=True)
class MatchResult:
    item: EquipmentItem
    score: float
    compliant: bool
    differences: list[str]


def _normalize(value: Any) -> str:
    return str(value).strip().lower().replace(",", ".")


def match_equipment(
    requirement: dict[str, Any], candidates: list[EquipmentItem], limit: int = 5
) -> list[MatchResult]:
    title = _normalize(requirement.get("name", ""))
    required = requirement.get("characteristics", {}) or {}
    results: list[MatchResult] = []
    for item in candidates:
        base = SequenceMatcher(
            None, title, _normalize(f"{item.brand} {item.model} {item.category}")
        ).ratio()
        differences: list[str] = []
        chars = item.characteristics or {}
        for key, expected in required.items():
            actual = chars.get(key)
            if actual is None:
                differences.append(f"{key}: отсутствует значение")
            elif _normalize(expected) != _normalize(actual):
                differences.append(f"{key}: требуется {expected}, предложено {actual}")
        compliant = not differences
        score = base + (0.25 if compliant else 0.0)
        results.append(
            MatchResult(
                item=item, score=min(score, 1.0), compliant=compliant, differences=differences
            )
        )
    return sorted(
        results, key=lambda x: (x.compliant, x.score, -x.item.purchase_price), reverse=True
    )[:limit]
