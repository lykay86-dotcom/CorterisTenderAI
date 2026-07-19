# RM-146 immutable chart contract

## Boundary and version

The single public package is `app.ui.charts`; contract version is `corteris-chart-v1`. It is a
presentation boundary for already computed, ordered, provenance-bearing values. It must not query
repositories, call providers, aggregate data, calculate KPIs, infer missing values, round business
values, change approved recommendation/score logic, or alter critical stop-factor priority.

RM-146 fixtures are synthetic and offline. Real tender series/intervals/aggregation belong to
RM-147; financial units and rounding belong to RM-148.

## Immutable public model

All public values are frozen dataclasses, tuples, closed enums, or validated scalar aliases.

- `ChartSpec`: version, stable chart ID, kind, title, optional description, axes, ordered series,
  semantic state, source evidence, and optional state detail.
- `ChartSeries`: stable series ID, label, ordered points, one of the six chart colour roles, and a
  non-colour discriminator such as line/marker/pattern.
- `ChartPoint`: stable point ID, typed X value, exact `Decimal` Y value or `None`, and optional safe
  label. `None` is the only missing-value representation; it is never converted to zero.
- `ChartAxis`: closed category/numeric/time scale, title, and explicit unit label. A time X value
  must be timezone-aware.
- `ChartSelection`: chart/series/point IDs and a closed cause (`MOUSE`, `KEYBOARD`, `PROGRAMMATIC`).
- `ChartSourceEvidence`: the existing frozen RM-145 `DashboardSourceEvidence`, re-exported by the
  chart package. A new or lossy provenance DTO is forbidden.
- `ChartState`: `LOADING`, `READY`, `EMPTY`, `PARTIAL`, `STALE`, `ERROR`, `TOO_LARGE`, or
  `UNAVAILABLE`.
- `ChartKind`: `BAR` or `LINE`. Bar uses categorical X; line uses numeric or aware-time X.

Identifiers are non-empty bounded ASCII tokens and are unique within their parent. Titles, labels,
descriptions, units, and state details are bounded plain text. Control characters, NaN, infinity,
naive datetime values, duplicate IDs, unknown contract versions, invalid kind/axis combinations,
and out-of-order category duplication are rejected at construction.

## Ordering, exactness, and limits

- Series and point tuple order is source order and is never sorted by the presentation layer.
- Exact Y values remain `Decimal` through model, table, JSON, and CSV. Painter-only coordinates are
  finite floats derived inside normalization and never flow back into data export.
- A missing line point creates a gap; a missing bar has no mark. Both remain present in text/data
  output with an explicit missing value.
- Category labels are represented once per stable point; numeric/time X values must be
  non-decreasing within a series. Equal X values are allowed only when point IDs remain distinct.
- A chart accepts at most 6 series and 10,000 points per series so exact textual/data artifacts stay
  bounded. The renderer accepts at most 1,000 total points. A larger valid chart normalizes to
  `TOO_LARGE`; no hidden sampling, aggregation, truncation, or pagination changes its values.
- Normalization uses fixed margins, stable decimal-to-display formatting, stable tick selection,
  and deterministic geometry rounding. Input object identity, locale, wall clock, hash ordering,
  device DPI, and mouse position cannot change the semantic render plan.

## Semantic render plan

`normalize_chart(spec, viewport, palette)` produces an immutable `ChartRenderPlan` containing only
validated semantic state, plot/title/axis rectangles, ordered ticks, ordered marks/paths, complete
hit regions, textual labels, focus/selection IDs, and colour-role references resolved from the
provided RM-143 palette. It owns no widget and performs no I/O.

The same plan feeds screen painting and visual export. It is serializable to a deterministic test
projection so geometry/order/theme/state regressions do not depend on screenshots alone. Palette
values may differ between light and dark, but IDs, values, order, labels, state, and non-colour
discriminators must be identical.

## State rules

- `LOADING`: no marks or interaction; visible and accessible loading text.
- `READY`: complete source data; marks and selection enabled.
- `EMPTY`: valid zero-row source result; no marks; not an error.
- `PARTIAL`: retained/partial values may render, with explicit limitation text.
- `STALE`: retained values may render, with source age/limitation text.
- `ERROR`: no unsupported inferred marks; visible and accessible error detail.
- `TOO_LARGE`: visual rendering refused with limit/count text; exact table and JSON/CSV remain.
- `UNAVAILABLE`: capability/source unavailable; no marks or selection.

State never derives from formatted text. Caller-owned evidence and state remain authoritative.

## Ownership and compatibility

The chart package may depend on RM-143 theme tokens and the RM-145 evidence value only. Existing
repositories, analyzers, recommendation owners, controllers, routes, shell, lifecycle, and DI
paths remain unchanged. Consumers import the public package, not backend implementation modules.
There is one model, one normalizer, one table model, one interaction owner, one painter, and one
exporter; parallel chart DTOs or frameworks are forbidden.
