# RM-118 Audit — Explainable Draft Contract Analysis

Audit date: 2026-07-15
Branch: `feat/rm-118-draft-contract-analysis`
Base: `2697637fc0173082f1a6fec7c5b5eaef8e099698`
Status: audit complete; application code not changed

## Entry gate

- RM-117 is `DONE` and RM-118 is the only `IN PROGRESS` stage in the canonical
  `docs/STATUS.md` and `docs/ROADMAP.md`.
- RM-117 feature PR #37 was merged as `c9d5a31e671ca61a6c6f54428aa8b8f9b26a561a`.
- The RM-117 docs-only closeout PR #38 was merged as the baseline
  `2697637fc0173082f1a6fec7c5b5eaef8e099698`.
- Final-main Windows Quality Gate run `29377293601` passed on Python 3.12 and 3.13.
- The branch was created directly from final `origin/main`, not from an RM-117 feature branch.
- The canonical Definition of Done and accepted roadmap history were reviewed before this audit.

## Offline baseline

Baseline used `C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe`, Python 3.12.7,
`QT_QPA_PLATFORM=offscreen`, worktree-local `TEMP/TMP`, and no live provider, DNS, host
keyring, or saved credentials.

- RM-118 target contour before new draft-contract tests: `240 passed in 12.73s`.
- Full pytest: `1043 passed in 53.98s`.
- Target files: existing technical-specification, context, provider schema, persisted schema,
  analyzer, service, repository, provenance, provider-runtime, export, full-analysis UI,
  RM-107 participation-decision, and deterministic requirement-analyzer tests.
- User-owned untracked `.agents/` and `skills-lock.json` were present and left untouched.

## Audited versions

The values on final main match the expected RM-117 baseline:

- persisted `AiDocumentAnalysis` payload: `4`;
- provider output schema: `2`;
- Responses format: `corteris_tender_analysis_v2`;
- prompt: `4`;
- analyzer/fingerprint: `5`;
- context: `3`;
- citation resolver: `1`.

RM-118 must increase the first six values exactly once to payload `5`, provider schema `3`,
response format `v3`, prompt `5`, analyzer `6`, and context `4`. The citation resolver remains
at `1` because RM-118 reuses its existing exact-citation contract.

## Audited production graph

The production graph is singular and is the required extension path:

`TenderDocumentTextService` → `TenderDocumentContextBuilder` →
`TenderDocumentAiAnalysisService` → `TenderDocumentAiAnalyzer` → one
`AIProvider.analyze()` → RM-116 citation resolver/provenance →
`AiDocumentAnalysisRepository` → `TenderAiOrchestrator` →
`TenderFullAnalysisService` → RM-107 → existing UI/export.

`app/tenders/search_runtime.py` constructs one context builder, provider, analyzer, analysis
service, repository and Orchestrator. Static production inspection found exactly one
`provider.analyze(...)` call, in `app/core/ai/analyzer.py`. Calls in provider unit tests and the
separate deterministic `TenderRequirementsAnalyzer.analyze(...)` are not additional production
provider workflows.

## Classification and deterministic contract logic

- `DocumentKind.DRAFT_CONTRACT` and the shared pure `classify_document_kind(source_name, text)`
  already exist in `app/core/document_classification.py` and are used by both the deterministic
  analyzer and AI context builder.
- The current draft-contract rule includes broad bare terms `контракт` and `договор`. It therefore
  cannot yet be trusted as an evidence boundary: experience requirements, notices, instructions,
  application forms, technical specifications and NMCK calculations can contain those words.
- TS currently has rule-order priority, but explicit positive draft-contract structure and all
  required negative cases need deterministic regression coverage before contract evidence may be
  accepted as verified.
- `RequirementCategory.PAYMENT`, `WARRANTY`, `PENALTY`, and `CONTRACT`, the rules for contract
  security/payment/warranty/penalty/unilateral refusal, and
  `TenderRequirementAnalysis.contract_risks` already provide deterministic extraction.
