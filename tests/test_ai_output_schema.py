from __future__ import annotations

import json
from typing import Any

import pytest

from app.core.ai.output_schema import (
    AI_PROVIDER_OUTPUT_SCHEMA_VERSION,
    AI_RESPONSE_FORMAT_NAME,
    ProviderAnalysisPayload,
    build_provider_output_json_schema,
    build_responses_text_format,
    decode_and_validate_provider_output,
)
from app.core.ai.prompts import SYSTEM_PROMPT
from app.core.ai.schemas import TenderRequirements


ROOT_KEYS = {
    "summary",
    "requirements",
    "technical_specification",
    "risks",
    "suspicious_conditions",
    "contradictions",
    "missing_documents",
    "final_ai_conclusion",
}
REQUIREMENT_KEYS = tuple(TenderRequirements.__dataclass_fields__)
TECHNICAL_SPECIFICATION_KEYS = (
    "scope",
    "deliverables",
    "quantities_and_volumes",
    "technical_characteristics",
    "materials_and_equipment",
    "standards_and_regulations",
    "execution_conditions",
    "stages_and_deadlines",
    "acceptance_and_quality",
    "customer_inputs_and_dependencies",
    "ambiguities",
    "contradictions",
    "clarification_points",
)
FINDING_KEYS = {"statement", "document_id", "quote", "section", "page", "confidence"}


def _valid_payload() -> dict[str, Any]:
    return {
        "summary": "",
        "requirements": {name: [] for name in REQUIREMENT_KEYS},
        "technical_specification": {name: [] for name in TECHNICAL_SPECIFICATION_KEYS},
        "risks": [],
        "suspicious_conditions": [],
        "contradictions": [],
        "missing_documents": [],
        "final_ai_conclusion": "",
    }


def _finding(**overrides: object) -> dict[str, object]:
    return {
        "statement": "Delivery deadline",
        "document_id": "doc-1",
        "quote": "delivery period is 10 days",
        "section": "",
        "page": None,
        "confidence": 0.8,
        **overrides,
    }


def _walk_objects(value: object) -> list[dict[str, object]]:
    objects: list[dict[str, object]] = []
    if isinstance(value, dict):
        if value.get("type") == "object" or "properties" in value:
            objects.append(value)
        for item in value.values():
            objects.extend(_walk_objects(item))
    elif isinstance(value, list):
        for item in value:
            objects.extend(_walk_objects(item))
    return objects


def test_schema_name_version_and_responses_format_are_stable() -> None:
    schema = build_provider_output_json_schema()

    assert AI_PROVIDER_OUTPUT_SCHEMA_VERSION == "2"
    assert AI_RESPONSE_FORMAT_NAME == "corteris_tender_analysis_v2"
    assert build_responses_text_format() == {
        "type": "json_schema",
        "name": AI_RESPONSE_FORMAT_NAME,
        "strict": True,
        "schema": schema,
    }


def test_schema_is_deterministic_strict_and_matches_domain_buckets() -> None:
    first = build_provider_output_json_schema()
    second = build_provider_output_json_schema()

    assert first == second
    assert first["type"] == "object"
    assert "anyOf" not in first
    assert set(first["properties"]) == ROOT_KEYS
    assert set(first["required"]) == ROOT_KEYS
    requirements = first["properties"]["requirements"]
    assert requirements["$ref"].endswith("/ProviderRequirementsPayload")
    requirement_model = first["$defs"]["ProviderRequirementsPayload"]
    assert tuple(requirement_model["properties"]) == REQUIREMENT_KEYS
    assert set(requirement_model["required"]) == set(REQUIREMENT_KEYS)
    technical_model = first["$defs"]["ProviderTechnicalSpecificationPayload"]
    assert tuple(technical_model["properties"]) == TECHNICAL_SPECIFICATION_KEYS
    assert set(technical_model["required"]) == set(TECHNICAL_SPECIFICATION_KEYS)

    for object_schema in _walk_objects(first):
        assert object_schema["additionalProperties"] is False
        assert set(object_schema["required"]) == set(object_schema["properties"])


def test_schema_finding_contract_is_bounded_nullable_and_has_no_internal_fields() -> None:
    schema = build_provider_output_json_schema()
    finding = schema["$defs"]["ProviderFindingPayload"]
    page = finding["properties"]["page"]
    confidence = finding["properties"]["confidence"]
    rendered = json.dumps(schema, ensure_ascii=False, sort_keys=True)

    assert set(finding["properties"]) == FINDING_KEYS
    assert {item["type"] for item in page["anyOf"]} == {"integer", "null"}
    assert confidence["type"] == "number"
    assert confidence["minimum"] == 0
    assert confidence["maximum"] == 1
    assert finding["properties"]["statement"]["maxLength"] == 4_000
    assert finding["properties"]["quote"]["maxLength"] == 8_000
    assert "default" not in rendered
    for forbidden in (
        "verified",
        "unverified",
        "status",
        "category",
        "registry_key",
        "payload_version",
        "created_at",
        "warnings",
        "context",
        "score",
        "recommendation",
        "participation_decision",
        "critical_stop_factor",
        "citation_id",
        "provenance",
        "source_registry",
        "character_start",
        "character_end",
        "checksum_sha256",
        "context_fingerprint",
    ):
        assert f'"{forbidden}"' not in rendered


