# RM-152 DPI and responsive-layout matrix

Baseline: `9cb37b9a83f50ac9f8f8e34fdeb582c2ed76e257`

## DPI-awareness prerequisite audit

- Qt/PySide6 version: `6.11.1`; Python `3.12.7` on the discovered native host.
- `app.main` calls `bootstrap`; no Qt DPI attribute/environment override is set in application code.
- `installer/corteris_tender_ai.spec` supplies no explicit Windows application manifest or DPI
  mode; `setup.iss` adds the PyInstaller executable without a DPI declaration. The newly built
  EXE's embedded manifest was inspected and contains `longPathAware` but no DPI declaration.
- No production use of `devicePixelRatio`, logical/physical DPI, `screenChanged`,
  `availableGeometry`, `saveGeometry`, or `restoreGeometry` exists.
- Theme typography and most geometry use Qt logical pixels. Icon assets are local and delivered
  through the RM-143 icon provider; no network icon path exists.
- `ModernMainWindow` loads only theme from QSettings; window/dialog/splitter/column geometry is not
  persisted or clamped.

Qt 6 may supply a native default in the dev process, but the effective frozen process and
per-monitor mode are `NOT_EXECUTED`. RM-152 does not change process DPI awareness without the
required native packaged and mixed-monitor observation.

## Current host discovery

| Field | Value |
|---|---|
| Windows | 10.0.19045 |
| display | one DELL E2218HN, 1920x1080, available 1920x1040 |
| logical/physical DPI | 96 / approximately 102.4 |
| device pixel ratio | 1.0 |
| refresh | 60 Hz |
| mixed-monitor capability | unavailable in discovered environment |

This is environment discovery, not a matrix PASS.

## Required native matrix

Each theme cell includes physical Tab/Shift+Tab, Enter/Space/arrows/shortcuts, Escape/Alt+F4,
focus visibility, clipping/overlap/elision/scroll/hit targets, Russian growth, table headers, and
synthetic safe data. Representative state cells add empty/loading/partial/error/success.

| Cell | Viewport | Scale | Theme | Required sweep | Status |
|---|---:|---:|---|---|---|
| DPI-1366-100-D | 1366x768 | 100% | dark | shell/routes/tender tabs/workflow dialogs | NOT_EXECUTED |
| DPI-1366-100-L | 1366x768 | 100% | light | same | NOT_EXECUTED |
| DPI-1366-125-D | 1366x768 | 125% | dark | same | NOT_EXECUTED; deterministic baseline risk |
| DPI-1366-125-L | 1366x768 | 125% | light | same | NOT_EXECUTED; deterministic baseline risk |
| DPI-1920-100-D/L | 1920x1080 | 100% | dark/light | plus all states | BLOCKED; keyboard worked in both themes; white native fallback strips were removed on `81A11C...A866`; exact `11E59D...066F0` UIA rerun exposed 176 elements and zero mojibake marker lines; all states remain incomplete |
| DPI-1920-125-D/L | 1920x1080 | 125% | dark/light | plus all states | BLOCKED; Windows UIA confirmed 125% and exact-build restart; owner confirmed no clipping/overlap, clean dark/light switching, and Tab/Shift+Tab without a trap; Windows UIA confirmed 100% restoration after the run; all semantic states incomplete |
| DPI-1920-150-D/L | 1920x1080 | 150% | dark/light | plus all states | BLOCKED; Windows UIA confirmed 150% and exact-build restart; UIA exposed 166 current elements/zero mojibake lines; owner confirmed no clipping/overlap, clean dark/light switching, and Tab/Shift+Tab without a trap; all semantic states incomplete |
| DPI-2560-150-D/L | 2560x1440 | 150% | dark/light | plus theme/page switching | NOT_EXECUTED |
| DPI-2560-175-D/L | 2560x1440 | 175% | dark/light | plus theme/page switching | NOT_EXECUTED |
| DPI-3840-200-D/L | 3840x2160 | 200% | dark/light | plus large table/modal nesting | NOT_EXECUTED |
| DPI-MIXED-A-B-A | two physical monitors | distinct per-monitor scales | both | main/dialog/tooltips A→B→A, route/theme/reopen | NOT_EXECUTED |
| DPI-HC | representative supported viewport | actual scale | Windows HC | focus/text/selection/icons/charts/dialog/menu | NOT_EXECUTED |
| DPI-FROZEN | representative cells | 100–200% | dark/light/HC | newly packaged executable | NOT_EXECUTED |

