# RM-119 Application Requirements Analysis — Implementation Plan

Baseline: `995d76c6eb1cc28661fec6e0a2f909447cd2abc2`
Branch: `feat/rm-119-application-requirements-analysis`

## Phase 1 — audit gate

1. Verify canonical active stage, final-main SHA and clean tracked worktree.
2. Run isolated target/full baselines.
3. Inspect versions, classifier, provider graph, context, payload/cache, UI/export and RM-107.
4. Commit only `docs/RM-119_AUDIT.md`.

## Phase 2 — RED contract

1. Add the canonical 21-group/status/source-scope tests first.
2. Extend version/schema/classification/context/cache/runtime/UI/export/RM-107 regressions.
3. Run the focused contour and preserve the expected pre-implementation failure.
4. Commit tests and implementation-contract documents without production changes.

## Phase 3 — domain and classification

1. Export the single canonical application source-kind set.
2. Harden the one classifier while preserving established document priorities.
3. Extend `TenderRequirements` in place with local metadata and 21 explicit finding fields.

## Phase 4 — context, schema and prompt

1. Generalize scoped context statistics to kind sets and add application completeness fields.
2. Apply the required stable context ordering and mark every scoped omission path incomplete.
3. Extend the existing strict `requirements` provider object and one prompt.
4. Raise payload/provider/prompt/analyzer/context versions exactly once.

## Phase 5 — analyzer, payload and presentation

1. Reuse generalized scoped normalization and independent-citation validation.
2. Extend safe failure and service completeness application.
3. Implement exact v6 requirements payload/current provenance validation and fail-closed legacy.
4. Extend the current AI tab, citation navigator and existing JSON/HTML exporter.
5. Preserve the RM-107 generic-only decision boundary and existing SQLite repository.

## Phase 6 — acceptance

1. Run the exact target contour, full pytest, Ruff check/format, mypy, secret scan, dependency
   audit and diff check in the offline environment.
2. Perform the required adversarial static review and record exact counts, durations and SHA.
3. Commit feature acceptance, publish the feature branch and open the specified feature PR.
4. Keep RM-119 `IN PROGRESS` until feature merge, post-merge gate and docs-only closeout.
