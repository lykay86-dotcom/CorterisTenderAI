# RM-115 Requirements — Strict Tender Intelligence JSON Schema

Status: APPROVED FOR IMPLEMENTATION  
Canonical contract date: 2026-07-14  
Depends on: RM-107, RM-110, RM-111, RM-112, RM-113, RM-114

## Goal

RM-115 creates one strict raw-output contract for Tender Intelligence. OpenAI and generic
`openai_compatible` requests use Responses API `text.format`; every provider, including
Ollama, is validated locally against the same fail-closed contract before any AI finding is
created.

## Architecture and non-negotiable invariants

- Reuse one `OpenAICompatibleProvider`, one `TenderDocumentAiAnalyzer`, one
  `TenderAiOrchestrator`, one `AiDocumentAnalysisRepository`, and the current DI/bootstrap.
- Keep exactly one production `provider.analyze()` call.
- Keep RM-107 as the only owner of score/recommendation and preserve absolute critical
  stop-factor priority.
- Preserve deterministic fallback when AI is disabled, unavailable, or rejected.
- Keep bootstrap, settings load, and settings save offline and keep business logic out of UI.
- Do not create a transport, pipeline, provider ID, analyzer, orchestrator, repository,
  Decision Engine, database, table, migration, or persisted schema.
- Do not use `app/ai/structured_analysis.py` as a production workflow.
- Do not add Chat Completions, `response_format`, tools, streaming, retry/backoff/failover,
  capability probes, a second request, or a strict-schema UI toggle.

## Canonical provider-output module

Create `app/core/ai/output_schema.py` using installed Pydantic v2 and no new dependency.
Public elements are:

- `AI_PROVIDER_OUTPUT_SCHEMA_VERSION = "1"`;
- `AI_RESPONSE_FORMAT_NAME = "corteris_tender_analysis_v1"`;
- `ProviderAnalysisPayload`;
- `build_provider_output_json_schema()`;
- `build_responses_text_format()`;
- `decode_and_validate_provider_output()`.

All Pydantic models use strict validation and `extra="forbid"`. Every key is required;
strings and arrays have explicit local bounds; types are never coerced. The generated schema
is deterministic, contains no defaults, has no root `anyOf`, and sets
`additionalProperties=false` on every object. The Pydantic models are the only hand-authored
source of the provider JSON Schema.

The exact root fields are `summary`, `requirements`, `risks`, `suspicious_conditions`,
`contradictions`, `missing_documents`, and `final_ai_conclusion`. `requirements` contains all
and only the eleven `TenderRequirements.__dataclass_fields__` keys in their declared order.

Every finding contains exactly `statement`, `document_id`, `quote`, `section`, `page`, and
`confidence`. `page` is integer or null; `confidence` is a strict finite number from 0 to 1.
Unknown section/page values are represented by `""`/`null`; absent facts use empty strings or
arrays.

Provider output and its schema must not contain `verified`, `unverified`, `status`, `category`,
`registry_key`, `payload_version`, `created_at`, `warnings`, `context`, `score`,
`recommendation`, participation decisions, or critical stop-factor results.

## Strict decoder

`decode_and_validate_provider_output()` accepts only `str`, `bytes`, or `bytearray`, decodes
UTF-8, and accepts exactly one JSON object. It rejects markdown fences, prefix/suffix text,
arrays/scalars/null, invalid UTF-8, duplicate object keys, NaN/Infinity, absent/unknown keys,
wrong types, booleans used as numbers, string page/confidence, and exceeded string/array
limits. Duplicate keys use `object_pairs_hook` or equivalent; non-finite constants use
`parse_constant` or equivalent. It never searches for the first/last brace.

The function returns a validated `ProviderAnalysisPayload` or one safe invalid sentinel. It
must not expose raw response data, Pydantic `ValidationError`, exception text, or payload
fragments to callers, results, warnings, or logs.

## Provider interface and request policy

Extend `AIProvider.analyze()` minimally:

```python
def analyze(
    self,
    prompt: str,
    documents: list[str],
    *,
    output_format: Mapping[str, object] | None = None,
) -> dict[str, object]:
```

Update `DisabledProvider`, `OpenAICompatibleProvider`, and every relevant provider test double
directly. Do not catch `TypeError` to emulate the old signature.

`OpenAICompatibleProvider` receives explicit `supports_text_format: bool = True`. When
`output_format` is supplied and support is enabled, the request contains the exact supplied
mapping as `text.format`. The provider does not mutate the mapping and does not validate
Tender Intelligence semantics. Existing `model`, `input`, `stream=false`, cloud
`store=false`, one-request execution, safe output extraction, and RM-114 security limits
remain intact.

- OpenAI: `supports_text_format=True`; send `text.format`; retain `store=false`.
- `openai_compatible`: `supports_text_format=True`; use the same request. Incompatibility is
  the existing safe error, without downgrade or second request.
