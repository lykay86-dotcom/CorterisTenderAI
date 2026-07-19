# RM-148 numeric contract

Contract version: `financial-numeric-v1`.

## Types and states

- Domain money and percentage values are finite `Decimal`; direct `float` domain construction is
  rejected. Explicit legacy adapters may accept JSON numeric lexemes only through Decimal JSON
  parsing.
- Units are closed: `MONEY`, `PERCENTAGE_POINT`, `COUNT`, `RATIO`.
- Currencies are closed for this owner: `RUB`, `UNKNOWN`. No FX conversion is performed.
- States are closed: `AVAILABLE`, `MISSING`, `INVALID`, `CONFLICTED`,
  `UNSUPPORTED_CURRENCY`, `OUT_OF_RANGE`, `STALE`, `ERROR`.
- `None` is missing. Zero is an available value. Invalid, conflicted and unsupported values never
  participate in aggregates.

## Parse and canonical representation

- Machine/persisted input is an unsigned non-exponent fixed-point string.
- User input accepts either `.` or `,` as decimal separator, but not both; spaces/NBSP may be
  validated grouping separators. `₽`/`RUB` may appear only as boundary decoration.
- Empty input is missing, never zero. Bool, NaN, sNaN and infinities are invalid.
- Money commit precision is at most two fractional digits. Overprecision is an error, not silent
  quantization.
- Canonical persisted money always has two fractional digits. Canonical margin always has two
  percentage-point digits. Negative zero serializes as `0.00`.

## Bounds

- RUB money: `0.00..999999999999.99` (12 integer digits, two fractional digits).
- Profit is non-negative; RM-148 does not introduce loss semantics.
- Derived margin: `0.00..1000.00` percentage points. A larger derived result is `OUT_OF_RANGE`.
- Workflow snapshot: at most 10,000 records; larger input fails closed without sampling.

## Precision and aggregation

- Input precision: two money digits; two explicit percentage-point digits.
- Storage precision: canonical fixed-point strings at the same scale.
- Calculation precision: exact Decimal with no intermediate quantize.
- Presentation precision: full money and margin use two digits; compact projections must expose an
  exact tooltip/accessibility value.
- Sum before rounding. Weighted margin is `sum(profit) / sum(total) * 100`; arithmetic mean of
  record margins is not an aggregate margin.
- Deterministic order: state, currency code, exact value, stable record ID; missing/invalid sort
  after available values.

## Snapshot

The one immutable Qt-free snapshot carries contract/schema/metric versions, aware `generated_at`,
query interval/timezone, source fingerprint, exact values, currency/unit/state, included/excluded
counts and reasons, stable contributor IDs and export fingerprint. Table, KPI, chart, accessible
table and export consume that snapshot or its immutable projections without re-query.

