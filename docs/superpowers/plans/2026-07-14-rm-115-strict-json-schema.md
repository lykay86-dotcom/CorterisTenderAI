# RM-115 Strict Tender Intelligence JSON Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce one canonical strict raw Tender Intelligence JSON contract for every AI provider while preserving the existing provider/analyzer/orchestrator/repository/Decision Engine graph.

**Architecture:** A new Pydantic v2 boundary module is the only source for both local validation and the Responses API JSON Schema. The existing provider optionally forwards that generated format, while the existing analyzer always validates locally before evidence normalization. Prompt/analyzer/provider-schema versions invalidate the previous lenient cache without changing persisted payloads or SQLite.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, urllib Responses API adapter, SQLite repository, Ruff, mypy.

## Global Constraints

- Active stage is RM-115 only; RM-116 and RM-117 remain out of scope.
- Keep one `OpenAICompatibleProvider`, one `TenderDocumentAiAnalyzer`, one `TenderAiOrchestrator`, one `AiDocumentAnalysisRepository`, and one production `provider.analyze()` call.
- Keep `AI_ANALYSIS_SCHEMA_VERSION = 2`; add no dependency, database, migration, provider ID, retry, fallback endpoint, streaming, tool call, capability probe, UI toggle, or Decision Engine change.
- Provider output cannot control verification, status, category, score, recommendation, participation decision, or critical stop-factor state.
- Never expose raw provider output, prompt, documents, credentials, URL/query, exception text, Pydantic errors, traceback, private paths, or SQLite payloads.
- All tests and checks run offline with `TEMP/TMP` redirected inside the worktree when required by the managed filesystem.

---

### Task 1: Canonical provider-output schema and strict decoder

**Files:**
- Create: `app/core/ai/output_schema.py`
- Create: `tests/test_ai_output_schema.py`

**Interfaces:**
- Produces: `AI_PROVIDER_OUTPUT_SCHEMA_VERSION: str`, `AI_RESPONSE_FORMAT_NAME: str`, `ProviderAnalysisPayload`, `build_provider_output_json_schema() -> dict[str, object]`, `build_responses_text_format() -> dict[str, object]`, and `decode_and_validate_provider_output(value: object) -> ProviderAnalysisPayload | None`.
- Consumes: `TenderRequirements.__dataclass_fields__` only in tests for parity; production schema stays independently typed but must use the same exact eleven names.

- [ ] **Step 1: Write schema-contract tests that fail because the module is absent**

  Cover stable name/version, deterministic generation, root object/no root `anyOf`, exact required root and requirements keys, recursive `required == properties`, recursive `additionalProperties == false`, nullable page, bounded confidence, absence of defaults/internal fields, and parity with `TenderRequirements`.

- [ ] **Step 2: Run the schema tests and verify RED**

  Run: `python -m pytest -q tests/test_ai_output_schema.py`

  Expected: collection failure for missing `app.core.ai.output_schema`.

- [ ] **Step 3: Implement strict Pydantic models and deterministic schema generation**

  Use `ConfigDict(strict=True, extra="forbid")`, constrained strict strings, constrained strict integers/floats, and bounded lists. Define every field without defaults. Generate schema only through `ProviderAnalysisPayload.model_json_schema()` and remove no constraints except metadata that the Responses subset does not need. Build:

  ```python
  def build_responses_text_format() -> dict[str, object]:
      return {
          "type": "json_schema",
          "name": AI_RESPONSE_FORMAT_NAME,
          "strict": True,
          "schema": build_provider_output_json_schema(),
      }
  ```

- [ ] **Step 4: Add strict decoder RED cases**

  Cover minimal/full valid objects plus missing/extra fields, wrong containers/types, bool-as-number, string confidence/page, duplicate keys, NaN/Infinity, array/scalar/null roots, fences, prefix/suffix, invalid UTF-8, oversized strings, and oversized arrays.

- [ ] **Step 5: Implement the fail-closed decoder**

  Decode only `str|bytes|bytearray`; use `json.loads(..., object_pairs_hook=...)` to reject duplicate keys and `parse_constant` to reject non-finite constants. Pass the single parsed object to `ProviderAnalysisPayload.model_validate(..., strict=True)`. Catch errors internally and return `None` without logging or exposing error text.

- [ ] **Step 6: Verify Task 1 GREEN**

  Run: `python -m pytest -q tests/test_ai_output_schema.py`

  Expected: all new schema/decoder tests pass.

- [ ] **Step 7: Review and checkpoint**

  Run `git diff --check`, inspect only the two Task 1 files, and commit:
  `feat(rm-115): add canonical Tender Intelligence output schema`.

### Task 2: Provider interface and Responses `text.format`

