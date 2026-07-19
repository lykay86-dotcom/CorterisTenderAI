# RM-147 tender analytics acceptance

## Verdict and publication status

Feature implementation, publication, PR-head gate, merge, and exact merge-SHA gate are complete.
The deterministic tender analytics page, filters, drill-down, exact export, provenance/partial
states, and bounded performance contract are covered locally and on Windows Python 3.12/3.13.

This separate docs-only package records canonical closeout. RM-147 is `DONE` and RM-148 becomes the
sole `IN PROGRESS` stage; RM-149–RM-200 remain `PLANNED`.

## Entry gate and traceability

- Exact baseline: RM-146 docs-only closeout merge
  `570ef10b9ea0666a09aa267cbcb47bab8882f401`.
- RM-146 feature PR #100 head: `72118c31a31f16b524c79ee83bc82a9daf7071fb`; feature merge:
  `e09af67931c3a63874e259bed08efc5ce3a14284`.
- RM-146 exact feature merge-SHA Quality Gate run `29686798140`: success; Python 3.13 job
  `88192371636`, Python 3.12 job `88192371659`.
- RM-146 closeout PR #101 head: `a2fb06da9cb4dc5a3f67bfbe17267928f4c0aadc`; closeout merge
  and RM-147 baseline:
  `570ef10b9ea0666a09aa267cbcb47bab8882f401`.
- RM-146 closeout Quality Gate run `29688334074`: success; Python 3.12 job `88197385864`,
  Python 3.13 job `88197386364`.
- Dedicated worktree/branch: `.worktrees/rm147`, `feat/rm-147-tender-analytics`.
- The unrelated root-checkout `.agents/` and `skills-lock.json` were not changed.

Local implementation lineage:

| Commit | Intent |
|---|---|
| `2eea4ee` | audit, source-of-truth, metrics, time, provenance, drill-down/export and plan contracts |
| `486dd04` | passing characterization of inherited owners |
| `150d8b9` | expected-red RM-147 contracts |
| `e33ea63` | deterministic aggregation, repository reads, chart adapter, exact export and benchmark |
| `40b8339` | production route/page/controller, exact drill-down, lifecycle, icon and frozen coverage |
| `b3f9a5b` | complete preset/custom/source/status/law/archive filter contract |
| `0fd1ca6` | audited RM-146 chart-consumer allowlist |
| `ea84b06` | local acceptance evidence |

The characterization contour passed 7 tests. The expected-red commit produced exactly 18 failures,
all caused by the intentionally absent RM-147 package, route, or seam; it exposed no inherited
regression.

## Accepted architecture and deterministic boundaries

- `app.tenders.analytics` owns immutable Qt-free contracts, the four-metric catalog, aware
  day/week/month interval rules, deterministic aggregation, RM-146 chart translation, exact
  JSON/CSV export, and generation-based view-model state.
- The four metrics are tender discovery by `first_seen_at`, current normalized tender status,
  source-reference observations, and application-deadline horizon. Their catalog IDs and semantic
  versions are fixed and ordered.
- Existing `TenderRegistryRepository` and `CollectorStateRepository` provide bounded bulk read-only
  facts. No new database, migration, cache, materialized view, provider, network request, collector
  execution, scheduled job, AI call, dependency, or second repository owner was added.
- The UI translates an immutable snapshot into the existing RM-146 `ChartWidget` API. Aggregation,
  filtering, evidence quality, and KPI semantics do not live in widgets.
- Route `future.analytics` is reused as the production `analytics` destination. The modern shell
  owns exactly one page/controller lifecycle and shuts it down once.
- Drill-down resolves the selected stable registry key through the existing tender registry
  controller/dialog path. Export writes the exact displayed snapshot, not a re-query.
- Query fingerprints canonicalize aware bounds in the display timezone. Moscow time supports the
  audited fixed `+03:00` fallback when zoneinfo data is unavailable. Naive record timestamps remain
  unknown and are not silently assigned a timezone.
- Partial, conflicted, stale, empty, error, unavailable, and too-large conditions remain explicit.
  A request above 10,000 records fails closed as `TOO_LARGE`; there is no hidden sampling.
- Stable IDs, ordering, contributor identities, query fingerprints, JSON, and CSV are deterministic.
  CSV formula-leading content is neutralized; control and bidi text is rejected; file replacement is
  atomic.
- Nothing in RM-147 changes RM-107 scoring, recommendation, critical stop-factor priority, money
  semantics, or an AI decision path.

## Filter, provenance, accessibility, and export acceptance

- Presets cover last 7 days, last 30 days, current month, custom range, and all available data.
- Grain, source, current status, law, archive inclusion, and aware interval bounds are part of the
  immutable query and fingerprint.
- Coverage, conflicts, unknown-time counts, source evidence, contributor identities, and exact
  point facts are retained through snapshot, chart/table presentation, selection, drill-down, and
  export.
- Four charts have complete native textual-table equivalents. Names, descriptions, keyboard focus,
  filter labels, status text, limitation text, and exact selection behavior are regression-tested.
- Light/dark theme integration reuses RM-143 tokens and RM-146 charts. Final design audit reports no
  literal color outside the theme.

Automated offscreen accessibility, keyboard, lifecycle, theme, route, drill-down, export, and frozen
self-test evidence is complete. A real installed EXE journey with Windows Narrator, native high
contrast, physical multi-monitor DPI, and a manual screenshot review is `NOT_EXECUTED`; no WCAG or
native assistive-technology certification is claimed by this package.

## Performance and boundedness evidence

