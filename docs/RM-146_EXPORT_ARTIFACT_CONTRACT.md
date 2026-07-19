# RM-146 export and artifact contract

## Ownership and API

The chart package exports in-memory immutable bytes plus media type and suggested extension. It
does not choose a user path, open a dialog, overwrite a file, upload an artifact, or retain export
state. The calling application owns path policy and atomic file writing.

Data export reads the immutable `ChartSpec`; visual export reads the normalized
`ChartRenderPlan`. Neither export reads widget pixels, selection/hover position, locale, wall clock,
randomness, repository state, or a provider.

## Deterministic JSON

- Media type: `application/json`; encoding: UTF-8; one trailing LF.
- Top-level key order is fixed: contract version, chart ID, kind, title, description, state,
  state detail, axes, source evidence, series.
- Arrays preserve source tuple order.
- `Decimal` is an exact canonical string, never a JSON float.
- Aware datetime is ISO 8601 including offset; missing is JSON `null`.
- Enums use stable contract values. IDs and text are emitted exactly after contract validation.
- JSON is compact and uses deterministic separators/escaping; no generated timestamp is included.

## Deterministic CSV

- Media type: `text/csv`; encoding: UTF-8 with BOM omitted; line ending: LF.
- Fixed header:
  `contract_version,chart_id,chart_state,series_id,series_label,point_id,point_order,x_kind,x_value,y_value,y_missing,unit`.
- One row per source point in series/point order. Values use exact decimal and aware ISO formats.
- Missing Y has an empty `y_value` and `y_missing=true`.
- RFC 4180 quoting is applied deterministically. Spreadsheet formula prefixes (`=`, `+`, `-`,
  `@`) in text cells are prefixed with a single apostrophe; the original validated value remains
  unchanged in JSON/model.

## Bounded PNG and SVG

- PNG uses `QImage` plus the shared painter; media type `image/png`.
- SVG uses `QSvgGenerator` plus the shared painter; media type `image/svg+xml`.
- Accepted logical width/height: 320–4096 by 200–4096; accepted device scale: 1.0–4.0; maximum
  physical pixel count: 16,777,216. Invalid or larger requests fail before allocation.
- Visual export is available only when a renderable semantic plan exists. `LOADING`, `ERROR`,
  `TOO_LARGE`, and `UNAVAILABLE` may export a bounded semantic-state artifact, but never invented
  marks. Exact JSON/CSV remains available for every valid spec.
- Export explicitly sets viewport, scale, background, fonts, antialiasing, and active light/dark
  palette. It does not capture OS chrome, a tooltip window, current focus, or hover.
- SVG contains no external link, script, image reference, font download, source path, secret, or
  generated timestamp.

Byte-for-byte determinism is required for JSON/CSV in one contract version. PNG/SVG acceptance is
semantic and geometry deterministic in the pinned Qt/font environment; tests compare dimensions,
media signature, stable plan projection, absence of unsafe references, and repeated-run artifact
hashes on that environment. Cross-Qt binary equality is not promised.

## Limits and failures

Export returns typed failures for unsupported format, invalid dimensions/scale, pixel-budget
overflow, normalization failure, encoder failure, or visual `TOO_LARGE`. There is no silent resize,
sampling, aggregation, point omission, format fallback, partial file, or exception containing raw
user paths/data.

Artifacts used as CI evidence must be synthetic, contain no credentials or user data, be bounded,
and be declared explicitly if committed. The default RM-146 strategy is test-time temporary
artifacts and recorded measurements, not checked-in binary screenshots.
