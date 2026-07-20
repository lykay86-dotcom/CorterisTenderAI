# RM-152 contrast and Windows high-contrast contract

Baseline: `9cb37b9a83f50ac9f8f8e34fdeb582c2ed76e257`

## Owners and thresholds

`app.ui.theme` remains the only palette/token/stylesheet owner. Local widgets consume semantic
tokens and may not introduce literal colors. RM-152 extends the RM-143 machine-readable pair
inventory and native evidence; it does not declare WCAG conformance from ratios alone.

Project-approved regression thresholds are 4.5:1 for normal text and 3.0:1 for focus, semantic
non-text indicators, and disabled-state differentiation where RM-143 explicitly approved that
policy. Every semantic state also has text/state; passing contrast never permits color-only status.

## Current machine-computed pairs

Ratios use the existing W3C-compatible sRGB implementation in `app.ui.theme.contrast`.

| Pair | Dark ratio/min | Light ratio/min | Baseline result |
|---|---:|---:|---|
| primary text / app | 17.150 / 4.5 | 14.579 / 4.5 | pass |
| secondary text / panel | 10.101 / 4.5 | 7.169 / 4.5 | pass |
| muted text / card | 5.013 / 4.5 | 4.559 / 4.5 | pass |
| text / brand | 5.398 / 4.5 | 5.398 / 4.5 | pass |
| text / danger | 4.559 / 4.5 | 5.087 / 4.5 | pass |
| input text / input | 16.275 / 4.5 | 14.725 / 4.5 | pass |
| disabled text / input | 3.040 / 3.0 | 3.591 / 3.0 | pass, dark has 0.040 margin |
| selection text / selection | 10.820 / 4.5 | 13.323 / 4.5 | pass |
| focus ring / app | 9.390 / 3.0 | 3.804 / 3.0 | pass |
| info / info background | 5.692 / 3.0 | 4.252 / 3.0 | pass |
| success / success background | 6.483 / 3.0 | 3.678 / 3.0 | pass |
| warning / warning background | 7.578 / 3.0 | 3.964 / 3.0 | pass |
| danger / danger background | 3.028 / 3.0 | 4.216 / 3.0 | pass, dark has 0.028 margin |

The exact foreground/background values come from `DARK_PALETTE` and `LIGHT_PALETTE`. The committed
machine-readable report is `docs/evidence/RM-152_CONTRAST_PAIRS.json`; it is regenerated from
`app.ui.theme.contrast_inventory` and checked by `scripts/check_rm152_accessibility.py`. It
serializes pair ID, theme, token names, exact colors, measured ratio, minimum, result, surface, and
the non-color alternative. The near-threshold dark disabled/danger pairs are A3 watch items.

Placeholder hints and decorative chart grids are explicitly `ADVISORY`, never `PASS`: persistent
labels/accessible names and chart axes/full data tables carry their meaning. All pairs with a
project-approved threshold pass in both themes.

## Inventory to add/verify

The accepted inventory expands beyond the inherited 13 pairs to cover, for both themes:

- focus ring against app, panel, card, input, selected, danger, warning, and table/chart surfaces;
- selected text and selected boundary against adjacent rows/background;
- link/action text against actual surface;
- placeholder/input/invalid border;
- critical/warning/success text and icon against their actual containers;
- chart axis/grid/series against background and adjacent series;
- table header/text/selection/focus;
- disabled text/control boundary;
- notification unread/read and semantic severity.

Opaque sRGB ratios are computed only for opaque pairs. Alpha/overlay results require compositing
against the declared underlying surface before measurement.

## Visible focus contract

The global stylesheet uses RM-143 `focus_ring` and `BorderWidth.FOCUS` for edits, buttons,
toolbuttons, check/radio, lists, trees, and tables. Component-local styles must not erase it.

Native review checks that focus:

- differs from hover, selected, pressed, invalid, and semantic state;
- is not clipped by rounded frames, scroll viewports, table cells, chart canvas, or strict maxima;
- remains visible for icon tools, custom cards/tiles, tabs, menus, notification rows, and disabled
  adjacency;
- scales at 100–200% and remains visible in dark/light/high contrast.

Static QSS presence and ratio are automated regression guards, not visual proof.

## Status is not color-only

Success, partial/stale/conflict, error, running/cancelling, selected/current, disabled/unavailable,
critical stop factor, unread notification, and provider/source health have visible text and native
state/description. Icons/shapes supplement. RM-146 charts retain a complete textual equivalent and
RM-107 critical evidence remains first even with positive score.

## Windows high-contrast behavior

Native sessions activate Windows high contrast, restart the dev/frozen app as required, and verify:

1. text/background, enabled/disabled, selected/current, invalid, and semantic states remain
   distinguishable;
2. keyboard focus is visible on every representative control;
3. local QSS does not hide system selection/focus/menu/tooltip semantics;
4. missing/invisible glyphs retain text/name alternatives;
5. chart data remains available through text/table even if series colors collapse;
6. destructive warning and safe default remain understandable;
7. switching app theme is not required to recover usability.

If Qt/QSS cannot safely follow a system palette without a broad RM-143 rewrite, record the exact
surface and native fallback as `FAIL`/`BLOCKED` and request owner decision. Do not silently replace
the palette system or claim high-contrast support.

## Test and evidence boundary

Automated tests cover pair schema/thresholds, no local literal colors, focus selectors/tokens,
text alternatives, and theme-invariant semantic identity. Native cells cover actual focus,
high-contrast fidelity, menus/tooltips/dialogs/tables/charts, and dark/light at required DPI.
Every high-contrast cell is currently `NOT_EXECUTED`.
