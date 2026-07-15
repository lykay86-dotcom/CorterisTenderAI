# RM-119 Audit — Explainable Application Requirements Analysis

Audit date: 2026-07-15
Branch: `feat/rm-119-application-requirements-analysis`
Base: `995d76c6eb1cc28661fec6e0a2f909447cd2abc2`
Status: audit complete; application code and tests not changed

## Entry gate

- RM-118 is `DONE` and RM-119 is the only `IN PROGRESS` stage in the canonical
  `docs/STATUS.md` and `docs/ROADMAP.md`.
- RM-118 feature PR #39 was merged as
  `40b7da25ec3ce43585650ddcec7afef994299f94`.
- The RM-118 docs-only closeout PR #40 was merged as the baseline
  `995d76c6eb1cc28661fec6e0a2f909447cd2abc2`.
- Final-main Windows Quality Gate run `29399914600` passed on Python 3.12 and 3.13.
- The feature branch was created directly from final `origin/main` at the expected baseline SHA.
- The canonical Definition of Done, roadmap history, RM-117 audit/requirements and RM-118
  audit/requirements were reviewed before this audit.
- User-owned untracked `.agents/` and `skills-lock.json` were present and left untouched.

## Offline baseline

Baseline used `C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe`, Python 3.12.7,
`QT_QPA_PLATFORM=offscreen`, worktree-local `TEMP/TMP`, and no live provider, DNS, host
keyring, or saved credentials.

- RM-119 target contour before the new application-requirements test file:
  `277 passed in 14.82s`.
- Full pytest: `1080 passed in 59.11s`.
- Target files were the existing deterministic classifier, context, strict provider schema,
  persisted schema, analyzer, service, repository, provenance, provider-runtime, TS, contract,
  UI/export and RM-107 regression tests required by the RM-119 task.

## Audited versions

The values on final main match the expected RM-118 closeout:

- persisted `AiDocumentAnalysis` payload: `5`;
- provider output schema: `3`;
- Responses format: `corteris_tender_analysis_v3`;
- prompt: `5`;
- analyzer/fingerprint: `6`;
- context: `4`;
- citation resolver: `1`.

RM-119 must increase the first six values exactly once to payload `6`, provider schema `4`,
response format `v4`, prompt `6`, analyzer `7`, and context `5`. The citation resolver remains
at `1` because RM-119 reuses the existing RM-116 exact-citation contract.

## Audited production graph

The production graph is singular and is the required extension path:

`TenderDocumentTextService` → `TenderDocumentContextBuilder` →
`TenderDocumentAiAnalysisService` → `TenderDocumentAiAnalyzer` → one
`AIProvider.analyze()` → RM-116 citation resolver/provenance →
`AiDocumentAnalysisRepository` → `TenderAiOrchestrator` →
`TenderFullAnalysisService` → RM-107 → existing UI/export.

`app/tenders/search_runtime.py` constructs one context builder, provider, analyzer, analysis
service, repository and Orchestrator. Static production inspection found exactly one
`provider.analyze(...)` call, in `app/core/ai/analyzer.py`. The deterministic
`TenderRequirementsAnalyzer.analyze(...)` is not a provider call, and `RUNNING_AI` remains the
single production AI stage.

## Existing classification and source-scope gap

- `DocumentKind.APPLICATION_REQUIREMENTS` and the public pure
  `classify_document_kind(source_name, text)` already exist in
  `app/core/document_classification.py`; both `TenderRequirementsAnalyzer` and the AI context
  builder call this classifier.
- The current application-requirements rule recognizes only two phrases and has no exported
  canonical set of allowed requirement source kinds.
- Existing priority rules do not yet prove all required positive, negative and combined-document
  cases. In particular, application form, instructions and procurement notice are separate kinds
  but are not united into one evidence boundary.
- RM-119 requires one public `APPLICATION_REQUIREMENTS_SOURCE_KINDS` containing application
  requirements, application form, instructions and procurement notice, reused by context,
  analyzer, persisted validation, provenance validation and tests.

## Existing provider object and domain contract

- The canonical strict root provider output already has exactly one `requirements` object; a
  parallel `application_requirements` root object would duplicate the existing contract.
- `ProviderRequirementsPayload` currently contains 11 required arrays: `equipment`,
  `certificates`, `licenses`, `specialists`, `documents`, `experience`, `deadlines`, `warranty`,
  `bid_security`, `contract_security`, and `bank_guarantee`.
