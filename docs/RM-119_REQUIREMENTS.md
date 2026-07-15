# RM-119 Requirements — Explainable Application Requirements Analysis

Status: implementation contract
Baseline: `995d76c6eb1cc28661fec6e0a2f909447cd2abc2`
Branch: `feat/rm-119-application-requirements-analysis`

## Outcome and hard boundary

Extend the existing root `requirements` provider object and the existing
`AiDocumentAnalysis.requirements: TenderRequirements` domain object into an explainable,
locally scoped application-requirements analysis. It must use one provider response, verify every
candidate through the RM-116 resolver, report context completeness, persist current provenance,
render/export through the existing paths and leave RM-107 unchanged.

Do not add an `application_requirements` root object, provider call, analyzer, application
requirements service, Orchestrator, repository, database object, AI stage, prompt workflow,
classifier, citation resolver, UI workflow, exporter, Decision Engine, stop factor,
recommendation, participant-compliance assessment, legal/financial conclusion or rejection
probability.

## Canonical source scope

Define one public `APPLICATION_REQUIREMENTS_SOURCE_KINDS` in
`app/core/document_classification.py` containing exactly:

- `DocumentKind.APPLICATION_REQUIREMENTS`;
- `DocumentKind.APPLICATION_FORM`;
- `DocumentKind.INSTRUCTIONS`;
- `DocumentKind.PROCUREMENT_NOTICE`.

Context, analyzer, payload/provenance validation and tests must import this set rather than copy
its members.

## Domain contract and 21 groups

Add local `AiApplicationRequirementsStatus` values `not_found`, `complete`, `partial`, and
`unavailable`. Extend `TenderRequirements` with local `status`, `document_ids`,
`included_document_ids`, and `warnings`; do not create another dataclass. Define one explicit
`_APPLICATION_REQUIREMENTS_FINDING_FIELDS` tuple containing exactly:

1. `application_composition`;
2. `participant_eligibility`;
3. `declarations_and_consents`;
4. `equipment`;
5. `certificates`;
6. `licenses`;
7. `specialists`;
8. `documents`;
9. `experience`;
10. `deadlines`;
11. `warranty`;
12. `bid_security`;
13. `contract_security`;
14. `bank_guarantee`;
15. `submission_format_and_signature`;
16. `national_regime_and_origin`;
17. `price_proposal_and_estimate`;
18. `grounds_for_rejection`;
19. `ambiguities`;
20. `contradictions`;
21. `clarification_points`.

Provider `requirements` contains only these 21 mandatory finding arrays. Local metadata,
category, verification, severity, provenance, citations, links, score, recommendation,
participation, stop factors and legal/financial fields remain forbidden provider output.

## Classification contract

Keep one public `classify_document_kind(source_name, text)`. Recognize explicit application
requirements names/headings such as content/composition requirements, application requirements,
document lists and participant/application-composition requirements. A bare occurrence of
`заявка` is insufficient.

Preserve priority for procurement notices, instructions, application forms, TS, draft contracts
and estimates. Review protocols and actual participant applications remain outside the
application-requirements kind. Combined documents with explicit TS retain TS priority. The
deterministic analyzer and AI context must continue to call the same classifier.

## Context completeness

Add explicit application-requirements found/included counts, IDs and truncation to
`AiContextStatistics`. Generalize `_ScopedContextStatistics` to a set of document kinds and use it
for requirements, TS and contract scopes. Stable context order is TS, draft contract,
application requirements, application form, instructions, procurement notice, estimate, then
other.

Unavailable, unreadable, empty, truncated, total-limit omitted or checksum-deduplicated scoped
documents make the requirements context incomplete. Use only existing `StoredDocumentText`; do
not reread or download source files. All explicit statistics participate in the existing context
fingerprint.

## Strict provider schema and prompt

Keep one strict/extra-forbidden Pydantic schema, decoder, JSON Schema and Responses API
`text.format`. Missing, extra or duplicate keys; invalid nested types; NaN/Infinity; oversize
values; and provider-owned local fields reject the whole response. The one prompt must bind
requirements to the canonical four KIND values, retain the TS/contract boundaries, demand exact
continuous quotes and supplied IDs, forbid duplicate facts and invention, and prevent participant
compliance, rejection forecasting, legal/financial conclusions and all local decision fields.

