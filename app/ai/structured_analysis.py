"""Deprecated JSON/citation helpers retained for v1.4 compatibility tests.

Production AI execution is owned by ``app.core.ai``.  This module deliberately
contains no provider call, score, recommendation, persistence, or orchestration.
"""

from __future__ import annotations

import json
import re
from typing import Any


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def validate_citations(payload: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for bucket in ("risks", "competition_flags", "contradictions"):
        for i, item in enumerate(payload.get(bucket, []) or []):
            source = item.get("source") or {}
            if not source.get("source_document"):
                problems.append(f"{bucket}[{i}]: отсутствует source_document")
            if not source.get("quote"):
                problems.append(f"{bucket}[{i}]: отсутствует quote")
    return problems


__all__ = ["_extract_json", "validate_citations"]
