# RM-146 chart technology audit

## Decision

RM-146 will use one repository-owned Qt Widgets backend built on `QWidget`, `QPainter`,
`QImage`, and `QSvgGenerator`. It will expose a backend-neutral immutable chart contract and a
normalized render plan from `app.ui.charts`. No chart package, transitive dependency, lockfile,
build hook, or second rendering framework is added.

This is a technical distribution-risk decision, not legal advice. The repository has no root
`LICENSE` or `LICENSE.md`, so its distribution model cannot be inferred. Reusing the already
shipped QtGui/QtSvg surface is the only reviewed option that does not enlarge the project's
dependency or licensing surface.

## Entry gate and exact baseline

- Worktree: `.worktrees/rm146`; branch: `feat/rm-146-interactive-chart-layer`.
- Exact baseline: RM-145 docs-only closeout merge
  `cf2bc8f080ad006131ab501863a424dcede30a1c`, PR #99.
- RM-145 feature PR #98 head:
  `ac846e9e6cfa6c8ab77c445810cd081097478bc8`.
- RM-145 feature merge: `ac8d2662911e8a0e450fcb20677f99082187793a`.
- Exact feature merge-SHA Quality Gate run `29680204767`: success on Windows Python 3.12 and
  Python 3.13.
- RM-145 closeout PR #99 head:
  `aa3baf9a80a487a67383ef36b85ce076983d470a`.
- Exact closeout Quality Gate run `29680893803`, attempt 2: success on Windows Python 3.12 and
  Python 3.13. Attempt 1 contained a transient native Python 3.12 process failure; the accepted
  exact-SHA rerun passed.
- Canonical status at the baseline: RM-145 `DONE`; RM-146 is the sole `IN PROGRESS` stage;
  RM-147 and later stages remain `PLANNED`.
- Clean baseline full suite: `2095 passed, 2 warnings in 184.19s (0:03:04)`. Both warnings are the
  unchanged openpyxl warnings in `test_rm132_legacy_credentials_handoff.py`.
- Secrets, Ruff check, Ruff format (`670 files already formatted`), mypy (20 source files), and
  `git diff --check` passed.
- Neighboring shell/design/RM-145 smoke selection: `19 passed in 30.13s`.
- Design-system audit: `matrix=45; styles=43; violations=0`.
- UI inventory: 78 modules, 31,612 lines, 123 UI test modules, and no literal colours outside the
  theme owner.

The root checkout's unrelated untracked `.agents/` and `skills-lock.json` are outside this
worktree and are not changed.

## Existing surface

- Supported Python is `>=3.12,<3.14`; supported PySide6 is `>=6.8,<7`.
- PySide6/Qt 6.11.1 is installed in the audit environment. `PySide6.QtCharts` and
  `PySide6.QtGraphs` can be imported from that wheel, but importability is not distribution
  permission.
- `pyqtgraph`, `matplotlib`, and NumPy are not installed.
- `pyproject.toml` and synchronized requirements contain no chart dependency.
- The frozen build has no chart-specific collection or hook.
- Repository search found no chart framework or reusable chart implementation.
- `ThemePalette` already owns `chart_1` through `chart_6`, `chart_grid`, and `chart_axis` for both
  light and dark modes.
- RM-145 already owns immutable source evidence as `DashboardSourceEvidence`; RM-146 will reuse
  that type rather than create a competing provenance model.

## Candidate review

| Candidate | License evidence | Technical/build evidence | Verdict |
|---|---|---|---|
| Repository `QWidget`/`QPainter` | Existing PySide6 QtGui surface; no new package | Full control of focus, keyboard, text fallback, hit testing, theme tokens, offscreen tests, PNG/SVG, and frozen behavior; highest local implementation cost | **Selected** |
| `PySide6.QtCharts` | Official docs say commercial or GPLv3 | Present in wheel but deprecated since Qt 6.10; distribution permission is unresolved | Rejected |
| `PySide6.QtGraphs` | Qt licensing page lists Qt Graphs among GPL-only modules unless commercially licensed | Present in wheel; adds an unapproved module and does not remove the need for application accessibility contracts | Rejected |
| pyqtgraph | Official repository license is MIT | Requires new pyqtgraph and NumPy dependency/build/frozen surface; application-specific keyboard/text semantics still required | Rejected |
| Matplotlib Qt canvas | Official license is PSF/BSD-compatible | Heavy new transitive, font, backend, startup, artifact, and frozen-build surface; accessibility integration remains local work | Rejected |

Official evidence checked on 2026-07-19:

- <https://doc.qt.io/qt-6/qtcharts-index.html>
- <https://doc.qt.io/qt-6/licensing.html>
- <https://doc.qt.io/qt-6/qtgraphs-index.html>
- <https://doc.qt.io/qtforpython-6/>
- <https://doc.qt.io/qtforpython-6/package_details.html>
- <https://doc.qt.io/qtforpython-6/overviews/qtgui-overview.html>
- <https://doc.qt.io/qtforpython-6/PySide6/QtGui/QImage.html>
- <https://doc.qt.io/qtforpython-6/PySide6/QtSvg/QSvgGenerator.html>
- <https://github.com/pyqtgraph/pyqtgraph>
- <https://github.com/pyqtgraph/pyqtgraph/blob/master/LICENSE.txt>
- <https://matplotlib.org/stable/project/license.html>

## Prototype evidence and limit consequence

A disposable offscreen prototype used the selected primitives without repository changes. It
rendered dark/light line charts at 640x360, 800x450, 1024x576, and 2x100 scale. At 800x450 the dark
PNG was 53,413 bytes, the light PNG was 52,686 bytes, and SVG was 4,683 bytes.

Ten exact 10,000-point renders measured:

| Theme | p50 | p95 |
|---|---:|---:|
| Dark | 2688.188 ms | 2963.203 ms |
| Light | 2924.024 ms | 3138.462 ms |

The prototype proves feasibility for bounded charts and proves that an unbounded 10k paint path is
not acceptable. The production contract therefore has an explicit exact-render ceiling and a
`TOO_LARGE` state. It must never silently aggregate, sample, truncate, or reorder input. Exact
JSON/CSV remains available for valid contract data even when visual rendering is refused.

## Selected architecture and rollback

The public model normalizes into a backend-independent render plan. One painter routine consumes
that plan for the on-screen widget, `QImage` PNG export, and `QSvgGenerator` SVG export. A Qt table
model provides the complete textual equivalent. Business aggregation, score/recommendation,
critical stop-factor priority, financial rounding, data loading, and navigation remain outside the
package.

Rollback is a revert of the RM-146 commits. There is no dependency, schema, settings, credential,
or persisted-data migration. Stop implementation if the painter cannot satisfy deterministic
export, keyboard/text equivalence, accepted limits, offscreen/frozen operation, or theme parity.