- Ollama: `supports_text_format=False`; send only its confirmed `model`, `input`, `stream`
  subset; omit `text` and `store`; never read cloud keyring.
- Disabled provider: no network and unchanged fallback.

## Analyzer and evidence boundary

`TenderDocumentAiAnalyzer` passes `SYSTEM_PROMPT`, current rendered documents, and
`build_responses_text_format()` to the one provider call. For a provider `status="ok"`, it
uses only `decode_and_validate_provider_output()`; ordinary lenient `json.loads` is removed
from this boundary.

Any structural or schema error returns `AiAnalysisStatus.INVALID_RESPONSE` with zero risks,
requirements, contradictions, or other AI findings. No partially accepted structural payload
is allowed.

After structural success, the validated payload enters the existing local normalization.
Finding categories derive only from their local buckets. A finding becomes verified only when
its `document_id` is known, its quote is non-empty and occurs exactly and continuously in the
local document text, and confidence is valid. Unknown documents, empty/false quotes, or other
evidence mismatch remain unverified and may produce `PARTIAL`. AI-supplied verification,
status, or category is impossible by schema.

The existing Orchestrator exception boundary and safe constant warnings remain unchanged.

## Prompt and versions

Set `AI_PROMPT_VERSION = "2"`. `SYSTEM_PROMPT` requires one bare JSON object, no markdown or
explanation, every required root and requirement key, only supplied document IDs, continuous
exact quotes, `page=null`/`section=""` when unknown, empty values instead of guesses, and no
invented facts, verification claims, score, recommendation, or participation decision.

Set `AI_ANALYZER_VERSION = "3"`. Keep `AI_ANALYSIS_SCHEMA_VERSION = 2` because the persisted
`AiDocumentAnalysis.to_payload()` contract does not change.

Add `AI_PROVIDER_OUTPUT_SCHEMA_VERSION` to the fingerprint version map. Prompt, analyzer, or
provider-output schema changes must alter the fingerprint, so old lenient results cannot be
reused. Existing SQLite rows remain readable as history and no migration is created.

## UI, export, RM-107, and security

UI and exporters continue to receive the same domain payload. An invalid strict response uses
the existing `invalid_response` status and constant warning while deterministic analysis
continues. Raw provider output must not appear in UI, JSON/HTML export, repository, or logs.
The current-run invalid result must not be replaced by stale success, and only validated,
locally verified current-run evidence may reach RM-107.

No error or log may expose an API key, Authorization header, base URL/query, prompt, document
text, raw response/refusal, output schema payload, Pydantic error, traceback, Windows username,
private path, or SQLite payload. All RM-115 tests remain offline without DNS, live OpenAI or
Ollama, host keyring, or stored credentials.

## Required tests and acceptance

Create `tests/test_ai_output_schema.py` for recursive schema invariants, deterministic schema
generation, domain-key parity, strict valid payloads, and every requested decoder rejection.
Update analyzer, provider, provider-selection/Ollama, repository/fingerprint, runtime, UI,
export, RM-107, and stop-factor regression tests described in the RM-115 task contract.

The final target command includes:

```text
tests/test_ai_output_schema.py
tests/test_ai_document_analyzer.py
tests/test_ai_document_schemas.py
tests/test_openai_compatible_provider.py
tests/test_ai_provider_selection.py
tests/test_ollama_local_mode.py
tests/test_ai_document_analysis_repository.py
tests/test_ai_document_analysis_service.py
tests/test_ai_orchestrator.py
tests/test_ai_orchestrator_runtime_integration.py
tests/test_full_analysis_service.py
tests/test_tender_analysis_runtime_integration.py
tests/test_bootstrap_tender_search_integration.py
tests/test_tender_full_analysis_dialog.py
tests/test_tender_ai_analysis_export.py
```

After the target contour, run full pytest, Ruff check, Ruff format check, mypy, repository
secret scan, `pip_audit --skip-editable`, and `git diff --check`. The mandatory mypy contour
must include `app/core/ai/output_schema.py`, `app/core/ai/analyzer.py`, and
`app/core/ai/schemas.py`. Record Python version, exact results, and durations in this file.

## Local baseline — 2026-07-14

- Python: `3.12.7`.
- Existing target contour: `191 passed in 5.97s`; wall time `7.06s`.
- Full pytest: `863 passed in 57.85s`; wall time `59.26s`.
- A prior host-temp attempt produced `121 passed, 70 errors`; all errors were sandbox
  `PermissionError` failures creating pytest temp paths, not application failures. Redirecting
  `TEMP/TMP` into the worktree produced the successful results above.

## Completion boundary

Local success makes RM-115 ready for review, not DONE. The feature PR title is
`feat(rm-115): enforce strict Tender Intelligence JSON schema`. RM-115 may be marked DONE and
RM-116 activated only after feature merge and successful post-merge Windows Quality Gate on
Python 3.12 and 3.13. That later completion update must record merge SHA, PR number, run ID,
matrix results, and the required roadmap history changes.

