# RM-146 interaction and accessibility contract

## Equivalent representations

Every chart has two first-class representations of the same immutable `ChartSpec`:

1. the visual canvas; and
2. a complete textual data table available from the keyboard and mouse.

The table is not generated from pixels or tooltip text. It exposes stable series ID, series label,
point ID, exact X, exact Y/missing status, source order, chart state, and relevant provenance. Row
order is series order followed by point order. It remains available for `PARTIAL`, `STALE`, and
`TOO_LARGE` valid data.

## Focus and selection

The chart canvas is a focusable control with a visible RM-143-token focus indicator. Selection is a
typed `ChartSelection`, never a positional integer or formatted label. Mouse hit testing and
keyboard movement resolve to the same stable series/point IDs and emit one selection signal.

Only non-missing points in an interactable state can be selected. A state transition that removes
the selected ID clears selection once. A refresh that retains the ID retains selection. The
package does not navigate, filter business data, or execute an action in response to selection.

## Closed key map

| Input | Behavior |
|---|---|
| `Tab` / `Shift+Tab` | Enter or leave the chart using normal Qt focus order |
| `Left` / `Right` | Previous/next selectable point in source order within the series; no wrap |
| `Up` / `Down` | Same point position in previous/next series, falling back to the nearest selectable source-order point; no wrap |
| `Home` / `End` | First/last selectable point in the current series |
| `Ctrl+Home` / `Ctrl+End` | First/last selectable point in the complete chart |
| `Enter` / `Space` | Confirm the current typed selection and show its tooltip-equivalent text |
| `Escape` | Clear selection and transient tooltip |
| `F2` | Move focus to/show the complete data table |

Unsupported keys are passed to Qt. Disabled semantic states do not synthesize a selection.

## Pointer and tooltip behavior

Primary-button click selects the nearest mark only inside its bounded hit region. Hover may show a
tooltip but must not change selection. Tooltip text is escaped plain text and contains chart title,
series label, point label/X, exact value or “missing”, unit, and state limitation when present. The
same string is available to keyboard users and is reflected in accessible description/state text.
No source HTML, URL, file path, or executable rich text is accepted.

## Accessible names, descriptions, and states

- Canvas accessible name: chart title plus chart kind.
- Canvas accessible description: chart description, series/point counts, semantic state, unit,
  source/freshness limitation, and the `F2` table instruction.
- Selected point description: series, point, exact value/missing status, position, and state.
- Table accessible name: `<chart title> — data table`.
- Loading, empty, partial, stale, error, too-large, and unavailable are communicated in visible text
  and accessible descriptions, never by colour alone.
- Series differ by label and a line/marker/pattern discriminator as well as colour.
- Focus, selection, missing values, and state banners satisfy dark/light parity and do not depend on
  red/green interpretation.

The canvas exposes one coherent control-level accessible contract; the table supplies cell-level
navigation through Qt's native item-view accessibility. The package must not claim that painted
marks are separate native controls.

## Resize, theme, and lifecycle

Resize recomputes geometry without changing IDs, values, source order, state, or selection. Theme
change resolves the same semantic colour roles through the active palette. The widget has no
background thread, timer, provider, repository, network call, or process. Disposal disconnects
signals and releases only widget-owned objects; application lifecycle remains RM-144-owned.

Offscreen automated tests cover the complete key map, mouse/keyboard identity parity, focus order,
table equivalence, tooltip escaping, state text, resize retention, and light/dark non-colour
parity. Native Windows keyboard/screen-reader observations are recorded separately and never
fabricated from offscreen evidence.