**Files:**
- Modify: `app/ai/provider.py`
- Modify: `app/core/ai/provider_selection.py`
- Modify: `tests/test_openai_compatible_provider.py`
- Modify: `tests/test_ai_provider_selection.py`
- Modify: `tests/test_ollama_local_mode.py`
- Modify: `tests/test_ai_provider_runtime_integration.py`

**Interfaces:**
- Consumes: `output_format: Mapping[str, object] | None` supplied by the analyzer.
- Produces: every `AIProvider.analyze()` accepts the keyword-only argument; `OpenAICompatibleProvider.supports_text_format` determines whether the exact mapping is placed under `payload["text"]["format"]`.

- [ ] **Step 1: Add provider contract tests before implementation**

  Assert cloud requests contain the exact supplied format, no `response_format`, and one request; assert the input mapping is unchanged. Assert Ollama omits both `text` and `store`. Assert selection produces `supports_text_format=True` for OpenAI/generic and `False` for Ollama without network/keyring changes.

- [ ] **Step 2: Run focused provider tests and verify RED**

  Run: `python -m pytest -q tests/test_openai_compatible_provider.py tests/test_ai_provider_selection.py tests/test_ollama_local_mode.py tests/test_ai_provider_runtime_integration.py`

  Expected: failures for the missing keyword argument/property/request field.

- [ ] **Step 3: Extend the provider interface minimally**

  Import `Mapping` from `collections.abc`. Add the keyword-only parameter to `AIProvider`, `DisabledProvider`, and `OpenAICompatibleProvider`. Add `supports_text_format: bool = True` to the compatible provider constructor. When enabled and a format is supplied, copy only the outer request containers and retain the caller's exact nested mapping under `text.format`.

- [ ] **Step 4: Encode compatibility policy in provider selection**

  Construct cloud providers with `supports_text_format=True`; construct Ollama with `supports_text_format=False` and existing `store_response=None`. Do not add provider IDs, probes, or network work.

- [ ] **Step 5: Update only actual AIProvider test doubles**

  Change doubles that implement the provider boundary to accept `*, output_format: Mapping[str, object] | None = None`. Do not alter unrelated service/analyzer/tender-provider doubles.

- [ ] **Step 6: Verify Task 2 GREEN and security invariants**

  Re-run the focused command. Confirm request count remains one and safe failures contain none of the schema, prompt, document, URL, or credential fixtures.

- [ ] **Step 7: Review and checkpoint**

  Run `git diff --check` and commit:
  `feat(rm-115): enforce structured Responses output`.

### Task 3: Analyzer all-or-nothing structural validation and local evidence verification

**Files:**
- Modify: `app/core/ai/analyzer.py`
- Modify: `tests/test_ai_document_analyzer.py`

**Interfaces:**
- Consumes: `build_responses_text_format()` and `decode_and_validate_provider_output()`.
- Produces: unchanged `AiDocumentAnalysis` domain payload; structural errors return `INVALID_RESPONSE` with no findings, while evidence mismatch remains local `PARTIAL`/unverified.

- [ ] **Step 1: Replace lenient fixtures with a complete strict-payload helper**

  The helper must include every root key and all eleven requirement arrays. Every finding includes all six required keys, using `section=""` and `page=None` when unknown.

- [ ] **Step 2: Add analyzer RED tests**

  Assert the provider receives `SYSTEM_PROMPT`, rendered documents, and the canonical output format. Cover valid exact quote, unknown document, false quote, malformed JSON, unknown/missing root fields, wrong types, and a payload containing one valid-looking finding plus one structural defect. The last cases must yield `invalid_response` with empty findings.

- [ ] **Step 3: Run analyzer tests and verify RED**

  Run: `python -m pytest -q tests/test_ai_document_analyzer.py`

- [ ] **Step 4: Replace analyzer `_decode` with the canonical decoder**

  Call the provider once with `output_format=build_responses_text_format()`. On provider `status="ok"`, validate the response text. Return safe `INVALID_RESPONSE` for `None`; otherwise pass `payload.model_dump()` or explicitly typed fields into existing normalization. Keep exact quote/category/status decisions local.

- [ ] **Step 5: Simplify only obsolete lenient structural branches**

  Retain defensive local evidence checks and safe domain construction. Remove ordinary JSON decoding and behavior that partially accepts structurally malformed top-level data. Do not change the Orchestrator boundary.

- [ ] **Step 6: Verify analyzer and orchestration GREEN**

  Run: `python -m pytest -q tests/test_ai_document_analyzer.py tests/test_ai_orchestrator.py tests/test_ai_orchestrator_runtime_integration.py tests/test_ai_document_analysis_service.py tests/test_full_analysis_service.py`