- `TenderRequirements` is the existing `AiDocumentAnalysis.requirements` domain object with the
  same 11 finding groups. It has no local status, found/included document IDs or scoped warnings.
- Provider decoding is already strict, extra-forbidden, duplicate-key/NaN/Infinity rejecting and
  size bounded. RM-119 must extend this one object to exactly 21 required finding arrays without
  exposing local status, verification, provenance or decision fields.
- Existing UI/export iterates every `TenderRequirements.__dataclass_fields__` member as findings.
  Adding metadata therefore requires one explicit finding-fields tuple shared by serialization,
  analysis, UI and export.

## Context and completeness gap

`TenderDocumentContextBuilder` reads only existing `StoredDocumentText`, classifies prepared
records once, deduplicates by checksum and applies per-document and total limits. It records
explicit TS and draft-contract statistics through `_ScopedContextStatistics`, but that helper
accepts only one `DocumentKind` and the public statistics contain no application-requirements
scope.

The current ordering is TS, draft contract, notice/estimate, then all other documents. There are
no found/included application requirement IDs, no application-specific truncation flag, and no
way for unavailable, empty, omitted or deduplicated scoped documents to prevent a false complete
requirements result. All explicit dataclass statistics already enter the service fingerprint, so
adding the five required fields will make scoped completeness cache-relevant without a second
fingerprint path.

## Analyzer, evidence and safe-failure gap

- Current `requirements` candidates are normalized by unrestricted `_findings()`. A verified
  exact quote from TS, contract, estimate or any other locally included kind can therefore remain
  verified inside `requirements`.
- `_scoped_findings()` already restricts TS and draft-contract evidence, but accepts one kind.
  It is the correct sharing point to generalize to a `frozenset[DocumentKind]` for all three
  scoped sections.
- RM-116 `resolve_citation()` remains the only final verifier. RM-119 must additionally require
  the canonical application source scope and current provenance before requirements evidence may
  be verified.
- `_safe_failure()` currently assigns local statuses and document IDs only for TS and draft
  contract; `requirements` remains an unscoped empty dataclass on provider disabled/error/invalid
  response.
- The contract contradiction helper already supports distinct canonical citation IDs, including
  distinct offsets in one document. It should be generalized and reused for requirements rather
  than copied.

## Payload, provenance and cache gap

- `AiDocumentAnalysis.to_payload()` stores `requirements` as a mapping of every dataclass field;
  `from_payload()` accepts a loose mapping and has no exact scoped requirements shape.
- Current payload v5 may retain verified requirements evidence when provenance is current, but it
  does not validate that the source kind is in an application-requirements scope.
- Legacy requirements have 11 unscoped arrays and no completeness metadata. RM-119 must preserve
  their readable statements only as unverified, return local status `unavailable`, keep scoped
  document IDs empty, add an explicit legacy warning and leave the ten new groups empty.
- Current v6 must require exact keys for status, document IDs, 21 groups and warnings; damaged,
  future or provenance-incompatible payloads remain fail-closed. A current provider failure must
  not be replaced by stale success.

## UI, export and RM-107 boundary

- `TenderFullAnalysisDialog` has one existing `AI-анализ` tab and one citation navigator.
  `TenderAiAnalysisExporter` owns the only JSON/HTML export path; JSON delegates to canonical
  `to_payload()` and HTML escapes external values and uses internal citation anchors.
- The current requirements section is a flat `Требования` list without local status,
  found/included counts, 21 group labels, scoped warnings or incomplete-context notice.
- `_current_verified_ai_findings()` in RM-107 consumes only current verified generic `risks`,
  `suspicious_conditions` and `contradictions`. It does not consume `requirements`, TS or draft
  contract findings. RM-119 must preserve this boundary and the absolute priority of deterministic
  critical stop factors.

## SQLite and migration decision

RM-119 changes only the versioned JSON stored in the existing
`tender_ai_document_analyses.payload_json`/`payload_version` columns. No table, column, index,
relationship or repository change is required, so a SQLite migration would be unjustified.

## Audit decision

Strengthen the one classifier and define one exported application source scope. Extend the
existing context/statistics/fingerprint, strict root `requirements` schema, prompt,
`TenderRequirements`, scoped analyzer normalization, safe failure, versioned payload/current
provenance, existing AI tab/citation navigator and existing exporter. Reuse the single provider
call, RM-116 resolver, service, repository, Orchestrator, full-analysis stage and RM-107 decision
path. Do not add a second requirements section, AI workflow, classifier, decision source, database
object, legal/financial conclusion, participant compliance assessment or rejection forecast.
