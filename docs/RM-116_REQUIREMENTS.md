# RM-116 Requirements — Verified Citations and Provenance

Status: DESIGN APPROVED; READY FOR IMPLEMENTATION PLAN
Canonical contract date: 2026-07-14
Depends on: RM-107, RM-110, RM-111, RM-112, RM-113, RM-114, RM-115

## Goal

Every `VERIFIED` Tender Intelligence finding must have an exact locally resolved citation,
a stable source snapshot, and provenance for the current analysis. Provider output remains
candidate evidence only. Unverified, legacy, damaged, or stale findings cannot affect RM-107.

## Invariants and scope

- Reuse the production path documented in `docs/RM-116_AUDIT.md`.
- Preserve one provider, analyzer, Orchestrator, repository, context builder, strict JSON
  Schema, Decision Engine, document viewer, and exporter.
- Keep RM-107 as the only score/recommendation owner and preserve absolute critical
  stop-factor priority.
- Keep fallback offline and failure-safe. A citation/provenance error cannot stop
  deterministic analysis or promote stale evidence.
- Do not add fuzzy matching, OCR, web verification, external search, a vector database, a
  second RAG path, retry/failover/streaming, Chat Completions, or RM-117 analysis.

## Public provider metadata

Add an immutable public `AiProviderMetadata` contract with `provider_id` and `model`.
`AIProvider.metadata` returns that contract. Values are bounded, free of control characters,
and supplied explicitly by provider selection. The metadata contract must never contain an
API key, Authorization header, base URL, query/fragment, prompt, document text, response body,
or private path. The existing sanitized `raw_id` may be recorded as `provider_response_id`.

## Citation contract

Extend `AiEvidence`; do not add a parallel evidence model. Verified evidence contains:

- `citation_id` in the form `cit_<bounded hex>`;
- `document_id` and exact `quote`;
- zero-based `character_start` and exclusive `character_end`;
- locally derived `section` and optional `page`;
- model `confidence`, labelled “уверенность AI” in UI;
- closed `verification_method="exact_quote"`;
- valid source `checksum_sha256`;
- logical `source_ref` derived from document ID;
- current `context_fingerprint`.

`citation_id` is calculated locally from the context fingerprint, document ID, checksum,
offsets, and quote. Identical input produces the same ID; a changed checksum, context, locator,
or quote changes it. Unverified findings have no citation ID and cannot affect RM-107.

## Resolver contract

Create one pure resolver in `app/core/ai/citations.py`. It receives candidate evidence,
current `AiDocument` values, and the current fingerprint. It has no provider, repository, UI,
filesystem, or network dependency.

1. Resolve a document only by exact `document_id` and require a 64-character SHA-256 value.
2. Require a finite confidence in `[0, 1]` and a non-empty exact quote.
3. Find every case-sensitive continuous occurrence in `AiDocument.text`.
4. Parse enclosing `===== <label> =====` markers locally. `Страница N` supplies a PDF page.
5. For one occurrence, use local offsets and locator. Contradictory provider hints are ignored
   and reported only through a constant safe warning.
6. For multiple occurrences, provider page/section hints may select only among locally found
   matches. Verification requires exactly one locally matching occurrence; otherwise the
   finding is unverified.
7. Never normalize, fuzzy-match, infer, or preserve an unconfirmed locator.
8. Preserve source truncation in the source snapshot so UI/export can label it.

## Provenance contract

Add immutable `AiAnalysisProvenance` and `AiSourceSnapshot` models. Provenance contains a
locally generated analysis ID, current fingerprint, timezone-aware creation time, prompt,
provider-output schema, persisted schema, analyzer, context and citation resolver versions,
safe provider metadata, bounded response ID, and ordered source snapshots.

Each snapshot contains document ID, safe display name, document type, checksum,
verification status, timezone-aware received time or explicit `unknown`, truncation state,
included character count, and original character count. It never contains a local path, file
URL, full document text, prompt, raw response, exception, traceback, credential, or keyring
data.

## Context and versions

