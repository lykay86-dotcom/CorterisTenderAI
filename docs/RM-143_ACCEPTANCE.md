# RM-143 — Corteris Design System v1 acceptance

Local acceptance date: 18 July 2026.

Package status: feature implementation, local gates, feature PR, PR-head Quality Gate, merge and
exact merge-SHA Quality Gate are complete. This separate docs-only package records the canonical
roadmap closeout and activates RM-144.

## Entry gate and traceability

- Canonical baseline: `67beb8787db5908c9e8dd52f7e17e385aed48814` (`main` and `origin/main`).
- RM-142 feature merge: `246734d2f3b700392c6682c7bcfb5d6ab1469ec5`; exact merge-SHA Quality
  Gate run `29659317641`, successful on Python 3.12 and 3.13.
- Feature branch/worktree: `feat/rm-143-design-system`, `.worktrees/rm143`.
- Audit/contract/matrix/plan: `69785ee` (documentation only).
- Current-theme characterization: `6cfc79d`; `6 passed in 1.08s`.
- Expected-red contract: `363a572`; eight expected collection errors exclusively for absent
  RM-143 modules/public symbols.
- Versioned design tokens and contrast policy: `5becb16`.
- Semantic icon registry/assets/frozen evidence: `e88bd31`.
- Reusable component states and gallery: `b7a9702`.
- Foundational style migration and deterministic guard: `42bbaee`.
- Formatter-only normalization: `97e21f8`.

The entry baseline full suite passed with `1983 passed, 2 warnings in 170.15s` before application
changes. The root checkout's unrelated untracked `.agents/` and `skills-lock.json` were preserved.

## Accepted design-system contract

- `app.ui.theme` remains the only theme/design-system owner and exports immutable
  `corteris-design-v1` tokens for spacing, controls/icons, borders, radii, elevation, motion and
  layout presentation.
- Dark/light palettes retain identical roles. The approved component pairs use deterministic sRGB
  relative luminance and explicit 4.5:1 text or 3:1 non-text/disabled thresholds.
- The two database-status raw colours and exception-rich HTML were removed. Static scan reports no
  raw `#RRGGBB` literals outside the theme allowlist.
- One semantic `IconId` registry resolves local original SVG assets with a bounded cache and safe,
  path-free fallback. The manifest declares `Corteris original assets`; runtime network/CDN access
  is absent. RM-142 route IDs, order, aliases, availability, context and registry ownership did not
  change.
- `CorterisButton` retains public subclasses/properties and now covers primary, secondary, outline,
  ghost, danger and accessible icon-only variants in three token sizes. Loading uses one owned
  token-timed `QTimer` and a visible/accessible label.
- `Card`/`KpiCard` retain object names, properties and signal behavior. Clickable cards have strong
  focus, Space/Enter activation and one reusable shadow effect across re-theme operations.
- Shared `StatusBadge`, `InlineMessage`, `DataState.disabled`, `FormField` and `FormSection` are
  presentation-only components. They receive text/tone/state from existing owners and do not infer
  business status, score or recommendation.
- `ComponentGallery` is an offline, non-route harness covering buttons, cards, status, data states,
  forms and icons in both themes, including long Russian labels and lifecycle-count stability.
- The versioned migration matrix covers all 45 baseline `setStyleSheet` sites. The guard observes 43
  current calls: seven migrated/removed legacy calls and five new exact canonical token-backed
  owners. Broad directory exceptions are forbidden.

## Inventory before and after

| Metric | Post-RM-142 baseline | RM-143 result |
|---|---:|---:|
| UI modules | 72 | 78 |
| UI lines | 30,174 | 31,048 |
| UI test modules | 105 | 115 |
| `setStyleSheet` calls | 45 | 43 |
| literal colours outside theme | 2 | 0 |
| accessible-name calls | 30 | 40 |
| accessible-description calls | 13 | 15 |
| timers / threads | 6 / 1 | 6 / 1 |
| `QTableWidget` / `QTableView` | 30 / 2 | 30 / 2 |

RM-143 deliberately does not claim application-wide WCAG/high-contrast/screen-reader acceptance;
that remains RM-152. Deferred page/dialog styles remain exact matrix entries for their owning RMs.

## Local validation evidence

Environment: Windows, Python 3.12 virtual environment, `QT_QPA_PLATFORM=offscreen`, repository-local
isolated `--basetemp` paths.

- Final RM-143 contract: `76 passed in 10.23s`.
- Neighboring RM-127/RM-128/RM-130/RM-142, health/status/profile contour: `40 passed in 29.35s`.
- Full pytest: `2059 passed, 2 warnings in 284.17s`.
- Release/frozen resource smoke: `6 passed in 9.56s`.
- Required CI smoke group: `8 passed in 24.08s`; public controller import printed
  `DashboardController`.
- Repository secret scan: passed.
- `python -m ruff check .`: passed.
- `python -m ruff format . --check`: `662 files already formatted`.
- Required mypy contour: `Success: no issues found in 20 source files`.
- `python -m scripts.check_design_system --format summary`:
  `design-system: OK; matrix=45; styles=43; violations=0`.
- `python -m scripts.audit_ui_inventory --format summary`: no literal colours outside theme.
- `python -m pip_audit --skip-editable`: `No known vulnerabilities found`; editable project skipped
  as intended. The first sandboxed attempt was blocked from PyPI; the approved network retry with a
  task-local cache succeeded.
- `git diff --check`: passed.

The two warnings are the existing openpyxl unsupported-extension and conditional-formatting
warnings from `test_rm132_legacy_credentials_handoff.py`; RM-143 adds no warning.

## Boundaries, persistence and rollback

- DB/schema/migration: not required and not changed.
- New runtime dependency: not required and not added.
- No repository, service, controller, worker, socket, keyring or persistence owner was added.
- RM-107 approved score, recommendation and critical stop-factor priority are unchanged; AI output
  cannot override them.
- QSettings keeps the existing `ui/theme` values `dark` and `light`.
- Rollback is a revert of RM-143 feature commits/merge to baseline `67beb87`; no DB, data, credential,
  schedule or settings downgrade is needed. Missing icons retain a safe fallback and RM-142 route
  contracts remain compatible.

## GitHub acceptance and closeout

- Feature PR #94 head: `1915be92dc0a9e0b9c1edc0bb5955abf6c94f948`.
- PR-head Quality Gate run `29662950338`: `success`; Python 3.12 — `5m03s`, Python 3.13 —
  `3m30s`.
- Feature merge SHA: `c8d111f3db615dd3c21c231bf265bb00093c65bd`.
- Exact merge-SHA push run `29663124774`: `success`; Python 3.12 — `4m38s`, Python 3.13 —
  `4m54s`. Full suite, dependency audit and every required step succeeded.
- The only annotation is the existing non-blocking official-actions Node.js 20/24 migration notice.
- This docs-only closeout changes only `ROADMAP.md`, `STATUS.md`, `ROADMAP_HISTORY.md` and this
  acceptance file. It marks RM-143 `DONE` and activates RM-144 as the sole `IN PROGRESS` stage.

Final DoD verdict: RM-143 satisfies the Definition of Done. Feature and exact merge-SHA gates are
green; DB/data/settings downgrade is unnecessary; UI-141-003 is closed.