- RM-118 must not reproduce those rules, severities, decisions, or stop factors in the AI section.
  The new section is neutral evidence-backed extraction only.

## Context and completeness

`TenderDocumentContextBuilder` reads only existing extraction results, classifies each prepared
record once, deduplicates by checksum, applies per-document and total limits, and records explicit
TS completeness fields in `AiContextStatistics`. All dataclass statistics are included in the
service fingerprint.

RM-118 must add draft-contract statistics and order documents as TS, draft contract,
notice/estimate, then all others. Empty, unavailable, truncated, duplicate, or total-limit omitted
contracts must remain visible to local completeness logic. A small scoped-statistics helper should
share mechanics with TS without removing the explicit public TS and draft-contract fields.

## Provider schema, prompt and analyzer

- `app/core/ai/output_schema.py` owns one strict Pydantic decoder with `strict=True` and
  `extra="forbid"`. `ProviderFindingPayload` is the only provider finding shape.
- The current root has one nested `technical_specification` object and no draft-contract object.
  RM-118 must add exactly one required nested object with all 16 required arrays; any missing,
  extra, or mistyped value rejects the whole provider payload.
- The single `SYSTEM_PROMPT` governs the one response. It already forbids local status,
  verification, provenance, score and decision fields; it must add the DRAFT_CONTRACT boundary
  and prohibit legal/financial conclusions.
- `TenderDocumentAiAnalyzer` already routes candidates through the one RM-116
  `resolve_citation()` and locally owns verification, warnings and status. The current TS-specific
  normalization and multi-source contradiction helper are the sharing point, but must not be
  copied wholesale.
- Draft-contract evidence must be restricted to current locally classified contract document IDs.
  A contract contradiction may use two distinct canonical citations from one document when their
  offsets differ; a repeated citation is not independent support.

## Payload, provenance and cache

- `AiDocumentAnalysis.to_payload()` and `from_payload()` own the canonical persisted shape.
- Current payload v4 validates the exact TS subsection, verifies current provenance versions,
  downgrades unsafe findings, rejects future/incompatible data, and permits safe legacy reads.
- The repository stores versioned JSON in the existing `tender_ai_document_analyses` table and
  reuses only exact current fingerprints. Provider disabled/error results do not substitute stale
  success.
- RM-118 must add an exact fail-closed draft-contract shape. Generic, TS, unknown, non-contract,
  altered, or provenance-damaged cached evidence cannot be promoted to verified contract evidence.
  Raw provider response, prompt, full document text and private paths remain unpersisted.

## UI, export and decision boundary

- `TenderFullAnalysisDialog` has one existing `AI-анализ` tab and one citation navigator built by
  `_current_citation_targets()`.
- `app/reporting/tender_ai_analysis.py` has one JSON/HTML exporter. JSON delegates to canonical
  `to_payload()`; HTML escapes external strings, uses safe internal citation anchors, and
  deduplicates sources.
- These are the only extension points. RM-118 adds no tab, dialog, action, AI stage, navigator, or
  exporter.
- RM-107 consumes eligible current verified generic findings. The draft-contract subsection must
  not enter `_current_verified_ai_findings()`, change score/recommendation/action plan, or weaken
  the absolute priority of deterministic critical stop factors.

## SQLite and migration decision

RM-118 changes only the versioned JSON payload stored in the existing
`tender_ai_document_analyses.payload_json`/`payload_version` columns. No table, column, index, or
relationship changes are required, so a database migration would be unjustified.

## Audit decision

Harden the one classifier, extend the current context/statistics/fingerprint, strict provider
schema, prompt, explicit domain types, analyzer normalization, versioned payload, UI, citation
navigator and exporter. Reuse the existing service, provider call, resolver/provenance,
repository, Orchestrator, full-analysis workflow and RM-107 decision path. Do not implement
RM-119, RM-120, RM-121, legal conclusions, financial conclusions, or a second source of decisions.
