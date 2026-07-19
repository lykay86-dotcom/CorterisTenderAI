# RM-150 performance measurement plan

Baseline: `c7b9c2210dbcbb5db7b9b24fc81f0809d05f8d6b`

## Goal and baseline

RM-141 measured 10,000-row filter p95 at 148.005 ms on its recorded environment. That value is a
historical comparison point, not a portable machine-independent pass threshold. RM-150 records a new
pre-implementation characterization baseline in the dedicated worktree and repeats the exact harness
after implementation.

## Fixtures and operations

Deterministic seeded fixtures contain 0, 100, 1,000 and 10,000 rows, duplicate display labels/equal
sort keys, Unicode text, nulls, exact `Decimal`, mixed states, stable identities and revisions.
Measure separately:

1. Qt-free snapshot validation/construction;
2. initial model publication;
3. single-column and multi-column sort;
4. free-text no-match, sparse-match and common-match filter;
5. update with 1% changed, inserted and removed identities;
6. selection restoration for present and removed identities;
7. visible-snapshot/export projection;
8. repeated attach/update/detach lifecycle.

Representative adapters cover workflow, dashboard, provider, registry/search, editable rows, backup
and analytics. Repository, disk, network and AI time is excluded.

## Protocol

- Record OS, CPU, Python, PySide6, Qt platform, commit SHA and power/runtime caveats.
- Use a deterministic seed, five warmups and at least 20 measured samples per size/operation.
- Record p50, p95, maximum, row count, sample count and peak Python allocation via `tracemalloc`.
- Run with the offscreen Qt platform where the CI-compatible UI tests do so.
- Persist machine-readable JSON and a concise Markdown table through the benchmark script; do not
  hand-edit benchmark numbers.
- Compare before/after on the same machine and command. Report ratios as evidence, not universal
  latency promises.

## Acceptance

Correctness tests must pass at every size. Ordering, selection and export remain deterministic under
fixture shuffling. Operations must be bounded by the supplied snapshot and must not perform
repository/network/filesystem/AI work or create unbounded timers/threads. A material p95 or peak-memory
regression versus the recorded baseline blocks acceptance until explained and approved; 10,000-row
filter is also compared explicitly with RM-141's 148.005 ms historical result. Exact numbers and any
approved variance are recorded in `RM-150_ACCEPTANCE.md`.
