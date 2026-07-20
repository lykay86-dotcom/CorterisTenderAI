# RM-153 UI performance and resource audit

## Entry gate and scope

- Canonical baseline: `1c227c323c0e9912f9a8f44dc859703e2d3fcd36`.
- The exact baseline Quality Gate run `29778715967` succeeded for Windows Python 3.12 and 3.13.
- `docs/STATUS.md` and `docs/ROADMAP.md` name RM-153 as the only `IN PROGRESS` stage.
- RM-154 visual goldens and RM-155 final acceptance are excluded.
- The approved RM-107 score, recommendation and critical stop-factor priority are immutable.

The audit covered startup composition, first paint, canonical route switches, Dashboard snapshot
updates, RM-150 table filtering, RM-146 chart updates, theme changes, bounded shutdown and repeated
theme/navigation resource cycles. Measurements are offline, deterministic and headless; they do not
exercise network, AI, credentials or production persistence.

## Existing owner inventory

| Concern | Existing owner | RM-153 decision |
|---|---|---|
| process/bootstrap lifetime | `app.bootstrap` and `app.main` | keep |
| shell and ordered close | `ModernMainWindow` | adapt only measured presentation work |
| page stack/router/history | `DashboardLayout` and RM-142 navigation contracts | keep |
| Dashboard data refresh | `DashboardController` | keep worker/timer/generation owner |
| workflow data and health | `BusinessWorkflowPage`, repository, `SystemHealthMonitor` | keep transaction and shutdown owners |
| analytics refresh | `TenderAnalyticsController` and page | keep |
| tables | RM-150 shared model/filter/selection contracts | reuse |
| charts | RM-146 chart contract and `ChartCanvas` | reuse |
| theme | `ModernMainWindow.apply_theme` plus current page adapters | adapt propagation only |

No new repository, service, router, page stack, worker pool, timer, dependency, database schema,
telemetry or network path is justified.

## Reproducible baseline

Command:

```text
python scripts/benchmark_rm153_ui.py --output docs/RM-153_PERFORMANCE_BASELINE.json
```

Environment: Windows 10.0.19045, Python 3.12.7, PySide6 6.11.1,
`QT_QPA_PLATFORM=offscreen`; two warmups and ten timed samples.

| Scenario | Fixture | p50 ms | p95 ms |
|---|---:|---:|---:|
| shell construction | full shell | 995.857 | 1114.509 |
| first paint | full shell | 189.244 | 232.923 |
| shell shutdown | full shell | 9.247 | 10.213 |
| canonical page switch | dashboard/tenders/workflow | 26.907 | 47.737 |
| Dashboard snapshot update | 1,000 rows | 50.908 | 59.853 |
| theme switch | full shell | 633.348 | 742.422 |
| workflow table filter | 10,000 rows | 126.641 | 138.552 |
| chart update | 1,000 points | 27.728 | 43.424 |

After 25 dark/light plus Dashboard/tenders cycles, growth was zero for descendant `QObject`,
`QThread`, `QTimer`, active timers and Python threads. Traced current/peak allocations were
22,640/30,524 bytes. This is a bounded characterization, not proof of process-wide leak freedom.

## Call-level profile

A `cProfile` smoke used the same harness with one small data sample and the 25 resource cycles.
It recorded 53 calls to `ModernMainWindow.apply_theme`: 21.519 seconds cumulative, including
2,935 `QWidget.setStyleSheet` calls at 21.323 seconds cumulative. The root-window stylesheet alone
accounted for 13.286 seconds; Dashboard local theme propagation accounted for 5.293 seconds and
workflow propagation for 2.835 seconds.

Two shell constructions spent 1.418 seconds in `ModernMainWindow.__init__`. Its measured callees
included 0.588 seconds in Dashboard construction, 0.592 seconds in the final all-page
`apply_theme`, 0.101 seconds in workflow construction, 0.068 seconds in tender-workspace
construction and 0.027 seconds in analytics construction.

## Findings and decisions

1. **P1 — duplicate startup theme propagation.** Every themed page receives the selected theme in
   its constructor, then the shell immediately applies the same theme to every page again. The
   profile attributes about 42% of the two profiled shell constructions to this final propagation.
   RM-153 will remove only this duplicate pass while keeping the root shell/top-bar theme.
2. **P1 — eager styling of hidden pages on every toggle.** Root styling plus all local page
   adapters repolish hidden surfaces. RM-153 will apply the local adapter to the active page and
   mark hidden adapters stale; a stale page must receive the current epoch synchronously before
   its route handler exposes it. The canonical router and page objects remain unchanged.
3. **P2 — eager page construction.** The shell still constructs all four canonical pages. Lazy page
   creation would change public composition/binding and close-order contracts, so it is not the
   default RM-153 slice. It remains a stop-and-audit item if the bounded theme change cannot meet
   the approved outcome.
4. **P2 — synchronous workflow/file callbacks.** RM-141 identified them, but this baseline does not
   show a failing representative budget. Moving them to threads without repository/thread-safety
   evidence is prohibited.
5. **P3 — table/chart updates.** Existing RM-150 and RM-146 owners stay within measured budgets;
   no optimization is authorized.

The selected implementation is therefore limited to theme-epoch propagation and duplicate startup
work. It does not alter business results, persistence, route identities, refresh ownership or
shutdown ordering.