## Evidence and status rules

Generalize `_scoped_findings()` to `frozenset[DocumentKind]` and reuse it for requirements, TS and
contract. Every candidate goes through the one RM-116 `resolve_citation()`. Evidence from TS,
contract, estimate, other, unknown/altered/locator-conflicting or provenance-damaged sources stays
unverified and makes requirements partial.

- `not_found`: no local document from the canonical source scope exists;
- `unavailable`: scoped documents exist but provider is disabled/errors, output is invalid or a
  safe result cannot be prepared;
- `partial`: scoped context is incomplete, a candidate is rejected/unverified, contradiction
  evidence is not independent or a scoped warning exists;
- `complete`: scoped documents exist, context is complete, payload is valid, every returned
  finding is verified and scoped warnings are empty.

Twenty-one empty arrays may be complete when context and response are otherwise complete.
Contradictions require two distinct canonical citation IDs; distinct offsets in one document are
allowed. Safe failure returns real found/included scoped IDs and empty findings.

## Payload, cache and versions

Current payload v6 stores exact `requirements` keys: status, document IDs, 21 finding groups and
warnings. Current verified requirements evidence requires current provenance and a source kind in
the canonical scope. Generic, TS, contract, estimate, other and unknown evidence cannot be
promoted.

Legacy v1-v5 preserves old 11-array statements only as unverified, uses status `unavailable`,
empty scoped IDs, an explicit legacy-unscoped warning and empty new groups. Future/corrupt cache
remains incompatible; current failure never falls back to stale success.

Increase exactly once: payload `5→6`, provider schema `3→4`, response format `v3→v4`, prompt
`5→6`, analyzer `6→7`, context `4→5`. Citation resolver remains `1`. Continue using the existing
SQLite table and versioned JSON; no migration is required.

## UI, export and security

Replace the existing flat AI heading with `Требования к заявке` in the current tab/export. Show
Russian status text, found/included counts, all 21 labelled groups, scoped warnings,
verified/unverified distinction, safe RM-116 citation links and an incomplete-context notice.
Use the explicit finding tuple for rendering and citation targets. JSON delegates to canonical
`to_payload()`; HTML escapes external values and uses only internal anchors. Never expose full
documents, raw response, prompt, credentials, exceptions, tracebacks or private paths.

## RM-107 invariants

Do not change participation policy/service, score, estimator, deterministic requirement rules,
stop-factor services, thresholds or recommendation types. Requirements findings do not enter
`_current_verified_ai_findings()` and never alter score, recommendation, action plan,
participation or stop factors. Existing verified generic findings retain their current review
effect, and a deterministic critical stop factor remains absolute at score 100.

## Required validation

Add `tests/test_ai_application_requirements_analysis.py` and extend the existing deterministic,
context, schema, analyzer, service, repository, provenance, runtime, TS, contract, export, UI and
RM-107 contours named in the task. Cover classification priorities, completeness/fingerprint,
strict 21-key output, all four statuses, evidence boundaries, independent contradictions,
current/legacy/future/corrupt cache, singular runtime, safe rendering and unchanged RM-107.

Baseline environment: Python 3.12.7, worktree-local `TEMP/TMP`,
`QT_QPA_PLATFORM=offscreen`, no live provider/DNS/keyring.

- Baseline SHA: `995d76c6eb1cc28661fec6e0a2f909447cd2abc2`.
- Target baseline: `277 passed in 14.82s`.
- Full baseline: `1080 passed in 59.11s`.

Final acceptance must record actual target/full counts, durations and final SHA plus:

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format . --check
python -m mypy
python scripts/check_repository_secrets.py
python -m pip_audit --skip-editable
git diff --check
```

The feature branch does not mark RM-119 `DONE`; feature merge, post-merge Windows Quality Gate and
a separate docs-only closeout remain mandatory.
