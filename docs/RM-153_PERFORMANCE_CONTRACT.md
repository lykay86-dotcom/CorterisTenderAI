# RM-153 UI performance and resource contract

## Measurement contract

`scripts/benchmark_rm153_ui.py` is the canonical offline harness. A comparable run uses the same
machine/runtime, offscreen Qt platform, fixture sizes, two warmups and at least ten timed samples.
Budgets are evaluated on p95; p50, min and max remain diagnostic. CI tests validate behavior and
resource invariants, not wall-clock milliseconds on shared runners.

The first measured baseline fixes these local guard ceilings:

| Scenario | p95 guard ceiling |
|---|---:|
| shell construction | 1230 ms |
| first paint | 260 ms |
| shell shutdown | 12 ms |
| canonical page switch | 55 ms |
| Dashboard snapshot update, 1,000 rows | 66 ms |
| theme switch | 820 ms |
| workflow filter, 10,000 rows | 155 ms |
| chart update, 1,000 points | 50 ms |

The ceilings are the measured p95 rounded above a roughly 10% same-host noise allowance. They are
not universal hardware promises. For the two profiled implementation targets, the post-change
same-host p95 must improve by at least 20%: shell construction at or below 891.607 ms and theme
switch at or below 593.938 ms. If either target cannot be reproduced, the change is not accepted as
an optimization and must be revised or rolled back.

## Theme propagation contract

- `ModernMainWindow` remains the sole theme owner and persists the selected `ThemeName`.
- The root stylesheet and top bar are updated synchronously for every real theme change.
- The active canonical page receives its local theme adapter synchronously.
- Hidden page adapters may be deferred, but each carries a shell theme epoch. A stale page is
  updated synchronously inside its existing route handler before route-specific state/refresh work.
- Applying the already-current theme is idempotent and performs no repolish or settings write unless
  the caller explicitly requests startup shell initialization.
- Dashboard, workflow and analytics keep their existing local adapters. Tender workspace continues
  to inherit the root stylesheet; no competing adapter is introduced.
- Deferred work must not add a timer, thread, worker, event bus or second router.

## Resource and lifecycle contract

Across 25 alternating theme changes and canonical route cycles:

- descendant `QObject`, `QThread`, `QTimer`, active `QTimer` and Python-thread growth is zero;
- traced current allocation is at most 64 KiB and peak allocation at most 128 KiB in the canonical
  harness;
- close remains bounded, idempotent and ordered through tender search, workflow, Dashboard and
  analytics owners;
- no callback may touch the shell after close begins;
- no user settings, credentials, network, production database or output file is accessed by the
  benchmark. A memory-only `QSettings` substitute and temporary workflow repository are mandatory.

## Deterministic and safety invariants

The optimization cannot change score, recommendation, critical stop-factor priority, Decimal
values, identities, selection, route context, export data, transaction/backup semantics or visible
operation truth. It adds no dependency, schema, telemetry or persistent cache. Timing evidence may
choose presentation work only; it can never choose or rewrite a business decision.

## Stop conditions and rollback

Stop on stale theme at first exposure, flash of an old local palette, route/focus/history drift,
added lifecycle owner, non-zero bounded resource growth, settings leakage, result/decision drift,
or any red full/frozen/Quality Gate. Rollback is a feature-merge revert; there is no data downgrade.
