# RM-115 Audit — Strict Tender Intelligence JSON Contract

Status: completed before application-code changes
Audit date: 2026-07-14
Baseline branch: `main`
Baseline HEAD: `d9713f6e0234e6dbec8314c87b95944c0061a485`
(`Merge pull request #32 from lykay86-dotcom/codex/git-integration-recovery`)
Implementation branch: `feat/rm-115-strict-json-schema`

## Repository and external-state audit

The main checkout contained unrelated untracked user-owned paths `.agents/` and
`skills-lock.json`. They were not modified. RM-115 is isolated in
`.worktrees/rm-115-strict-json-schema` from the accepted `main` HEAD above.

No local or remote branch matching `*rm-115*` existed before branch creation. A read-only
GitHub query found no open pull request whose title or body referenced RM-115.

`docs/STATUS.md` and `docs/ROADMAP.md` identify RM-115 as the only active stage. RM-114 is
accepted after PR #30 and post-merge Quality Gate run `29315630189`. RM-116 and RM-117 remain
planned and must not be started in this package.

## Baseline validation

All tests used `C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe`, Python 3.12.7, and
were executed offline from the isolated worktree.

- Initial target attempt used the host `%TEMP%` and was blocked by the managed filesystem:
  `121 passed, 70 errors in 32.41s`; every reported error came from pytest's inability to
  enumerate `C:\Users\LYKA0\AppData\Local\Temp\pytest-of-*`. No application assertion failed.
- The same target contour, with `TEMP` and `TMP` redirected inside the worktree, passed:
  `191 passed in 5.97s`; measured wall time `7.06s`.
- Full baseline with the same isolated temporary directory passed:
  `863 passed in 57.85s`; measured wall time `59.26s`.

The target contour included every existing file from the requested RM-115 contour. The new
`tests/test_ai_output_schema.py` did not exist at baseline and was therefore not included.

## Existing production flow

The accepted flow is:

```text
TenderDocumentContextBuilder
→ TenderDocumentAiAnalyzer
→ AIProvider
→ lenient local JSON decoding and evidence normalization
→ AiDocumentAnalysisRepository
→ RM-107 ParticipationDecisionService
→ TenderFullAnalysisResult
→ UI and HTML/JSON export
```

`app/tenders/search_runtime.py` is the production composition root. It resolves one provider,
constructs one `TenderDocumentAiAnalyzer`, one `TenderDocumentAiAnalysisService`, one
`TenderAiOrchestrator`, and one shared `AiDocumentAnalysisRepository`. The current runtime
does not perform network work during bootstrap, settings load, or settings save.

The only production occurrence of `provider.analyze()` is
`TenderDocumentAiAnalyzer.analyze()` in `app/core/ai/analyzer.py`. Direct test calls exercise
transport fixtures only. RM-115 does not require another provider, analyzer, orchestrator,
repository, Decision Engine, transport, or AI pipeline.

## Existing provider implementations and test doubles

`app/ai/provider.py` contains the complete production `AIProvider` hierarchy:

- abstract `AIProvider`;
- offline `DisabledProvider`;
- the single HTTP adapter `OpenAICompatibleProvider`.

`AiProviderSelectionService` constructs that same `OpenAICompatibleProvider` for official
OpenAI, generic `openai_compatible`, and loopback-only Ollama. Test doubles with `analyze()`
exist in analyzer, runtime, service, orchestrator, full-analysis, and requirement-analysis
tests. Every double that implements `AIProvider` or stands in for the production provider
boundary must accept the new keyword-only `output_format`; unrelated analyzers and tender
source providers are outside this signature change.

## Current request/output contract

`OpenAICompatibleProvider.analyze()` currently sends one synchronous `POST /responses` with
`model`, `input`, and `stream=false`. Cloud profiles also send `store=false`; Ollama omits
`store`. The provider extracts safe `output_text` and returns it as a string in the existing
safe result envelope.

There is no provider-output JSON Schema and no `text.format` request field. The analyzer uses
ordinary `json.loads`, accepts a partially shaped mapping, defaults absent collections, and
locally drops or truncates malformed members. That RM-110 behavior is intentionally lenient
and cannot enforce the RM-115 all-or-nothing structural contract.

Current OpenAI documentation defines Responses structured output under `text.format`, using
`type=json_schema`, a bounded `name`, the JSON `schema`, and `strict=true`. RM-115 will use
that request shape. It will not send the Chat Completions `response_format` shape.

## Existing domain and persistence schemas

`app/core/ai/schemas.py` owns the persisted/domain contracts:

- `AiDocument`, `AiEvidence`, `AiFinding`, and `TenderRequirements`;
- `AiDocumentAnalysis` with `AI_ANALYSIS_SCHEMA_VERSION = 2`;
- local `AiFindingStatus` and safe `AiAnalysisStatus` values;
- `to_payload()`/`from_payload()` for repository history and export.

`TenderRequirements` has exactly eleven deterministic dataclass fields: `equipment`,
`certificates`, `licenses`, `specialists`, `documents`, `experience`, `deadlines`, `warranty`,
`bid_security`, `contract_security`, and `bank_guarantee`.

These domain/persistence schemas include trusted local fields such as `status`, `category`,
`registry_key`, `payload_version`, `created_at`, `warnings`, and `context`. They must not be
exposed as provider-controlled output. The new raw provider schema is an input-boundary
schema, not a replacement for these types.

`AiDocumentAnalysisRepository` stores append-only versioned payloads in the existing
`tender_ai_document_analyses` table. A provider-output schema version can be added to the
fingerprint's version map without changing the table, row shape, or persisted payload.
Therefore RM-115 needs no new database, table, column, or migration. Existing history remains
readable; only reuse under the new fingerprint is prevented.

## Provider compatibility decision

- `openai`: existing `OpenAICompatibleProvider`, provider-side `text.format` enabled,
  `store=false` retained.
- `openai_compatible`: the same provider and `text.format`; an incompatible endpoint returns
  the existing safe provider error. There is no capability probe, downgrade, retry, or second
  request.
- `ollama`: the same provider with provider-side `text.format` disabled. Its confirmed request
  subset remains `model`, `input`, and `stream`; `text` and `store` are omitted. The returned
  text is nevertheless subject to the same local strict decoder.
- `disabled`: no network and unchanged deterministic fallback.

Stable provider IDs and persisted settings remain unchanged.

## Decision and evidence invariants

RM-107 remains the only owner of score and recommendation, and critical stop factors keep
absolute priority. The provider may not return or control decision fields, finding status,
category, or verification state.

After structural validation, the existing analyzer remains responsible for assigning a
bucket-derived category and for exact-quote verification against a known `document_id` and
local document text. Structurally invalid output is rejected in full as `invalid_response`;
structurally valid but unsupported evidence may produce unverified findings and `partial`.

## Stage boundaries

RM-115 introduces only the strict raw provider-output contract, provider-side Responses
format where supported, local fail-closed validation, prompt/analyzer/fingerprint versioning,
and regression coverage.

It explicitly excludes RM-116 citations/provenance and RM-117 specialized technical-
specification analysis. It also excludes contract/application/legal/financial analysis,
Chat Completions fallback, retry/backoff/failover, capability probing, UI switches, score or
recommendation changes, raw-response persistence, and any new AI workflow.

## Audit conclusion

The correct extension points are the existing provider interface, `OpenAICompatibleProvider`,
`AiProviderSelectionService`, `TenderDocumentAiAnalyzer`, prompt constants, and repository
fingerprint. One canonical Pydantic v2 provider-output model can generate the JSON Schema and
validate every provider locally while preserving the accepted architecture and persistence.
