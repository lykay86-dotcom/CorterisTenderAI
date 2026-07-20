# RM-151 operation feedback acceptance

## Verdict and publication status

`READY FOR FEATURE PR` on the local Windows/Python 3.12 contour. RM-151 establishes one
immutable Qt-free operation-episode vocabulary, fail-closed transitions, safe user feedback,
bounded diagnostic correlation, a compatibility adapter over the existing notification owner and
coalesced accessible updates. Existing business, lifecycle, scheduler, crash, support, routing and
deterministic decision owners remain authoritative.

This feature package intentionally leaves RM-151 `IN PROGRESS`. It must not become `DONE`, and
RM-152 must not become active, until the feature PR is merged, the Quality Gate succeeds on that
exact merge SHA for Windows Python 3.12 and 3.13, and a separate docs-only closeout is merged.

## Entry gate and lineage

- Feature baseline: `c07773772a360d9bd6f7a3da0b18f44c6315d725`, the RM-150 docs-only
  closeout merge.
- RM-150 feature PR #108 merged as `8d6640691ca3e0fc6a22d7e6dd2d732955e0eedd`.
- RM-150 exact feature merge-SHA Quality Gate run `29708473745` succeeded on Windows Python
  3.12 and 3.13.
- RM-150 docs-only PR #109 merged as the feature baseline above; post-closeout exact-SHA run
  `29708921882` succeeded.
- Canonical documents make RM-151 the only `IN PROGRESS` stage and keep RM-152-RM-200
  `PLANNED`.
- Dedicated worktree and branch: `.worktrees/rm151`, `feat/rm-151-operation-feedback`.
- Pre-production audit/contracts: `c64f3c6`; characterization: `abeeecd`; expected-red:
  `0f91d94`; Qt-free core: `b719417`; owner adapters: `c233087`; bounded measurements:
  `627faf8`; safe consumer regression expectations: `1dd2971`.
- Expected-red was observed before production implementation: 20 failures, comprising 19 missing
  `app.operations` contracts and one missing scheduler adapter. Secret scan, Ruff and formatting
  remained green at that point.
- Unrelated root-checkout `.agents/` and `skills-lock.json` were not changed.

The work closes `UI-141-012` and covers J02/J07/J08/J09/J10/J13/J15 without starting the broader
RM-152 accessibility matrix.

## Audit and owner decisions

The pre-production inventory classifies 30 operation groups and records trigger, exact subject
identity, business owner, lifecycle owner, states, feedback path, cancellation/retry/close rules,
persistence, risk and keep/adapt/migrate evidence. The baseline counts 17 worker classes, 11
`QRunnable` references, one `QThread`, two `QThreadPool` constructions, six timers, 134 message-box
calls, 13 status-bar messages, 14 rich-text calls and 77 direct exception-string candidates.

The implementation reuses:

- `TenderSearchUiController` as the only collector/document/analysis/AI/score worker owner;
- `TenderCollectorSchedulerUiController` and its sole `CollectorNotificationRepository`
  construction as notification persistence and action owners;
- RM-142 route and exact identity admission, RM-143 presentation states and RM-144 shutdown;
- existing crash-report, support-bundle, workflow health/recovery and repository services;
- RM-107 scoring, recommendation and critical stop-factor priority without modification.

No task framework, event bus, second shell, scheduler, notification repository, crash store or
diagnostic persistence database was introduced.

## Accepted contracts and integrations

- `OperationEpisode` and `OperationEvent` are frozen/slotted values with aware-time and identity
  invariants. States include `IDLE`, `QUEUED`, `RUNNING`, `PARTIAL`, `CANCELLING`, `SUCCEEDED`,
  `FAILED`, `TIMED_OUT`, `CANCELLED` and `CLOSED`, preserving RM-140 semantics.
- Transitions are fail-closed. Retry creates a new attempt linked to its parent; cancellation is
  first requested and becomes terminal only on owner confirmation. Duplicate, stale-generation,
  late-terminal and post-close events cannot reopen an episode.
- Safe feedback is allowlist-first and bounded. Unknown exceptions produce a neutral user message
  plus an opaque correlation ID; raw exception text, credentials, DB URLs, local paths, URL
  query/fragment, traceback, markup/script, bidi and control markers are absent from user,
  notification, status, accessibility and clipboard summaries.
- The bounded in-memory diagnostic registry retains safe context and a retrieval route without
  mutating approved crash/support artifacts. User-visible summaries do not reveal artifact paths.
- Notification envelopes use typed identity, revision/freshness, dedupe and action validation. The
  schema-v1 adapter reuses the capped atomic legacy repository and rejects future schema; read or
  dismiss state does not delete diagnostic evidence.
- Announcement coalescing emits progress at bounded 10% buckets, preserves terminal updates and
  releases active episode state after terminal completion.
- Search mirrors immutable episodes without replacing its lifecycle. Dashboard, document,
  requirements, full-analysis, AI, score, provider, verification, workflow, crash and support
  boundaries use safe projection while retaining their current owners.