Final benchmark environment: Microsoft Windows NT 10.0.19045.0, Python 3.12.7, PySide6 6.11.1;
2 warm-ups and 10 timed samples per size. Times are p50/p95 milliseconds. Each ordered/shuffled
fixture produced an equal semantic snapshot; service query count was zero, application read-query
count was four, and sampling was false for every size.

| Records | State | Aggregate | Adapter | Render | Selection | Peak bytes | Contributor bytes | JSON bytes | CSV bytes |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | EMPTY | 3.1348/5.3348 | 0.4214/0.5386 | 0.0707/0.1319 | 0.0002/0.0003 | 41,903 | 0 | 18,814 | 10,755 |
| 1 | READY | 3.0103/3.6893 | 0.4327/0.5563 | 0.5949/0.9263 | 0.0086/0.0582 | 48,787 | 60 | 19,627 | 11,199 |
| 10 | READY | 3.8808/5.1706 | 0.4830/0.7856 | 0.9668/1.2366 | 0.0086/0.0493 | 60,355 | 600 | 21,899 | 12,649 |
| 100 | READY | 6.0884/7.9297 | 0.4818/0.5520 | 0.6315/0.7444 | 0.0275/0.0657 | 85,594 | 6,000 | 28,408 | 18,431 |
| 1,000 | READY | 21.3252/23.4816 | 0.4959/0.6512 | 0.6089/0.7005 | 0.2077/0.2500 | 509,634 | 60,000 | 93,239 | 76,055 |
| 10,000 | READY | 202.7655/295.1390 | 0.5444/0.6538 | 0.7228/0.9833 | 0.3607/0.4608 | 4,536,548 | 600,000 | 741,298 | 652,107 |

The full matrix is reproducible with
`python scripts/benchmark_rm147_analytics.py --samples 10 --warmups 2 --sizes 0,1,10,100,1000,10000`.
The bound is exact-data, not downsampling: 10,001 records return `TOO_LARGE` with no sampled result.

## Test and quality evidence

| Contour | Exact result |
|---|---|
| final RM-147 focused set | `40 passed in 7.30s` |
| neighboring route/theme/frozen/UI set | `62 passed`; final UI subset `42 passed` |
| repository contour | `33 passed` |
| shell/lifecycle | `27 passed`; workflow-composition rerun `3 passed` |
| complete final suite at `0fd1ca6` | `2163 passed, 2 warnings in 165.42s (0:02:45)` |
| repository secret scan | `Repository secret scan passed.` |
| Ruff check | `All checks passed!` |
| Ruff format | `705 files already formatted` |
| canonical mypy | `Success: no issues found in 20 source files` |
| dependency audit | `No known vulnerabilities found`; editable project skipped |
| design-system audit | `matrix=45; styles=43; violations=0` |
| UI inventory | 87 modules, 34,092 lines, 132 UI test modules, no literal colors outside theme |
| migration/schema workflow smoke | `5 passed in 3.91s` |
| offline workflow smoke | `2 passed in 5.95s` |
| bootstrap integration smoke | `1 passed in 0.35s` |
| build/frozen workflow smoke | `7 passed in 4.36s` |
| Dashboard public import | `DashboardController` |

The two warnings are the unchanged openpyxl unsupported-extension and conditional-formatting
warnings in `test_rm132_legacy_credentials_handoff.py`; RM-147 adds no warning. The first complete
suite had one failure in the inherited RM-146 characterization because it still asserted that no
production chart consumer existed. The fix narrows that assertion to the two audited RM-147
consumer files; its focused rerun passed 6 tests and the subsequent complete suite passed all 2,163.

## GitHub acceptance and closeout

- Feature PR #102 head: `ea84b068d437cf2e4e2e366aa94bb079938587e5`.
- PR-head Quality Gate run `29692568668`: success. Python 3.12 job `88207743289` completed in
  `4m36s` with `2163 passed, 2 warnings in 146.82s`; Python 3.13 job `88207743293` completed in
  `4m40s` with `2163 passed, 2 warnings in 151.95s`.
- Feature merge SHA: `d85cf8c99f8ee72279bbb8054942a0f4d5675ac2`.
- Exact merge-SHA Quality Gate run `29693165086`: success. Python 3.12 job `88209342677` completed
  in `6m36s` with `2163 passed, 2 warnings in 257.05s`; Python 3.13 job `88209342717` completed in
  `4m48s` with `2163 passed, 2 warnings in 150.21s`.
- Both runs passed secret scan, Ruff check/format (`705 files`), canonical mypy (`20 source files`),
  offline/migration/import/composition/build/frozen smokes, full pytest, and dependency audit with
  no known vulnerabilities.
- The only annotations are existing non-blocking notices that GitHub is forcing official actions
  from Node.js 20 to Node.js 24. They did not change either job conclusion.
- This docs-only closeout updates `STATUS.md`, `ROADMAP.md`, and `ROADMAP_HISTORY.md`; it changes no
  application code, dependency, database, schema, migration, setting, or user data.

## Rollback, residual risks, and closeout gate

Rollback is a revert of the RM-147 branch commits to exact baseline `570ef10b`. No dependency,
schema, migration, persisted setting, credential, or user data downgrade is required.

Stop publication for any failed PR-head or exact merge-SHA gate, new vulnerability/warning,
non-deterministic shuffled result, missing contributor/provenance, hidden sampling, duplicate owner,
unexpected network/collector access, export mismatch, frozen failure, or changed business-decision
semantics.

All feature conditions in `DEFINITION_OF_DONE.md` are satisfied. The feature PR and exact merge-SHA
gate are complete, and this separate canonical docs-only closeout records RM-147 as `DONE` and
activates RM-148. RM-149 must not start until RM-148 separately satisfies Definition of Done.
