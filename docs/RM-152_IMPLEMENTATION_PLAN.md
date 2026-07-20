# RM-152 implementation plan

Baseline: `9cb37b9a83f50ac9f8f8e34fdeb582c2ed76e257`
Branch: `feat/rm-152-accessibility-dpi`

## Objective and constraints

Close `UI-141-013` and `UI-141-014` with audit-first, tests-first, automated and actual native
Windows evidence. Preserve RM-107 score/recommendation/critical stop-factor priority and all
RM-142–151 owners. Default impact is no new dependency, schema/migration, network/AI/provider,
keyring read, business formula, or persisted domain-data change.

The web-interface accessibility review guidance used for the audit reinforces explicit labels,
keyboard-equivalent actions, visible focus, non-color status, bounded async announcements, long
text handling, and safe destructive confirmation. Only principles applicable to native Qt are
adopted; DOM/web-specific mechanisms are not introduced.

## Commit sequence

1. **Pre-production documents** — these nine audit/contract/plan files only.
2. **Characterization** — freeze accepted RM-142 route history, RM-146 chart keys, RM-150 exact
   selection, RM-151 coalescing/security, current shortcut catalog, safe destructive defaults, and
   reproducible baseline failures without changing production.
3. **Expected-red** — intended failures for traversal, initial/return focus, label relation,
   icon-only name, color-only state, visible focus token, removed-focus fallback, 1366@125 layout,
   Russian growth, geometry/mixed-DPI guard, and native matrix not-pass validation.
4. **Shared seams** — smallest extensions to RM-143 widgets/theme and RM-142 navigation; bounded
   dialog/geometry helpers only where repeated contracts prove a common seam.
5. **Representative consumers** — shell/Dashboard/search/tender; tables/charts/notifications;
   forms/providers; backup/recovery/crash/support. Each batch gets focused tests.
6. **Native matrix and fixes** — physical keyboard, Narrator, dark/light/high contrast, required
   viewports/scales, mixed monitor, dev/frozen. Rerun failed cells on the same fixed commit.
7. **Acceptance and feature PR** — full gate and `RM-152_ACCEPTANCE.md`; stage stays IN PROGRESS.
8. **Post-merge** — exact merge-SHA Windows 3.12/3.13 gate, then separate docs-only closeout.

## Characterization scope

- exact shortcut/action catalog and no-conflict baseline;
- pointer/Enter/Space parity for RM-143 cards/buttons, Dashboard, RM-146 charts, RM-150 tables;
- RM-142 route/context/history and existing focus-token behavior;
- credential write-only initial focus, buddy, safe default, Escape/no secret;
- destructive `No`/`Cancel` defaults and exact identity revalidation;
- RM-151 start/phase/bucket/terminal bounds, safe text, and focus invariance;
- current palette ratios and absence of literal colors;
- injected shell/page/dialog geometry and historical native `NOT_EXECUTED` states.

Characterization may document existing failure but cannot encode it as desired behavior.

## Expected-red tests

| Red ID | Intended missing contract |
|---|---|
| RED-01 | full-shell forward/reverse traversal detects Dashboard subcycle/unreachable control |
| RED-02 | empty Tenders table fails bounded Tab exit |
| RED-03 | representative dialog lacks deterministic initial/return origin fallback |
| RED-04 | form label lacks runtime buddy/usable name relation |
| RED-05 | icon-only/search/health/theme control lacks safe contextual name/state |
| RED-06 | semantic status fixture uses color/icon without text/state |
| RED-07 | focus selector/pair missing or clipped for a component/theme state |
| RED-08 | removed row/action leaves deleted/neighbor focus instead of container |
| RED-09 | 1366x768@125 logical available geometry is smaller than shell minimum/action layout |
| RED-10 | Russian 150–200% growth clips required action or loses full text |
| RED-11 | corrupt/offscreen/removed-monitor geometry has no deterministic clamp guard |
| RED-12 | native report validator rejects PASS derived from NOT_EXECUTED/missing metadata |

