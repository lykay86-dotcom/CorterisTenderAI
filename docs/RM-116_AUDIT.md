# RM-116 Audit — Verified Citations and Provenance

Audit date: 2026-07-14
Branch: `feat/rm-116-citations-provenance`
Base: `cb07d6b979cabf92f5820833a0aa64de3be9e15a`
Status: audit complete; application code not changed

## Entry gate

- RM-115 is `DONE` in `docs/STATUS.md` and `docs/ROADMAP.md`.
- Feature PR #33 was merged as `f2573c49cd6ac0dbbe703786414422034ffa53b2`.
- RM-115 closeout PR #34 was merged as
  `cb07d6b979cabf92f5820833a0aa64de3be9e15a`.
- Post-closeout Windows Quality Gate run `29353713499` passed on Python 3.12 and 3.13.
- RM-116 is the only active roadmap stage. RM-117 remains planned.

## Audited production path

The existing path is the required extension path and must remain singular:

`TenderDocumentTextService` → `TenderDocumentContextBuilder` →
`TenderDocumentAiAnalysisService` → `TenderDocumentAiAnalyzer` →
`TenderAiOrchestrator` → `AiDocumentAnalysisRepository` → RM-107 → UI/export.

The audit found one production `OpenAICompatibleProvider`, analyzer, Orchestrator, AI
repository, context builder, provider call, and AI export path. The deprecated
`app/ai/structured_analysis.py` is not a production workflow and must not be revived.

## Current evidence and strict-output boundary

- `app/core/ai/output_schema.py` is the only provider-output JSON Schema. Its finding model
  already permits only candidate fields: `statement`, `document_id`, `quote`, `section`,
  `page`, and `confidence`; `extra="forbid"` prevents provider-supplied citation or
  provenance fields.
- `app/core/ai/analyzer.py` currently verifies `quote in document.text`. It does not calculate
  offsets, detect duplicate occurrences, validate a checksum, or derive page/section from
  local markers. It currently trusts provider page/section after type validation.
- `AiEvidence` contains only document ID, quote, section, page, and confidence. It lacks a
  citation ID, offsets, checksum, verification method, safe source reference, and fingerprint.
- Unverified findings currently discard evidence. This is a safe default and can be retained;
  untrusted candidate fields do not need to be persisted.

Conclusion: extend `AiEvidence` and add one local resolver. Do not change or duplicate the
RM-115 provider-output schema.

## Document context and private-path boundary

- `TenderDocumentContextBuilder` correctly uses already extracted text and never rereads the
  original document.
- It currently sets `AiDocument.source` to `str(source_path)` when a path is available. This
  makes an absolute Windows path reachable from the AI domain even though the current payload
  does not serialize documents.
- The display name is already based on `source_path.name`, and the extracted text includes
  deterministic `===== <label> =====` section markers. PDF pages use labels
  `Страница N`.
- Checksums and truncation metadata are already present on `AiDocument`.

Conclusion: keep the basename as the display name, replace `source` with the logical value
`local_document_store`, and build `source_ref` only from `document_id`. Original paths remain
inside document storage/text services.

## Provider metadata and response identity

- `OpenAICompatibleProvider` exposes a sanitized, length-limited `raw_id` in its safe response.
- The provider stores a model internally, but there is no public metadata contract and the
  analyzer must not inspect arbitrary attributes.
- The approved design adds immutable public `AiProviderMetadata` with bounded `provider_id`
  and `model`. Provider selection supplies the stable provider ID explicitly. API keys, base
  URLs, headers, prompts, documents, and transport configuration are excluded.

## Serialization, repository, and cache

- `AI_ANALYSIS_SCHEMA_VERSION` is currently `2`; the existing SQLite table stores append-only
  `payload_json`, `payload_version`, registry key, fingerprint, status, and timestamp.
- This physical schema can persist citations, provenance, and source snapshots without a
  database migration.
- `context_fingerprint()` already includes document checksums and prompt/output/analyzer/
  context versions, but not a citation resolver version.
- `from_payload()` currently allows a version 1 or 2 finding marked `verified` when its legacy
  evidence parses. Under RM-116 such rows do not prove checksum, offsets, citation identity,
  or current-run provenance and must be downgraded to `UNVERIFIED`.
- Repository recovery already skips corrupt/newer rows and can continue to an older safe row.

Conclusion: raise the payload version to 3, add `CITATION_RESOLVER_VERSION` to the fingerprint,
validate version-3 provenance and citations on load, and safely display legacy rows without
allowing their findings to affect RM-107. No migration is required.

## RM-107 boundary

`ParticipationDecisionService` currently accepts AI risk input when `item.verified` and
`item.evidence is not None`. It preserves critical stop-factor priority and does not let AI
own score calculation. RM-116 must strengthen only the eligibility predicate: citation ID,
checksum, fingerprint, and analysis provenance must all be valid for the current result.
Score formulas, recommendation policy, and stop-factor ordering remain unchanged.

## UI and export boundary

- `TenderFullAnalysisDialog` renders verified evidence in the existing AI tab but has no
  internal citation-link handler.
- `TenderDocumentsDialog` is the existing document viewer and already selects rows by
  `document_key` internally, but has no public `select_document()` presentation API.
- `TenderSearchUiController` already owns both dialogs and is the correct navigation layer.
- The current HTML exporter escapes finding data but has no source registry or internal
  anchors. JSON delegates to `AiDocumentAnalysis.to_payload()`.

Conclusion: add a validated internal citation scheme to the existing AI tab, emit a safe
signal, let the controller open the existing document dialog, and select by document ID. Add
source anchors to HTML and structured provenance/source registry to the existing JSON payload.
Do not add a viewer, repository access in UI, local-file links, or external AI-provided links.

## Baseline

Baseline used `C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe`, Python 3.12.7, with
worktree-local `TEMP/TMP` and no live provider, DNS, keyring, or saved credentials.

- Existing RM-116 target contour (new citation/provenance test files absent):
  `193 passed in 10.60s`.
- Full pytest: `901 passed in 59.42s`.
- Worktree was clean before this documentation package.

## Audit decision

Create `app/core/ai/citations.py` because no canonical resolver exists. Extend the current
schemas, analyzer/service, repository fingerprint, RM-107 eligibility predicate, existing UI,
and existing exporter. Add the public provider metadata contract. Do not create a database
migration or a second schema, parser, provider, analyzer, Orchestrator, repository, context
builder, Decision Engine, exporter, or citation workflow.

## Implementation acceptance preparation

The audited extension was implemented without adding a second provider, analyzer,
Orchestrator, repository, context builder, output schema, Decision Engine, exporter, or
citation workflow. Production retains one `AIProvider.analyze(...)` call. No live provider,
DNS, keyring, saved credential, new database, or migration is required by the local suite.

Acceptance evidence on Python 3.12.7:

- exact RM-116 target: `262 passed in 6.37s`;
- strict/provider/UI regressions: `93 passed in 3.74s`;
- full suite: `1014 passed in 50.92s`;
- Ruff check and format (`507 files`) passed;
- mypy passed on the expanded fixed contour of 16 production files;
- repository secret scan passed;
- `pip_audit --skip-editable`: no known vulnerabilities; editable project skipped as expected;
- architecture/leak scans found one canonical component per audited boundary, one production
  provider call, no Chat Completions/retry/fuzzy/web path, and no raw exception/response logging.

This is feature-branch preparation only. RM-116 remains `IN PROGRESS`; feature merge,
post-merge Windows Quality Gate on Python 3.12/3.13, and merged docs-only closeout remain
mandatory before RM-116 becomes `DONE` or RM-117 becomes active.
