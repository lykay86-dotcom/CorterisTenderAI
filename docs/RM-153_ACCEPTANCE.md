# RM-153 acceptance evidence

## Scope and exact identities

- Canonical production baseline: `1c227c323c0e9912f9a8f44dc859703e2d3fcd36`.
- Audit package: `92986ab56452f31c4b1092346b40f96691f2d976`.
- Characterization: `c33bd916c73ea9833b08b97c4b944bc9b4b21ef2`.
- Expected-red: `0d0ee5995fc1166a5bca666cecea706a5b813511`.
- Production implementation: `db0b051795917daca3857d02bef950a44c9c9ff7`.
- Final evidence harness: `2c6c7cefbc853bc3a20d1020cbe56b6feda60e5d`.

The implementation changes only theme work owned by `ModernMainWindow`: idempotent real changes,
shell chrome/page stylesheet scoping, active-page propagation and route-time stale-page epochs.
All canonical page objects, router/history, controllers, repositories, transactions, shutdown owners
and deterministic decision paths are unchanged.

## Performance comparison

Baseline: 2 warmups + 10 samples. Final timing post: 2 warmups + 20 samples, same Windows host,
Python 3.12.7, PySide6 6.11.1 and offscreen Qt. The 20-sample nearest-rank p95 excludes only the
single worst sample instead of treating the maximum as p95.

| Scenario | Baseline p50 / p95 ms | Post p50 / p95 ms | p95 change | Guard |
|---|---:|---:|---:|---:|
| shell construction | 995.857 / 1114.509 | 566.100 / 627.888 | -43.7% | 1230 PASS |
| first paint | 189.244 / 232.923 | 132.485 / 157.609 | -32.3% | 260 PASS |
| shell shutdown | 9.247 / 10.213 | 7.491 / 10.210 | -0.0% | 12 PASS |
| canonical page switch | 26.907 / 47.737 | 22.158 / 36.344 | -23.9% | 55 PASS |
| Dashboard update, 1,000 rows | 50.908 / 59.853 | 22.504 / 31.753 | -47.0% | 66 PASS |
| theme switch | 633.348 / 742.422 | 167.983 / 188.245 | -74.6% | 820 PASS |
| workflow filter, 10,000 rows | 126.641 / 138.552 | 127.954 / 142.403 | +2.8% | 155 PASS |
| chart update, 1,000 points | 27.728 / 43.424 | 27.270 / 36.106 | -16.9% | 50 PASS |

The profiled targets required at least 20% p95 improvement. Shell construction and theme switch pass
at 43.7% and 74.6%. `RM-153_PERFORMANCE_POST.json` carries exact timing evidence.

## Resource evidence

A separate fresh-process run prevents the 20 lifecycle timing samples and standalone synthetic
chart cache from contaminating the shell resource interval. Over 25 alternating light/dark plus
Dashboard/tenders cycles:

- `QObject`: 1784 -> 1783;
- `QThread`: 0 -> 0;
- `QTimer`: 23 -> 22;
- active `QTimer`: 3 -> 2;
- Python threads: 1 -> 1;
- traced current/peak: 17,866 / 27,546 bytes.

All owner counts have non-positive growth and allocations pass 64/128 KiB budgets.
`RM-153_RESOURCE_POST.json` carries the exact evidence. The removed object/timer is bounded deferred
startup cleanup, not an owner created by the cycle.

## Visual, state and accessibility evidence

Eight 1540x940 offscreen captures covered Dashboard, tenders, workflow and analytics in dark and
light themes after route-time stale-page activation. Inspection found consistent page/chrome
palettes and no white table/corner strips in dark mode. The automated contour verifies that the
RM-152 `QTableCornerButton::section` and `QAbstractScrollArea::corner` fixes occur exactly once on
every activated page, and that route, stack, lifecycle and accessibility contracts remain intact.

This is not RM-154 pixel-golden acceptance. Native Windows interaction confirmation for startup,
theme switch, page switch, focus continuity and close remains required before RM-153 closeout.

## Security, privacy, migration and deterministic safety

- Benchmark data are synthetic and offline; no network, AI, credential, production DB, user
  settings or telemetry path is used.
- A memory-only settings substitute prevents Windows registry writes. Workflow data live under a
  bounded temporary directory.
- No dependency, database/settings schema, data migration, persistent cache or new lifecycle owner
  exists. The existing `ui/theme` value remains compatible.
- Score, recommendation, critical stop-factor priority, Decimal values, identities, routes,
  selection, transaction/backup semantics and exports are not read or changed by the optimization.
- Rollback is a feature-merge revert; no persisted-data downgrade or cleanup is required.

## Validation ledger

- expected-red before production: `2 failed in 10.55s`, both intended contract gaps;
- focused/neighboring post contour: `39 passed in 28.28s`;
- eight-page theme screenshot generation and inspection: PASS;
- deterministic timing post and resource post: PASS;
- repository secret scan: PASS;
- Ruff: PASS; Ruff format: `775 files already formatted`;
- mypy required contour: `Success: no issues found in 20 source files`;
- workflow offline smoke: `2 passed in 5.12s`;
- migration smoke: `5 passed in 3.35s`;
- public import: `DashboardController` PASS;
- composition-root smoke: `1 passed in 0.29s`;
- build/frozen smoke: `7 passed in 4.32s`;
- dependency audit: `No known vulnerabilities found`; editable project skipped by policy;
- initial full suite exposed two exact contract regressions after `2352 passed`; style matrix was
  extended from 45 to 47 exact sites and the RM-149 narrow static dispatch was preserved;
- final full suite: `2354 passed, 2 warnings in 193.39s`; both warnings are the accepted openpyxl
  unknown-extension/conditional-formatting fixture warnings;
- native worktree window launch: PASS; automated Windows Graphics Capture for this PySide6 window
  returned `0x80004002 (interface not supported)`, so no automated native clicks were continued;
- user native confirmation and GitHub exact-SHA gates: pending before closeout.