Red tests fail for absent APIs/contracts, not timing, pixel-perfect images, actual user data, or
unavailable hardware.

## Planned implementation seams

### RM-142 navigation

Extend `DashboardLayout` target validation and deterministic route fallback. Assign unique
route-derived sidebar/control IDs. Preserve route registry/history/context and existing handlers.

### RM-143 theme/components

Extend buttons/cards/topbar/status components with stable IDs, names/descriptions/state, and
focus-token usage. Expand machine-readable contrast pairs and focus selectors without local literal
colors or a second design system.

### Focus/dialog helper

If repeated tests require it, add a small Qt presentation helper for live-target validation,
initial focus, local origin capture, and exact/fallback return. It stores no domain data, uses no
global event filter, performs no I/O, and does not own close/result.

### Geometry helper

Add a Qt-free rectangle clamp/version contract where possible and a thin Qt screen adapter at the
shell boundary. Use existing QSettings only if persistence is implemented. No DPI-mode change is
allowed before frozen/native evidence.

### RM-150/RM-146/RM-151 consumers

Make a table one bounded task-flow Tab stop while retaining arrow/cell/editor semantics; keep exact
row/action tokens. Preserve chart key/data/text/export contracts. Add accessible operation/status
consumer metadata while retaining RM-151 coalescer/security and no-focus-steal behavior.

## Representative implementation order

1. shell/sidebar/topbar/status and route focus;
2. Dashboard traversal/dynamic states/stable IDs;
3. common table/chart focus and removed-selection fallback;
4. search/profile/provider/credential forms and operation states;
5. registry/detail/documents/requirements/verification/analysis/score;
6. scheduler/notifications;
7. workflow form/table/import/export/backup/recovery/health;
8. crash/safe mode/support;
9. geometry/Russian growth/contrast/high-contrast adjustments proven by tests/native findings.

Mechanical all-dialog/all-table rewrites are prohibited. Every touched consumer must have the same
owner/identity/lifecycle before and after.

## Verification plan

- focused RM-152 characterization/contracts/security/layout/native-report tests;
- neighboring RM-142–151 and J01–J16 representative contours;
- offline provider/keyring isolation, import/composition, migration/schema, lifecycle/shutdown,
  build/release and frozen-self-test smokes;
- full `python -m pytest -q`;
- Ruff check/format, canonical mypy targets, secret scan, dependency audit;
- accessibility owner/static guard, semantic pair artifact validator, native matrix report/privacy
  validator, no-PASS-from-NOT_EXECUTED rule;
- actual native matrix with exact environment metadata and privacy-scrubbed evidence.

Exact commands and totals are recorded in acceptance. The baseline full suite is
`2318 passed, 2 warnings in 121.78s`; warnings are the unchanged openpyxl warnings from
`test_rm132_legacy_credentials_handoff.py`.

## Stop conditions and native availability

Stop for owner decision if a fix changes domain identity/action/default safety, needs a global key
filter, changes DPI mode without packaged verification, requires broad RM-143 high-contrast
replacement, adds dependency/schema/network, needs real user data, or overlaps RM-153/RM-154.

Current host has one 1920x1080@100% display. Audit/contracts/tests/implementation may proceed, but
mixed-monitor, unavailable scale/viewport, high-contrast, Narrator, and frozen cells cannot be
declared PASS without actual observation or explicit owner-approved exception. If that evidence
cannot be obtained, final feature acceptance is BLOCKED, not silently reduced.

On 2026-07-20 the owner explicitly approved named decision
`RM152-OWNER-EXCEPTIONS-2026-07-20` for every incomplete cell. The exception registry retains four
`BLOCKED` and 29 `NOT_EXECUTED` statuses, records exact environment/reason/residual risk, and passes
the fail-closed strict validator without manufacturing a `PASS`.

## Rollback

Feature rollback is a revert of RM-152 presentation/test commits to the baseline. No data/schema,
dependency, network, setting migration, score, decision, or critical-priority rollback is expected.
