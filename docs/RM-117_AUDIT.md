# RM-117 Audit — Explainable Technical Specification Analysis

Audit date: 2026-07-15
Branch: `feat/rm-117-technical-specification-analysis`
Base: `343cd425e4f3f0eb1b22a1c4b2c41d8c3e2e0f24`
Status: audit complete; application code not changed

## Entry gate

- RM-116 is `DONE` in `docs/STATUS.md` and `docs/ROADMAP.md`.
- Feature PR #35 was merged as `b8ff9b1`; the docs-only closeout was merged as `343cd42`.
- Post-merge Windows Quality Gate run `29372896780` passed on Python 3.12 and 3.13
  with `1030 passed` on both versions.
- RM-117 is the only active roadmap stage. RM-118 remains planned.
- The canonical Definition of Done and accepted history were reviewed before application code.

## Audited production graph

The existing graph is the required extension path and must remain singular:

`TenderDocumentTextService` → `TenderDocumentContextBuilder` →
`TenderDocumentAiAnalysisService` → `TenderDocumentAiAnalyzer` → one
`AIProvider.analyze()` → RM-116 citation resolver/provenance →
`AiDocumentAnalysisRepository` → `TenderAiOrchestrator` →
`TenderFullAnalysisService` → RM-107 → existing UI/export.

Production composition in `app/tenders/search_runtime.py` creates one context builder, provider,
analyzer, analysis service, repository and Orchestrator. Static inspection found exactly one
production `provider.analyze(...)` call, in `app/core/ai/analyzer.py`. The separate deterministic
`TenderRequirementsAnalyzer.analyze(...)` is not a provider call and must remain the shared
classification owner rather than become a second AI workflow.

## Classification and context boundary

- `DocumentKind.TECHNICAL_SPECIFICATION` and `_DOCUMENT_KIND_RULES` already exist in
  `app/tenders/requirement_analysis.py`; `TenderRequirementsAnalyzer.classify_document()` is the
  only deterministic classifier. It is currently an instance method and is not reused by the AI
  context builder.
- `TenderDocumentContextBuilder` currently sorts by document key/path/checksum, applies per-file
  and total character limits, and records aggregate truncated/omitted counts. It does not classify
  documents, prioritize a technical specification, identify which omitted record was a TS, or
  expose TS-specific completeness.
- `AiDocument.document_type` represents the file format. A separate stable `document_kind` is
  required so file extension and semantic classification are not conflated.
- The safe extension is one public pure classifier used by both flows, TS-first stable ordering,
  and TS-specific included/truncated/omitted metadata in the existing context result.

## Strict provider, domain and persistence contract

- The canonical provider schema is `app/core/ai/output_schema.py`, version `1`, and rejects extra
  or non-strict fields. It currently has no `technical_specification` object.
- The canonical persisted domain is `AiDocumentAnalysis`, payload version `3`. Prompt, analyzer
  and context versions are respectively `3`, `4` and `2`; citation resolver version is `1`.
- Provider findings contain only statement and candidate citation fields. Local code owns category,
  verification, section status, warnings, provenance and every decision field.
- The existing `tender_ai_document_analyses` table stores the versioned JSON payload and needs no
  new table or column. Raising the payload/fingerprint versions isolates new cache rows while
  existing payloads can be read fail-closed with an empty unavailable TS section.
- Future/corrupt cache already fails closed and repository recovery can continue to an older safe
  compatible row.

## RM-116 verifier and provenance boundary

`app/core/ai/citations.py` is the single final verifier. It resolves exact quotes against locally
known documents, derives citation IDs/checksums/offsets and source snapshots, and is already used
by the analyzer. RM-117 must pass TS candidates through this resolver, additionally restrict
verified TS findings to locally classified TS document IDs, and validate multi-source
contradictions without adding `quote in text` or a second evidence shape.

## Service, cache, UI/export and RM-107

- `TenderDocumentAiAnalysisService` already builds context, fingerprints it, reuses only an exact
  successful match, analyzes once and persists the current result. Provider-disabled/error results
  remain safe current results rather than stale successes.
- `RUNNING_AI` is the only AI stage in `TenderFullAnalysisService`; no stage or total-step change is
  needed.
- `TenderFullAnalysisDialog` and `app/reporting/tender_ai_analysis.py` are the only current AI
  presentation/export extension points. JSON already delegates to canonical `to_payload()`; HTML
  escapes external text and uses RM-116 safe citation/source data.
- RM-107 consumes only eligible current verified generic risks. The TS subsection must not add a
  second penalty, affect score/recommendation, or weaken critical stop-factor priority.

## SQLite and migration decision

The AI cache physical schema remains one table with the existing columns: registry key, context
fingerprint, status, payload JSON, timestamps and payload version. The broader application schema
is currently migration version 3. RM-117 changes only the versioned JSON payload and therefore
does not justify a database migration.

## Offline baseline

Baseline used `C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe`, Python 3.12.7,
`QT_QPA_PLATFORM=offscreen`, worktree-local `TEMP/TMP`, and no live provider, DNS, host keyring or
saved credentials.

- Existing RM-117 target contour (excluding not-yet-created TS-focused tests):
  `201 passed in 14.32s`.
- Full pytest: `1030 passed in 68.21s`.
- User-owned untracked `.agents/` and `skills-lock.json` were present and left untouched.

## Audit decision

Expose the current classifier as one public pure function; extend the current context, strict
provider schema, `AiDocumentAnalysis` payload, analyzer normalization, repository fingerprint,
existing UI and exporter. Store the subsection in the existing JSON payload. Do not create a
provider, HTTP path, classifier table, citation verifier, analysis service, Orchestrator,
repository, database object, AI stage, Decision Engine, UI workflow or exporter.