- [ ] **Step 7: Review and checkpoint**

  Run `git diff --check`; fold this verified slice into the structured-output feature commit if still uncommitted, otherwise commit `test(rm-115): cover strict schema and provider boundaries` after Task 4 tests are complete.

### Task 4: Prompt, fingerprint, persistence, and regression boundaries

**Files:**
- Modify: `app/core/ai/prompts.py`
- Modify: `app/core/ai/repository.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_ai_document_analysis_repository.py`
- Modify: `tests/test_ai_document_schemas.py`
- Modify: integration/export/UI tests only where a new assertion is required

**Interfaces:**
- Produces: `AI_PROMPT_VERSION = "2"`, `AI_ANALYZER_VERSION = "3"`, and fingerprint key `provider_output_schema` using `AI_PROVIDER_OUTPUT_SCHEMA_VERSION`.
- Preserves: `AI_ANALYSIS_SCHEMA_VERSION = 2`, existing table/columns, history readability, and domain/export payload shape.

- [ ] **Step 1: Add RED tests for versioned cache isolation**

  Assert changing provider-output schema version changes the fingerprint; assert the default strict fingerprint cannot reuse a row saved under explicit old versions; assert persisted payload version stays 2 and repository initialization creates no new column/table.

- [ ] **Step 2: Run repository/schema tests and verify RED**

  Run: `python -m pytest -q tests/test_ai_document_analysis_repository.py tests/test_ai_document_schemas.py`

- [ ] **Step 3: Implement version and prompt changes**

  Update the prompt with the approved strict-output/evidence/no-decision rules. Add provider-output schema version to the serialized `versions` mapping and expose an optional argument for deterministic tests. Keep persisted schema unchanged.

- [ ] **Step 4: Extend the required mypy contour**

  Add `app/core/ai/output_schema.py`, `app/core/ai/analyzer.py`, and `app/core/ai/schemas.py` to `[tool.mypy].files` while retaining all existing entries.

- [ ] **Step 5: Run widened RM-115 regressions**

  Run the complete target contour from `docs/RM-115_REQUIREMENTS.md`, including UI/export/runtime tests. Confirm invalid current-run results are not replaced by stale success and no unverified evidence affects RM-107 or critical stop-factor priority.

- [ ] **Step 6: Review and checkpoint**

  Inspect the cumulative diff for scope and security, run `git diff --check`, and commit:
  `test(rm-115): cover strict schema and provider boundaries`.

### Task 5: Full offline acceptance, documentation, and pull request

**Files:**
- Modify: `docs/RM-115_REQUIREMENTS.md`
- Do not modify: `docs/STATUS.md`, `docs/ROADMAP.md`, or `docs/ROADMAP_HISTORY.md` before feature merge and post-merge Quality Gate.

**Interfaces:**
- Consumes: all implementation commits and the canonical target command.
- Produces: exact local acceptance evidence and a feature PR ready for Windows Quality Gate.

- [ ] **Step 1: Run fresh target and full pytest with measured durations**

  Use Python 3.12.7 from the project venv and worktree-local `TEMP/TMP`. Run the exact target contour, then `python -m pytest -q`.

- [ ] **Step 2: Run every static/security/dependency gate**

  Run in order: `python -m ruff check .`, `python -m ruff format . --check`, `python -m mypy`, `python scripts/check_repository_secrets.py`, `python -m pip_audit --skip-editable`, and `git diff --check`.

- [ ] **Step 3: Run architecture/security scans**

  Confirm one production `provider.analyze()` call, the existing component counts, no `response_format`, no Chat Completions fallback, no new migration, and no raw response/schema/error logging.

- [ ] **Step 4: Record exact acceptance evidence**

  Append command results, Python version, durations, architecture scan, offline/keyring statement, and database/migration statement to `docs/RM-115_REQUIREMENTS.md`.

- [ ] **Step 5: Run final verification after documentation**

  Re-run at minimum `git diff --check`, the secret scan, and the exact target contour after the documentation edit. Inspect `git status --short` and the full branch diff from `d9713f6`.

- [ ] **Step 6: Commit acceptance documentation**

  Commit: `docs(rm-115): record local acceptance results`.

- [ ] **Step 7: Push and create the feature PR**

  Push `feat/rm-115-strict-json-schema` and create PR title
  `feat(rm-115): enforce strict Tender Intelligence JSON schema`. The body must list reused
  components, the single production provider call, provider compatibility policy,
  structural-invalid versus evidence-unverified behavior, no database/migration,
  no RM-116/RM-117, no RM-107 changes, official Responses `text.format` basis, and exact
  validation results.

- [ ] **Step 8: Do not close RM-115 early**

  Leave RM-115 `IN PROGRESS`. Only after feature merge and successful post-merge Quality Gate
  on Python 3.12 and 3.13 may a separate docs completion package mark RM-115 DONE and activate
  RM-116.
