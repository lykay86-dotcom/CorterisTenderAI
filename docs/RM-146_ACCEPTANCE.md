# RM-146 accessible chart layer acceptance

## Verdict and publication status

Feature implementation, publication, PR-head gate, merge and exact merge-SHA gate for
`UI-141-007` are complete. This separate docs-only package records canonical closeout and activates
RM-147.

## Entry gate and traceability

- Exact baseline: RM-145 docs-only closeout merge
  `cf2bc8f080ad006131ab501863a424dcede30a1c`, PR #99.
- RM-145 feature PR #98 head:
  `ac846e9e6cfa6c8ab77c445810cd081097478bc8`; feature merge
  `ac8d2662911e8a0e450fcb20677f99082187793a`.
- RM-145 exact feature merge-SHA Quality Gate run `29680204767`: success on Windows Python
  3.12/3.13.
- RM-145 closeout PR #99 head:
  `aa3baf9a80a487a67383ef36b85ce076983d470a`; exact closeout run `29680893803`, attempt 2:
  success on Windows Python 3.12/3.13.
- Baseline full suite: `2095 passed, 2 warnings in 184.19s (0:03:04)`.
- Dedicated worktree/branch: `.worktrees/rm146`,
  `feat/rm-146-interactive-chart-layer`. The unrelated root-checkout `.agents/` and
  `skills-lock.json` remain untouched.
- All six required audit/contract/plan documents were committed in `aeb02e7` before tests or
  production code.
- Passing characterization `0d1584b`: `6 passed in 1.36s`.
- Expected-red `162bd08`: exactly 15 failures, all
  `ModuleNotFoundError: app.ui.charts`; no inherited regression.

Implementation lineage after the gates:

| Commit | Intent |
|---|---|
| `236f916` | immutable model and deterministic render plan |
| `c640ebb` | one QPainter backend, exports, table, and interaction |
| `365f301` | security/DPI/large-series/lifecycle/frozen hardening |
| `199dc5f` | strict targeted mypy correctness |
| `aaaadf2` | isolated, hidden frozen chart smoke |
| `e4ccaa6`, `06323f2` | deterministic offscreen hover acceptance harness |

## Backend and licensing/dependency decision

One repository-owned `QWidget`/`QPainter` backend is selected. `QImage` and `QSvgGenerator` reuse
the existing PySide6 QtGui/QtSvg distribution. No runtime/build dependency, lockfile, hidden-import
rule, license file, or second chart framework was added.

| Candidate | Decision | Evidence |
|---|---|---|
| QWidget/QPainter | selected | existing dependency; full keyboard/text/theme/export control; offscreen and frozen evidence green |
| PySide6.QtCharts | rejected | official commercial/GPLv3 terms and deprecated since Qt 6.10 |
| PySide6.QtGraphs | rejected | official Qt licensing identifies a GPL-only/commercial surface |
| pyqtgraph | rejected | MIT, but adds pyqtgraph/NumPy/build/frozen/accessibility surface |
| Matplotlib Qt canvas | rejected | compatible project license, but heavy transitive/font/backend/frozen surface |

The repository has no root `LICENSE`/`LICENSE.md`, so no project distribution license was assumed.
The technical audit is not legal advice. Official links and the complete rationale are recorded in
`RM-146_CHART_TECHNOLOGY_AUDIT.md`.

## Accepted architecture and public API

The only public boundary is `app.ui.charts`, contract version `corteris-chart-v1`.

- Frozen immutable `ChartSpec`, `ChartSeries`, `ChartPoint`, `ChartAxis`, `ChartSelection`, closed
  kinds/scales/states/roles/styles/causes, and checked `ChartViewport`.
- `ChartSourceEvidence` is exactly the existing RM-145 `DashboardSourceEvidence` type alias and
  re-export, not a duplicate provenance/freshness lineage.
- One `normalize_chart` builds one immutable `ChartRenderPlan`; one `paint_chart` consumes it for
  screen, PNG, and SVG.
- One `ChartTableModel` is the complete native textual equivalent. One `ChartWidget`/`ChartCanvas`
  owns focus, mouse, keyboard, tooltip, and typed selection only.
- Exact data exports are `export_chart_json` and `export_chart_csv`; bounded visual exports are
  `export_chart_png` and `export_chart_svg`.
