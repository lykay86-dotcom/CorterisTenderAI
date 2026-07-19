# RM-148 financial analytics acceptance

## Verdict and publication status

Feature implementation, PR-head gate, merge, and exact merge-SHA gate are complete. This separate
docs-only package records canonical closeout: RM-148 is `DONE`, RM-149 becomes the sole
`IN PROGRESS` stage, and RM-150–RM-200 remain `PLANNED`.

## Entry gate and traceability

- Exact feature baseline:
  `3c9ab31c7b65871e0367374ce084cf033c8a4534`.
- RM-147 feature PR #102 merged as
  `d85cf8c99f8ee72279bbb8054942a0f4d5675ac2`.
- RM-147 exact feature merge-SHA Quality Gate run `29693165086`: success on Windows Python 3.12
  and 3.13.
- RM-147 docs-only closeout PR #103 merged as
  `3c9ab31c7b65871e0367374ce084cf033c8a4534`.
- At feature entry, canonical documents identified RM-147 as `DONE`, RM-148 as the only
  `IN PROGRESS` stage, and RM-149–RM-200 as `PLANNED`.
- Dedicated worktree/branch: `.worktrees/rm148`, `feat/rm-148-financial-analytics`.
- The unrelated root-checkout `.agents/` and `skills-lock.json` were not changed.

Local implementation lineage:

| Commit | Intent |
|---|---|
| `b488468` | required audit, numeric/currency/rounding/margin/schema/parity/implementation decisions |
| `aa8f261` | passing inherited financial-boundary characterization |
| `399ac71` | exact expected-red core, persistence/migration and chart contracts |
| `a969149` | Decimal core, v3 persistence, migration, surfaces, export, recovery and resilience |
| `e38cb9a` | neighboring whole-RUB and RM-146 consumer contracts aligned to RM-148 |
| `7af9436` | exact XLSX import boundary, benchmark and local acceptance evidence |

The seven required decision documents were committed before production code. Characterization was
committed before expected-red, and expected-red was committed before the production package.

## Accepted numeric, currency, unit and margin contract

- `app.financial` is the single immutable, Qt-free owner for finite `Decimal`, typed value state,
  currency, units, canonical parsing/formatting, named rounding, aggregation, fingerprints, and
  JSON/CSV projection. The optional RM-146 chart translator is loaded lazily at the UI boundary.
- Existing workflow finance is explicitly `RUB`; audit evidence is the product UI, templates,
  reporting labels, and the accepted RM-145 workflow KPI. `UNKNOWN` remains a distinct state and
  mixed/unknown currency aggregation fails closed. RM-148 adds no FX or network path.
- Money uses the `money` unit, margin uses percentage points, and counts/ratios have distinct enum
  values. Missing, invalid, conflicted, unsupported-currency, out-of-range, stale, error, and exact
  zero are not interchangeable.
- Storage and standard presentation use two fixed decimal places. `ROUND_HALF_UP` is the named
  boundary rule; fixtures prove `1.005 → 1.01`, `2.675 → 2.68`, `10.115 → 10.12`, and
  `999999999.995 → 1000000000.00`.
- Margin is derived revenue margin `profit / total × 100`, never markup or a user-edited field.
  Zero/missing total produces missing margin. Aggregate margin is weighted
  `sum(compatible profit) / sum(compatible total) × 100`, never an average of percentages.
- No score, recommendation, critical stop-factor, AI/provider, tax, VAT, cash-flow, ROI, NMC-as-
  revenue, or probability-adjusted profit logic changed.

## Persistence, migration, audit and recovery

- `BusinessMetricsRepository.SCHEMA_VERSION` is 3. New records persist `total`, `profit`, and
  `margin_percent` as canonical fixed-point strings plus explicit `currency` and
  `margin_version`.
- Legacy JSON numbers are lexically decoded with `parse_float=Decimal` and are never rewritten by
  ordinary reads. Writes against v1/v2 stop with an actionable controlled-migration error.
- `BusinessMetricsV3Migration` provides deterministic dry-run issues, source SHA-256, exact source
  byte safety copy, fsynced temporary output, atomic replacement, every-record readback, and exact
  byte rollback under injected failure. Unsafe `NaN`, infinity, exponent, overprecision, and
  negative values block migration without changing source bytes.
- Repository replacement and ordinary writes use fsync plus atomic replacement. Corrupt stores
  fail closed; recovery first preserves exact quarantine bytes and restores them if verified backup
  recovery fails.
- Financial audit strings remain canonical and one event is recorded per changed field. Derived
  margin changes are explicit audit evidence; migration itself creates no false user event.
- Backup inspection, restore, and database health use shared Decimal/currency/version validation.
  The v3 `0.10`/`0.01` fixed strings survive backup and restore exactly.
- Concurrent-writer acceptance uses eight workers and forty records and preserves every stable ID
  and exact amount.

## Surface and export parity

One `FinancialAnalyticsSnapshot` owns current workflow total, the unchanged RM-145 potential-profit
contributor selection, and weighted margin. `BusinessMetricsRepository.summary()` now consumes this
owner instead of maintaining a second profit formula.

For the acceptance record `total=1.50 RUB`, `profit=0.25 RUB`:

| Surface | Accepted exact projection |
|---|---|
| workflow table/detail | `0.25 ₽`; Decimal sort key; tooltip includes RUB/unit/margin |
| Dashboard KPI | `0.25 ₽` from the exact metric value |
| RM-147 financial section | `0.25`, `money`, state and contributor IDs from the snapshot |
| RM-146 chart/accessibility | point `Decimal("0.25")`, label `0.25 RUB`, unit `RUB` |
| JSON | canonical string `"0.25"`, currency/unit/state/contributors/fingerprint |
| CSV | canonical `0.25,RUB,money` columns and snapshot fingerprint |
| XLSX | usable numeric cell plus hidden authoritative `FinancialExact` string metadata |

Workflow money editors are fixed-point text controls; they do not expose `QDoubleSpinBox`/binary
float values. Margin is read-only and derived by the shared owner. Dashboard, workflow, analytics,
chart, accessible table, and exporters translate immutable values and do not recalculate them.
Financial JSON/CSV export receives the displayed snapshot and performs zero repository reads.

The accepted RM-147 route/page/controller and RM-146 chart package are reused. RM-148 creates no
second primary route, chart framework, workflow repository, database, dependency, provider, or
network operation. The RM-149 tender-card redesign remains untouched.

## Performance and boundedness evidence

Reproducible command:

```text
python scripts/benchmark_rm148_financial.py
```

Environment: Windows, Python 3.12; 20 timed samples per size. Inputs are created before timing.
Times are p50/p95 milliseconds and memory is `tracemalloc` peak bytes for one immutable aggregation.
There is no sampling. The pure service and snapshot exporters make zero repository reads.

| Records | p50 ms | p95 ms | Peak bytes | JSON bytes | CSV bytes | Service/export reads |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.129 | 0.152 | 3,881 | 1,069 | 449 | 0 / 0 |
| 1 | 0.157 | 0.236 | 5,122 | 1,167 | 495 | 0 / 0 |
| 100 | 1.288 | 1.800 | 73,384 | 8,299 | 4,360 | 0 / 0 |
| 1,000 | 13.791 | 21.301 | 758,324 | 73,101 | 39,462 | 0 / 0 |
| 10,000 | 190.453 | 202.872 | 7,559,228 | 721,103 | 390,464 | 0 / 0 |

The automated 0/1/100/1,000/10,000 contour passed in `0.85s`; its 10,000-record call took `0.31s`
under pytest instrumentation, below the explicit five-second bound.

## Test and quality evidence

| Contour | Exact local result |
|---|---|
| focused exact/migration/chart/parity/performance/resilience | `38 passed in 14.06s` |
| RM-147 page + financial integration + repository/Dashboard neighbor | `11 passed in 4.59s` |
| required offline/migration/composition/build/frozen smokes | `15 passed in 16.12s` |
| first full suite | `2203 passed`, three expected stale presentation/consumer assertions |
| exact XLSX export/import/parity contour | `16 passed in 10.71s` |
| final full suite | `2209 passed, 2 warnings in 182.09s (0:03:02)` |
| repository secret scan | `Repository secret scan passed.` |
| Ruff check | `All checks passed!` |
| Ruff format | `722 files already formatted` before the acceptance document addition |
| canonical mypy | `Success: no issues found in 20 source files` |
| Dashboard public import | `DashboardController` |
| dependency audit after CI-equivalent pip upgrade | `No known vulnerabilities found` |

The two warnings are unchanged openpyxl unsupported-extension and conditional-formatting warnings
from `test_rm132_legacy_credentials_handoff.py`. RM-148 adds no warning. Automated build/frozen
contract and frozen self-test coverage pass; a newly built installed EXE, Narrator, native high-
contrast, physical DPI/multi-monitor journey, and manual screenshot certification were not executed
locally and are not claimed. The required Windows Python 3.12/3.13 evidence is recorded below from
the feature PR and exact merge-SHA Quality Gate.

## GitHub acceptance and closeout

- Feature PR #104 on head `7af94361f47660a44256751126a5871b34851202` was merged as
  `1116216cf00fc74dad2b870617c496242cd659c2`.
- PR-head Quality Gate run `29698349596` succeeded. Python 3.12 job `88222880837` reported
  `2209 passed, 2 warnings in 189.67s`; Python 3.13 job `88222880880` reported
  `2209 passed, 2 warnings in 142.97s`.
- No automatic push run appeared. The official workflow's `workflow_dispatch` path was therefore
  run on `main`; run `29699279963` reported exact
  `headSha=1116216cf00fc74dad2b870617c496242cd659c2`.
- In that exact merge-SHA run, Python 3.12 job `88225434927` reported
  `2209 passed, 2 warnings in 131.83s`, and Python 3.13 job `88225434947` reported
  `2209 passed, 2 warnings in 131.69s`. Every required step, including dependency audit, succeeded.
- This closeout is documentation-only: no application code, dependency, schema, migration,
  deterministic decision logic, score, recommendation, or critical stop-factor priority changes.

## Rollback, residual gate and next action

Code rollback is a revert of the RM-148 feature commits to exact baseline `3c9ab31`. Data rollback
uses the verified v2 safety bytes produced by the migration; ordinary compatibility reads do not
modify legacy bytes. Stop publication on any migration issue, currency mismatch, parity/fingerprint
change, new dependency or network path, warning/vulnerability, failed Windows matrix job, or changed
deterministic decision semantics.

All feature and publication conditions are satisfied. This separate canonical docs-only closeout
records RM-148 as `DONE` and activates RM-149. RM-150 must not start until RM-149 satisfies the
Definition of Done and its canonical status is updated.
