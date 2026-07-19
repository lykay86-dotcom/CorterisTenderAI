# RM-146 performance, resize, and DPI plan

## Purpose

Measure the selected painter backend rather than claim generic Qt performance. All fixtures are
synthetic, deterministic, and exact. No benchmark may hide work through aggregation, sampling,
point truncation, cached stale geometry, or disabled antialiasing that production enables.

## Measurement matrix

Run offscreen on the repository Python 3.12 environment and, in the final Windows gate, Python
3.12/3.13 where available.

| Dimension | Required cases |
|---|---|
| Kind | categorical bar; numeric line; aware-time line; missing-value gaps |
| Total points | 0, 1, 10, 100, 1,000, 10,000 |
| Series | 1 and 6 within accepted contract limits |
| Viewport | 320x200, 640x360, 800x450, 1024x576, 1920x1080 |
| Device scale | 1.0, 1.25, 1.5, 2.0, 4.0 |
| Theme | RM-143 light and dark |
| Operation | validation, normalization, paint, resize, hit test, table access, JSON, CSV, PNG, SVG |

Each timed case has warm-up followed by at least 10 samples. Record environment, sample count,
p50, p95, maximum, artifact bytes, image dimensions, and peak process-memory delta where the
runner supports it. Use `perf_counter_ns`; retain raw measurements in test output or a documented
temporary artifact. Performance assertions should enforce limits/state and generous regression
ceilings, not brittle workstation-specific millisecond promises.

## Initial feasibility evidence

Before production code, an offscreen QPainter prototype rendered dark/light 640x360, 800x450,
1024x576, and 2x100 artifacts. At 800x450: dark PNG 53,413 bytes; light PNG 52,686 bytes; SVG
4,683 bytes. Ten 10,000-point paints measured dark p50/p95 2688.188/2963.203 ms and light
2924.024/3138.462 ms.

Consequence: exact visual rendering is capped at 1,000 total points for this contract version.
Valid larger specs, up to the contract data ceiling, produce `TOO_LARGE` without painting marks;
their exact table/JSON/CSV remains available. The final implementation must remeasure all required
sizes and may lower the ceiling if evidence requires it. Raising it requires new measured evidence
and a contract-version review.

## Resize invariants

For every accepted viewport, repeated `A → B → A` normalization must reproduce the same A plan
projection. Resize may change only pixel geometry, tick density, and elision. It must preserve
stable IDs, exact values, order, state, provenance, selection, table rows, and data export bytes.
Zero/negative temporary Qt sizes must not allocate or raise; they yield a bounded unavailable
paint until a valid size returns.

## DPI invariants

Logical layout is normalized independently of device pixel allocation. PNG physical dimensions
equal checked logical dimensions multiplied by scale. Pen widths, marker sizes, hit targets, focus
ring, text spacing, and state banners remain readable at 100%, 125%, 150%, 200%, and 400%. SVG
retains the logical view box. No coordinate becomes NaN/infinite or exceeds the checked pixel
budget.

Offscreen scale evidence is automated. Native Windows per-monitor movement, screen-reader output,
font fallback, and actual 125%/150%/200% rendering are manual/frozen-gate evidence and remain
`NOT EXECUTED` until run; they must not be inferred from `QImage` tests.

## Acceptance and stop conditions

- 0/1/10/100/1,000 cases normalize, interact, table-render, and export exactly.
- 10,000 produces `TOO_LARGE` promptly and never calls mark painting.
- Six-series identity/order and missing gaps remain exact.
- Repeated light/dark and resize cycles do not leak selections or grow retained objects.
- PNG/SVG stay within declared dimensions/pixel budget; JSON/CSV remain byte deterministic.
- Frozen Windows imports `app.ui.charts`, renders one synthetic bar and line artifact, and exits
  without plugin/provider/network access.

Stop publication on UI-thread stalls beyond the documented bound, unbounded allocation, hidden
sampling, DPI clipping that loses meaning, non-deterministic data bytes, unsafe SVG content, frozen
module/resource failure, or a chart-specific crash.