One 1920x1080 screenshot cannot replace the matrix. Owner-approved exceptions must name exact
cells/environment/reason and remain distinguishable from PASS.

## Deterministic baseline failure

The shell calls `setMinimumSize(1180, 720)`. At 1366x768 physical and 125%, the approximate logical
viewport is `1093x614` before taskbar deductions. Therefore the current minimum cannot fit and can
hide required actions or window controls. Expected-red asserts the supported logical minimum fits
the injected available geometry and that each physical page has an accessible scroll/fallback.

## Responsive-layout contract

- Use Qt layouts/stretch/size policies and logical units; no absolute positioning.
- The shell supported minimum fits the smallest logical viewport and keeps window controls,
  sidebar/routes, primary action, cancel/close/recovery reachable.
- Pages with larger content use one predictable keyboard-accessible scroll area; nesting must not
  create an unreachable action or horizontal trap.
- Meaningful text wraps. Elision is allowed only with full accessible text and tooltip/details
  route. Buttons may grow or wrap according to component policy.
- Tables/charts explicitly handle small width with keyboard-reachable scrolling and textual data.
- Dynamic state replacement does not expand outer geometry or move focus.
- Dialogs with tables/forms/text growth remain resizable; an initial `resize()` is a preference,
  not a minimum.

`DashboardPage` and `BusinessWorkflowPage` already have responsive seams; extend them rather than
add a second layout system.

## Fixed/min/max audit

Baseline has 15 fixed, 34 minimum, six maximum calls, and 26 initial dialog/window resizes.

- Keep token-sized icon/tool/progress geometry after native crop checks.
- Keep chart minimum `160x120` and tokenized button minimum heights.
- Adapt sidebar width and dashboard/workflow panel minima to supported logical viewport.
- Replace fixed profile text-editor heights where validation/Russian growth needs space.
- Strict maximum provider/search/verification areas require keyboard scrolling and complete
  accessible text; otherwise replace with flexible size policy.
- Do not mechanically remove all constraints.

## Russian growth fixtures

Automated and native runs use synthetic long Russian route/action/status labels, tender/customer
names, 150–200% growth surrogates, plural/date/currency/status variants, long safe
validation/partial/failure summaries, and an unbroken token. Verify sidebar, topbar, buttons, tabs,
groups, headers, dialogs, notification rows, status bar, chart labels, and full accessible text.

## Geometry persistence and recovery

If geometry is added, it uses the existing QSettings owner with a versioned key and logical Qt
geometry. Before restore:

1. reject corrupt/unknown version;
2. compare against current `availableGeometry` for all screens;
3. clamp/move fully offscreen or negative coordinates onto the selected/primary screen;
4. bound size to available screen while preserving supported minimum;
5. avoid a visible jump by applying before show;
6. ordinary reads perform no migration/write;
7. tests use temporary QSettings and synthetic screen rectangles.

Removed-monitor and scale-change restore never keeps an inaccessible window. Dialog origins and
row identities are not encoded in geometry.

## Mixed-DPI sequence

Launch on A; open main/dialog/menu/tooltip; move main A→B; move dialog separately; verify fonts,
icons, focus ring, menus, tables/charts; switch route/theme; close/reopen and validate on-screen
geometry; return B→A. Record Qt screen name, logical/physical DPI, DPR, screen-change observations,
and exact failure. The discovered one-monitor host cannot currently execute this cell.

## Automated/native boundary

Offscreen tests inject viewport/available-screen rectangles and scale surrogates to prove layout
contracts, minimum bounds, full-text access, geometry clamping, and stable focus. They cannot prove
effective Windows DPI mode, physical pixels, RDP behavior, per-monitor movement, focus visibility,
or frozen manifest behavior. Those cells remain native-only.