- Backend classes are not part of consumer input contracts. Future breaking enum/field/validation
  or serialization changes require a new contract version; no speculative legacy aliases exist.

Supported kinds are categorical bar and numeric/aware-time line. Category line, numeric/time bar,
3D, animation, hidden aggregation/downsampling, browser/webview runtime, remote fonts/assets, and
real analytics consumers are unsupported.

## Data, axis, state, and deterministic behavior

- IDs are bounded ASCII tokens and unique in their parent. Series/point tuples preserve caller
  order; presentation never sorts business data.
- Y is exact finite `Decimal` or `None`. Floats, NaN/infinity, naive datetime, control/bidi text,
  duplicate IDs, invalid kind/axis combinations, and out-of-range render coordinates are rejected.
- `None` remains a missing bar/line gap and complete textual/data row; zero remains a real mark.
- At most six series and 10,000 points per series are valid for bounded exact data output. Visual
  rendering is capped at 1,000 total points; larger valid input becomes `TOO_LARGE` with zero marks.
- No chart code queries a repository/provider, opens a network connection, uses current time or
  randomness, calculates a KPI, changes score/recommendation/stop-factor logic, aggregates,
  samples, rounds business values, or persists data.
- `LOADING`, `READY`, `EMPTY`, `PARTIAL`, `STALE`, `ERROR`, `TOO_LARGE`, and `UNAVAILABLE` have
  distinct visible/accessibility text. Caller evidence/state remains authoritative.
- Equal fixtures produce equal specs/plans/table rows and byte-identical UTF-8 JSON/CSV. JSON uses
  exact decimal strings/aware ISO time; CSV preserves rows/missing and neutralizes formula-leading
  text. Neither contains current time, address, random value, or widget state.

## Theme, interaction, and accessibility evidence

- Only RM-143 `chart_1`–`chart_6`, `chart_grid`, `chart_axis`, semantic text/background, and focus
  tokens are resolved. Design audit found no literal colour outside the theme.
- Light/dark plans have identical semantic projection and distinct palette projection. Series also
  use label plus marker/line pattern; meaning is not colour-only.
- Mouse hover exposes escaped plain tooltip-equivalent text without selecting. Primary click and
  keyboard resolve the same stable series/point IDs and emit typed cause.
- Left/right, up/down, Home/End, Ctrl+Home/End, Enter/Space, Escape, F2, Tab/Shift+Tab behavior is
  covered. Focus is visible and ordinary Qt focus traversal prevents a trap.
- Accessible canvas name/description includes title, kind, counts, state, limitation, selection,
  and the F2 instruction. The native table exposes every source point including missing values.
- Selection persists across resize/theme/data refresh by stable ID and clears when the ID
  disappears. Twenty update/theme/resize cycles add no child widget; deferred delete invalidates
  the chart widget.
- HTML-like tooltip text is escaped; control/bidi text is rejected; SVG contains no script or
  external `href`; synthetic artifacts contain no credential/user fixture.

Automated accessibility/interaction acceptance is complete. Windows Narrator, native high
contrast, physical per-monitor movement at 125/150/200%, screen-edge tooltip observation, and a
manual keyboard-only journey are `NOT_EXECUTED` and handed to RM-152. This package does not claim
WCAG certification.

## Export, resize, DPI, and measured limits

JSON/CSV are in-memory exact bytes. PNG/SVG use the same semantic plan and accept logical dimensions
320–4096 by 200–4096, scale 1.0–4.0, and at most 16,777,216 physical pixels. Invalid allocation is
rejected before painting. The caller owns path/dialog/atomic file policy.

Automated PNG decoding verified exact physical size at 100%, 125%, 150%, 200%, and 400%; SVG kept
the 640x360 logical view box. Resize A→B→A preserves semantics/data/selection while geometry changes.
Native per-monitor DPI remains `NOT EXECUTED` as stated above.

Final benchmark environment: Windows 10 `10.0.19045`, Python 3.12.7, PySide6 6.11.1, offscreen,
800x450, warm-up 2, 10 timed samples, dark and light. The table reports the slower observed theme
as `p50/p95 ms`; raw per-theme results are reproducible with `scripts/benchmark_rm146_charts.py`.