def test_prompt_keeps_provider_output_candidate_only_and_locators_as_hints() -> None:
    prompt = SYSTEM_PROMPT.casefold()

    assert "exact continuous quote" in prompt
    assert "exactly one json object" in prompt
    assert "page and section are optional hints" in prompt
    assert "local application code" in prompt
    for forbidden_output in ("links", "citation ids", "provenance"):
        assert f"do not return {forbidden_output}" in prompt


def test_decoder_accepts_minimal_and_full_valid_payloads() -> None:
    minimal = _valid_payload()
    full = _valid_payload()
    full["summary"] = "Summary"
    full["requirements"]["deadlines"] = [_finding(page=3, confidence=1)]
    full["risks"] = [_finding(statement="Risk", confidence=0.0)]
    full["suspicious_conditions"] = [_finding(statement="Condition")]
    full["contradictions"] = [_finding(statement="Contradiction")]
    full["missing_documents"] = ["Appendix 1"]
    full["final_ai_conclusion"] = "Conclusion"

    decoded_minimal = decode_and_validate_provider_output(json.dumps(minimal))
    decoded_full = decode_and_validate_provider_output(
        json.dumps(full, ensure_ascii=False).encode("utf-8")
    )

    assert isinstance(decoded_minimal, ProviderAnalysisPayload)
    assert isinstance(decoded_full, ProviderAnalysisPayload)
    assert decoded_full.requirements.deadlines[0].page == 3
    assert decoded_full.risks[0].confidence == 0.0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.pop("summary"),
        lambda payload: payload.update({"unknown": True}),
        lambda payload: payload["requirements"].pop("equipment"),
        lambda payload: payload["requirements"].update({"unknown": []}),
        lambda payload: payload.update({"requirements": []}),
        lambda payload: payload.update({"risks": {}}),
        lambda payload: payload.update({"summary": 42}),
        lambda payload: payload.update({"missing_documents": [42]}),
    ],
)
def test_decoder_rejects_missing_extra_and_wrong_container_or_scalar_types(mutate) -> None:
    payload = _valid_payload()
    mutate(payload)

    assert decode_and_validate_provider_output(json.dumps(payload)) is None


@pytest.mark.parametrize(
    "finding",
    [
        {key: value for key, value in _finding().items() if key != "quote"},
        {**_finding(), "unknown": True},
        _finding(confidence="0.8"),
        _finding(confidence=True),
        _finding(page="1"),
        _finding(page=True),
        _finding(page=0),
        _finding(page=-1),
        _finding(page=1.5),
    ],
)
def test_decoder_rejects_invalid_finding_shapes_and_strict_numeric_types(finding) -> None:
    payload = _valid_payload()
    payload["risks"] = [finding]

    assert decode_and_validate_provider_output(json.dumps(payload)) is None


@pytest.mark.parametrize(
    "raw",
    [
        "[]",
        '"text"',
        "42",
        "null",
        "```json\n{}\n```",
        "prefix {}",
        "{} suffix",
        '{"summary": "a", "summary": "b"}',
        '{"value": NaN}',
        '{"value": Infinity}',
        '{"value": -Infinity}',
    ],
)
def test_decoder_rejects_non_object_wrappers_duplicate_keys_and_non_finite_numbers(raw) -> None:
    assert decode_and_validate_provider_output(raw) is None


def test_decoder_rejects_duplicate_keys_at_nested_depth() -> None:
    raw = json.dumps(_valid_payload()).replace(
        '"equipment": []',
        '"equipment": [], "equipment": []',
        1,
    )

    assert decode_and_validate_provider_output(raw) is None


@pytest.mark.parametrize("value", [None, {}, [], 1, object(), b"\xff", bytearray(b"\xff")])
def test_decoder_rejects_unsupported_input_and_invalid_utf8(value: object) -> None:
    assert decode_and_validate_provider_output(value) is None


def test_decoder_rejects_oversized_strings_and_arrays() -> None:
    oversized_summary = _valid_payload()
    oversized_summary["summary"] = "s" * 12_001
    oversized_statement = _valid_payload()
    oversized_statement["risks"] = [_finding(statement="x" * 4_001)]
    oversized_array = _valid_payload()
    oversized_array["risks"] = [_finding() for _ in range(201)]

    assert decode_and_validate_provider_output(json.dumps(oversized_summary)) is None
    assert decode_and_validate_provider_output(json.dumps(oversized_statement)) is None
    assert decode_and_validate_provider_output(json.dumps(oversized_array)) is None
