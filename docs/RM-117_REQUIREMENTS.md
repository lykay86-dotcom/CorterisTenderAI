# RM-117 Requirements — Explainable Technical Specification Analysis

Status: implementation contract
Baseline: `343cd425e4f3f0eb1b22a1c4b2c41d8c3e2e0f24`
Branch: `feat/rm-117-technical-specification-analysis`

## Outcome

Extend the single `AiDocumentAnalysis` result with a locally controlled technical-specification
subsection. It identifies TS documents deterministically, extracts only from those documents in
the one provider call, verifies evidence with the RM-116 resolver, reports completeness honestly,
and renders/exports the result without changing RM-107.

## Required groups and local status

The strict provider object has exactly these required finding arrays: `scope`, `deliverables`,
`quantities_and_volumes`, `technical_characteristics`, `materials_and_equipment`,
`standards_and_regulations`, `execution_conditions`, `stages_and_deadlines`,
`acceptance_and_quality`, `customer_inputs_and_dependencies`, `ambiguities`, `contradictions`,
and `clarification_points`.

Local code assigns `not_found`, `complete`, `partial`, or `unavailable`; discovered/included TS
document IDs, warnings, truncation/completeness and verified state are never provider-controlled.

## Acceptance rules

1. One public pure classifier owns `_DOCUMENT_KIND_RULES`; deterministic analysis and AI context
   use it. `AiDocument.document_kind` is separate from its file-format `document_type`.
2. Context ordering is stable and prioritizes TS, then notice/estimate, then other documents.
   Found-but-truncated or omitted TS context is partial and changes the fingerprint.
3. The provider schema requires the nested object, forbids extras/default omissions and reuses the
   canonical candidate finding payload. A malformed nested value rejects the whole response.
4. Provider/prompt/analyzer/context and persisted payload versions increase from the audited
   post-RM-116 values. Old supported payloads read safely with an unavailable empty TS section;
   future/corrupt payloads remain incompatible; old fingerprints cannot be reused.
5. The prompt permits TS findings only from locally classified TS documents and forbids invented
   facts/questions and all local status/decision fields.
6. Every verified TS finding passes the one RM-116 resolver and belongs to a known TS document.
   Non-TS, unknown, altered or incomplete evidence remains unverified. Clarification points need
   cited grounds. Contradictions require all necessary distinct source citations.
7. Structurally valid unverified items are retained, clearly marked, and make the subsection
   partial. Stable local deduplication must not collapse distinct sources.
8. The existing service, Orchestrator, repository, one provider call and `RUNNING_AI` stage remain
   singular. Error/disabled results are not cached as success and do not fall back to stale success.
9. The existing AI tab and export button render/export all 13 groups, safe sources, verified and
   unverified distinctions, Russian status text and truncation warnings. External text is escaped;
   private paths, raw responses/errors, credentials and tracebacks never appear.
10. TS-specific findings do not independently affect RM-107 score/recommendation. Unverified TS
    findings have no decision effect; critical stop-factor remains absolute.
11. The existing SQLite table/columns remain unchanged; no migration is required.
12. Bootstrap/settings/offline tests perform no network or real credential access. No raw provider
    response, prompt or full document is persisted or logged.

## Required cases

- classification by filename and text heading; deterministic/AI agreement; contract false-positive
  rejection; stable TS priority; duplicates/empty/unavailable behavior;
- complete TS, not found, disabled/error, truncated/omitted TS;
- non-TS and unknown document IDs, altered quote, incomplete provenance, malformed nested object;
- valid multi-source contradiction and unsupported clarification point;
- legacy/future/corrupt payload handling and fingerprint/cache isolation;
- one provider call/component graph and one AI stage;
- complete/partial/not-found/unavailable UI, verified/unverified evidence, XSS escaping, safe JSON
  round-trip and successful render after an error;
- RM-107 score, stale-cache and critical stop-factor regressions.

## Validation record

Baseline environment: Python 3.12.7, worktree-local `TEMP/TMP`,
`QT_QPA_PLATFORM=offscreen`, no live provider/DNS/keyring.

- Target baseline: `201 passed in 14.32s`.
- Full baseline: `1030 passed in 68.21s`.

Final acceptance must record exact target/full counts and durations plus:

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format . --check
python -m mypy
python scripts/check_repository_secrets.py
python -m pip_audit --skip-editable
git diff --check
```

Feature-branch completion does not mark RM-117 `DONE`; merge, post-merge Windows Quality Gate on
Python 3.12/3.13 and a separate docs-only closeout remain mandatory.

## Local implementation acceptance

Implementation checkpoint: `82b19ba74a068f9c5bdd8453d64693d087b028b0`
Baseline: `343cd425e4f3f0eb1b22a1c4b2c41d8c3e2e0f24`
Python: `3.12.7`

- Exact RM-117 target contour: `214 passed in 12.31s`.
- Full suite: `1043 passed in 50.92s`.
- `python -m ruff check .`: passed.
- `python -m ruff format . --check`: passed (`509 files already formatted`).
- `python -m mypy`: passed (`16 source files`).
- `python scripts/check_repository_secrets.py`: passed.
- `python -m pip_audit --skip-editable`: no known vulnerabilities; the editable project was
  skipped as expected.
- `git diff --check`: passed.

Architecture inspection found one production `provider.analyze(...)`, one provider/analyzer/
analysis service/Orchestrator/repository graph, one `RUNNING_AI` stage, no TS service/repository/
table/column/migration and no change to `ParticipationDecisionService`. The adversarial review
also proved that semantic document kind is current provenance, non-TS cached evidence is
downgraded, and TS omission/truncation statistics participate in the cache fingerprint.

This remains feature-branch acceptance only. RM-117 is still `IN PROGRESS`; feature merge,
post-merge Windows Quality Gate on Python 3.12 and 3.13, and a separate docs completion PR are
not yet complete.