| Points | State/marks | Normalize | Paint | Hit test | JSON | CSV | PNG | SVG |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | EMPTY / 0 | 0.061/0.063 | 0.814/1.103 | 0.002/0.002 | 0.109/0.115 | 0.025/0.026 | 18.829/19.394 | 0.628/0.691 |
| 1 | READY / 1 | 0.339/0.357 | 1.576/2.028 | 0.011/0.013 | 0.134/0.137 | 0.066/0.127 | 19.603/21.703 | 1.420/1.472 |
| 10 | READY / 9 plus one missing | 0.678/0.761 | 1.949/2.100 | 0.014/0.015 | 0.299/0.376 | 0.168/0.213 | 21.893/22.147 | 2.134/2.190 |
| 100 | READY / 99 plus one missing | 5.056/5.251 | 5.160/5.268 | 0.031/0.034 | 2.037/2.142 | 1.408/1.486 | 30.003/30.522 | 8.814/8.958 |
| 1,000 | READY / 999 plus one missing | 51.772/57.322 | 36.556/37.345 | 0.211/0.215 | 20.329/21.270 | 15.116/16.764 | 109.340/119.470 | 82.971/91.577 |
| 10,000 | TOO_LARGE / 0 | 25.767/26.106 | 0.809/1.078 | 0.001/0.003 | 205.436/211.857 | 147.889/154.100 | 44.841/46.144 | 27.627/30.745 |

Peak Python-traced allocation across the full matrix was 9,595,139 bytes. At 1,000 points, exact
JSON/CSV artifacts were 93,354/118,937 bytes; SVG 63,364 bytes; PNG 13,037–13,726 bytes. At 10,000,
exact JSON/CSV were 951,349/1,229,930 bytes while semantic-state PNG/SVG remained about 3 KB/2.5 KB.
No retained object/child growth, hang, OpenGL, network, or silent omission was observed.

## Build and frozen evidence

- Clean PyInstaller 6.21.0 one-file build succeeded on Windows Python 3.12.7 at implementation
  head `06323f2`.
- Final EXE: 83,262,896 bytes; SHA-256
  `B90B7974EF2D45AFD94CB5D13207FF6E4D34A57C40005FFD5A6CA648BE8C7720`.
- A previously saved local baseline EXE (not asserted to be exact RM-145 SHA) was 80,992,123 bytes;
  indicative delta: +2,270,773 bytes. No new package caused the delta.
- The archive contains Qt6Gui, Qt6Svg, qwindows/qoffscreen plugins, and chart modules.
- The existing frozen self-test owner now imports `app.ui.charts` and renders synthetic dark/light
  PNG, SVG, JSON, and CSV. Final isolated run: `success=true`, `frozen=true`, 8 checks; chart sizes
  JSON 563, CSV 311, dark/light PNG 1,663/1,678, SVG 4,048 bytes.
- The smoke wrapper launches hidden/offscreen and temporarily overrides data/config/log/cache under
  the report directory. It restores environment and deletes the checked runtime directory, so it
  neither reads nor modifies live user state. This fixed a reproduced 120-second hang caused by the
  former user-path-dependent smoke invocation.
- Build/dist artifacts were removed after size/hash/report evidence. No developer-only artifact is
  committed.
- Python 3.13 frozen/CI execution is pending the feature PR Windows Quality Gate; it is not inferred
  from the local Python 3.12 build.

## Test and quality evidence

| Contour | Exact result |
|---|---|
| RM-146 focused characterization/contracts/interaction/hardening | `27 passed in 4.00s` |
| frozen owner + final RM-146 focused split | `7 passed in 3.33s`; `27 passed in 1.78s` |
| neighboring RM-142–145, Dashboard, design, navigation, build/frozen | `203 passed in 43.54s` |
| first full acceptance attempt | `2122 passed, 1 failed, 2 warnings in 144.12s` |
| second full acceptance attempt | `2122 passed, 1 failed, 2 warnings in 145.60s` |
| final complete suite | `2123 passed, 2 warnings in 133.56s (0:02:13)` |
| secrets | passed |
| Ruff check | passed |
| Ruff format | `682 files already formatted` |
| canonical mypy | success, 20 source files |
| strict chart-package mypy | success, 7 source files |
| pip-audit | no known vulnerabilities; editable project skipped |
| design-system audit | `matrix=45; styles=43; violations=0` |
| UI inventory | 85 modules, 33,378 lines, 127 UI test modules, no literal colours outside theme |
| `git diff --check` | passed |