- `AiDocument.source` is `local_document_store`, never `source_path`.
- Display names use basename only; `source_ref` uses document ID only.
- Raise `AI_ANALYSIS_SCHEMA_VERSION` from the audited value 2 to 3.
- Add `CITATION_RESOLVER_VERSION` and include it in provenance and context fingerprint.
- Increase prompt/analyzer versions when their contracts change.
- Keep the RM-115 strict provider-output schema as the only raw output schema.
- No physical database migration is required.

## Serialization and compatibility

- Version-3 payloads serialize citations, provenance, and a source registry through
  `AiDocumentAnalysis.to_payload()` and round-trip through the existing repository.
- Version 1–2 payloads remain readable for safe display, but every legacy AI finding is
  `UNVERIFIED` and has no decision impact.
- A future version produces `CACHE_INCOMPATIBLE` with no verified findings.
- Missing or damaged version-3 provenance/citation data cannot produce `VERIFIED`.
- Cache reuse requires registry key, current fingerprint, schema/analyzer/context/output/
  prompt/resolver versions, and therefore the current document checksums.
- A corrupt newest row does not block an older valid row. A current provider failure is not
  replaced by stale success.

## UI navigation and export

- The existing AI tab shows statement, safe document name, locally confirmed page/section,
  exact quote, model confidence, shortened citation ID, and truncation state.
- An internal link contains only a validated citation ID. The dialog resolves it against the
  current normalized analysis and emits the known document ID; arbitrary schemes and unknown
  IDs are rejected.
- The controller opens the existing `TenderDocumentsDialog`. Its new
  `select_document(document_key: str) -> bool` API selects the row; the local file is not
  opened automatically.
- Unverified findings have no link and display
  “Неподтверждённый вывод — не влияет на рекомендацию”.
- JSON contains citations, provenance, and source registry but no document text or paths.
- HTML findings link only to escaped internal source anchors. The source section shows safe
  names, checksum prefixes, local locators, and citation IDs; it contains no file or external
  links. All values are HTML escaped.

## RM-107 eligibility

An AI finding may reach the existing decision input only when its status is `VERIFIED`, its
evidence and citation ID are valid, its checksum exists in the current source registry, its
fingerprint matches current provenance, and provenance is valid. This strengthens eligibility
only; score formulas, recommendations, deterministic facts, and stop-factor ordering do not
change.

## Required verification

Add `tests/test_ai_citations.py` and `tests/test_ai_provenance.py`; extend the schema, analyzer,
context, repository, service, output-schema, provider, Orchestrator, RM-107, full-analysis,
UI/document-navigation, and exporter tests listed in the RM-116 task contract.

Acceptance must cover unique and ambiguous quotes, locator agreement/conflict, exact offsets,
deterministic IDs, checksum/fingerprint changes, truncated sources, strict confidence,
timezone-aware provenance, legacy/future/corrupt cache, safe response metadata, private-path
exclusion, internal-link rejection, HTML injection, offline fallback, current-run decision
eligibility, and critical stop-factor priority.

Final validation is the exact RM-116 target contour followed by full pytest, Ruff check,
Ruff format check, the expanded mypy contour, repository secret scan,
`pip_audit --skip-editable`, and `git diff --check`. Record exact counts, versions, durations,
offline isolation, and the absence of a migration before opening the feature PR.

## Completion boundary

RM-116 remains `IN PROGRESS` through the feature PR. It becomes `DONE`, and RM-117 becomes
active, only after feature merge, a successful post-merge Windows Quality Gate on Python 3.12
and 3.13, and a merged docs-only closeout package.

## Feature acceptance evidence

The implementation satisfies the contract locally on Python 3.12.7:

- exact RM-116 target: `262 passed in 6.37s`;
- strict provider/output/UI regressions: `93 passed in 3.74s`;
- full suite: `1014 passed in 50.92s`;
- Ruff check/format, mypy on 16 fixed production files, repository secret scan,
  `pip_audit --skip-editable`, and diff hygiene passed;
- dependency audit reported no known vulnerabilities;
- no database migration or second AI workflow was added;
- offline/disabled/Ollama paths remain isolated from live provider, DNS, and keyring access.

These results prepare the feature PR and do not close the stage. RM-116 remains `IN PROGRESS`
and RM-117 remains planned until the completion boundary above is satisfied.