The three full-suite failures observed during acceptance were stale tests requiring raw worker
messages (`network unavailable`, `score calculation failed`, `text extraction failed`). Commit
`1dd2971` changes those assertions to require an opaque diagnostic reference and explicitly reject
the raw exception. The production behavior was not weakened to satisfy legacy expectations.

## Security and correctness evidence

- Malicious synthetic fixtures cover fake credentials, Windows and Unix paths, DB URLs, URL
  query/fragment, traceback, HTML/script and bidi/control characters; no live secret or user report
  is used.
- `scripts/check_rm151_operation_boundaries.py` statically rejects raw exception-to-UI paths on the
  migrated surfaces, dynamic rich HTML, Qt/keyring imports in the core, duplicate notification
  repository construction and duplicate shell ownership.
- Tests cover exhaustive canonical transitions, terminal immutability, retry parentage, confirmed
  cancel, stale revision/generation, exact notification target, duplicate delivery, read/dismiss,
  legacy restart compatibility, future-schema rejection and bounded diagnostic/announcement
  retention.
- No formatter, notification center or diagnostics viewer performs an implicit network, provider,
  AI or secret readback call.

## Performance and lifecycle evidence

`docs/RM-151_PERFORMANCE_BASELINE.json` records the inherited owners before production changes;
`docs/RM-151_PERFORMANCE_POST.json` records post-implementation sizes 0, 1, 100, 1,000 and 10,000
on Windows 10 / Python 3.12.7 with three warmups and ten repetitions. Timing is observational:
RM-151 adds no arbitrary budget (`pass_thresholds: null`).

| 10,000-event canonical scenario | p50 ms | p95 ms | output count | peak bytes |
|---|---:|---:|---:|---:|
| safe feedback projection | 0.304 | 0.577 | 1 | 4,049 |
| schema-v1 notification adapter | 0.196 | 0.234 | 1 | 3,982 |
| announcement coalescing | 1,227.489 | 1,315.180 | 12 | 7,365 |

The safe output remains 210 characters and one item independent of event count. Announcement
output is bounded to 12 items at 100/1,000/10,000 events, and active coalescer retention is zero
after a terminal event. One thousand duplicate legacy notifications yield one persisted item; the
legacy repository remains capped at 200. The measurement artifact identifies production baseline
`c07773772a360d9bd6f7a3da0b18f44c6315d725` and measurement head
`c23308739aa55c75030a98cb9ef69f912456a0ad`.

## Exact local verification

Environment: Windows 10 `10.0.19045`, Python 3.12.7. All pytest commands used a dedicated
`--basetemp` inside the RM-151 worktree because the sandbox cannot access the user-profile pytest
temporary directory.

| Contour | Exact result |
|---|---|
| focused RM-151 characterization/contracts/security/integration/performance | `42 passed in 11.34s` |
| neighboring RM-140/RM-144/dashboard/scheduler/crash/support contour | `35 passed in 10.14s` |
| offline provider and diagnostic-script smoke | `2 passed in 7.78s` |
| migration/schema smoke | `5 passed in 4.81s` |
| controller public import | `DashboardController` |
| bootstrap tender-search integration | `1 passed in 0.49s` |
| build/release and frozen self-test | `7 passed in 6.84s` |
| corrected raw-error regressions | `3 passed in 5.56s` |
| full repository suite | `2318 passed, 2 warnings in 138.70s` |
| repository secret scan | `Repository secret scan passed.` |
| RM-151 owner/static guard | `RM-151 operation boundary guard passed.` |
| Ruff check | `All checks passed!` |
| Ruff format | `761 files already formatted` before this acceptance document |
| canonical mypy | `Success: no issues found in 20 source files` |
| dependency audit | `No known vulnerabilities found` |

The two warnings are unchanged openpyxl unsupported-extension and conditional-formatting warnings
from `test_rm132_legacy_credentials_handoff.py`; RM-151 adds no warning. Dependency audit required
read-only network access after the sandbox correctly blocked its first attempt.

## Residual manual and CI evidence

- Local Python 3.13: `NOT_EXECUTED`; the required Python 3.12/3.13 matrix belongs to the PR-head
  and exact merge-SHA Windows Quality Gates.
- Newly packaged executable launch on physical Windows: `NOT_EXECUTED`; build/frozen contract and
  frozen self-test are green, while final packaging remains release scope.
- Narrator, physical keyboard-only walkthrough, high-contrast theme and physical DPI inspection:
  `NOT_EXECUTED`; automated accessible text/coalescing is accepted here, and the full native matrix
  remains RM-152 scope.
- Screenshot/golden visual certification and formal performance budgets are not claimed; they
  remain RM-154 and RM-153 work respectively.

## Scope, rollback and next action

- No DB schema, migration, dependency, settings, notification storage schema, network/AI flow,
  business formula, score, recommendation or critical stop-factor priority changed.
- Rollback is a revert of the RM-151 feature commits to baseline `c077737`; no data, dependency,
  schema or settings rollback is required.
- Next action is the feature PR titled
  `feat(rm-151): unify operation episodes and safe feedback`. This document must be finalized with
  feature PR/head/merge and exact Quality Gate evidence only in the later docs-only closeout.