The two warnings are the unchanged openpyxl unsupported-extension and conditional-formatting
warnings in `test_rm132_legacy_credentials_handoff.py`; RM-146 adds none. Both initial full-suite
failures were the same offscreen `QTest.mouseMove` order dependency: a global cursor at the target
position did not emit a hover event. The final guard sends a real `QMouseEvent(MouseMove)` through
Qt deterministically; `QTest.mouseClick` still covers pointer click. This acceptance finding and
the frozen user-path isolation finding were fixed and retained as regression guards.

## No-duplicate and boundary audit

Search evidence finds one `ChartSpec`, `ChartRenderPlan`, normalizer, painter, table model, selection
model, and exporter function per format. There is one public package and selected backend. The only
production import outside the package is the existing frozen diagnostic. No QtCharts, QtGraphs,
pyqtgraph, Matplotlib, Plotly, external chart dependency, second provenance type, second theme
token owner, local stylesheet, literal colour, router/shell/event bus/DI owner, or real chart
consumer exists.

The implementation changes no database/schema/migration, repository/cache/materialized view,
provider/AI/network path, setting/credential, KPI, tender metric, financial unit/rounding, route,
navigation, Dashboard value, RM-107 score/recommendation, or critical stop-factor priority.

## RM-147/RM-148 handoff, risks, and rollback

RM-147/RM-148 may consume `corteris-chart-v1`, bar/line kinds, exact Decimal/missing/aware-time
rules, eight states, RM-145 evidence alias, six-series/1,000-render/10,000-data limits, typed
selection, complete table, four exports, and measured DPI/performance behavior. They must define
their own truthful tender metrics, intervals/timezone/aggregation/drill-down and financial
currency/rounding/formulas. RM-146 provides no screen placement or real data fixture.

Residual risks are native accessibility/DPI observations deferred to RM-152, cross-stage
optimization deferred to RM-153, and cross-platform pixel-golden work deferred to RM-154. Visual
binary equality across Qt/font versions is deliberately not promised; semantic plan/dimensions and
same-environment repeatability are the gate.

Rollback is a revert of the RM-146 feature commits to exact baseline `cf2bc8f`. No dependency,
schema, setting, credential, or persisted user data requires downgrade. Stop publication on a
failed PR/head or exact merge-SHA gate, new warning/vulnerability, duplicate owner, artifact/privacy
leak, unexplained Python 3.13/frozen failure, or changed business-decision semantics.

## GitHub acceptance and closeout

- Feature PR #100 head: `72118c31a31f16b524c79ee83bc82a9daf7071fb`.
- PR-head Quality Gate run `29685966343`: `success`; Python 3.12 — `6m18s`, Python 3.13 —
  `4m16s`. The first Python 3.12 job ended in a native Windows access violation without a test
  assertion; the failed-job rerun on the same SHA passed without code or documentation changes.
- Final PR-head full suites: Python 3.12 — `2123 passed, 2 warnings in 247.36s`; Python 3.13 —
  `2123 passed, 2 warnings in 138.55s`.
- Feature merge SHA: `e09af67931c3a63874e259bed08efc5ce3a14284`.
- Exact merge-SHA push run `29686798140`: `success`; Python 3.12 — `5m8s`,
  `2123 passed, 2 warnings in 178.36s`; Python 3.13 — `4m54s`,
  `2123 passed, 2 warnings in 168.63s`. Dependency audit and every required step succeeded.
- The only annotations are the existing non-blocking official-actions Node.js 20/24 migration
  notices.
- This docs-only closeout changes only `ROADMAP.md`, `STATUS.md`, `ROADMAP_HISTORY.md` and this
  acceptance file. It marks RM-146 `DONE` and activates RM-147 as the sole `IN PROGRESS` stage.

Final DoD verdict: RM-146 satisfies the Definition of Done. Feature and exact merge-SHA gates are
green; `UI-141-007` is closed; DB/data/settings downgrade is unnecessary.
