# RM-147 time and filter contract

Contract version: `tender-analytics-query-v1`

## Immutable types

The public pure-Python contract contains no Qt, repository, SQL, locale parser, mutable collection,
or arbitrary expression:

```python
@dataclass(frozen=True, slots=True)
class AnalyticsInterval:
    start_inclusive: datetime
    end_exclusive: datetime
    timezone_name: str

class AnalyticsGrain(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"

class AnalyticsPreset(StrEnum):
    LAST_7_COMPLETE_DAYS = "last_7_complete_days"
    LAST_30_COMPLETE_DAYS = "last_30_complete_days"
    CURRENT_MONTH = "current_month"
    CUSTOM = "custom"
    ALL_AVAILABLE = "all_available"

@dataclass(frozen=True, slots=True)
class TenderAnalyticsQuery:
    interval: AnalyticsInterval
    grain: AnalyticsGrain
    source_ids: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    laws: tuple[str, ...] = ()
    include_archived: bool = False
```

The concrete implementation may carry the resolved preset as presentation metadata, but semantic
identity is the exact interval and filters above. Display labels are not contract values.

## Interval rules

- Every interval is half-open: `[start_inclusive, end_exclusive)`.
- Both bounds must be timezone-aware and `start < end`.
- `timezone_name` is a bounded explicit IANA name or audited application alias. Acceptance uses
  `Europe/Moscow`; UTC is allowed in tests.
- Bounds are normalized to the declared display zone before fingerprinting. Equivalent instants and
  zone produce one canonical ISO-seconds representation.
- Local days use the declared zone. ISO weeks start Monday. Months are calendar months.
- Boundary construction uses datetime/calendar operations, never localized string parsing.
- A record exactly at `start` is included; one exactly at `end` is excluded.
- Day/week/month buckets cover the interval without overlap and are sorted by period start.
- Partial edge buckets are permitted only for CUSTOM/CURRENT_MONTH and remain explicitly bounded.

## Preset resolution

Preset resolution accepts one injected aware `now` and returns exact bounds:

- `LAST_7_COMPLETE_DAYS`: seven completed local calendar days ending at today's local midnight;
- `LAST_30_COMPLETE_DAYS`: thirty completed local calendar days ending at today's local midnight;
- `CURRENT_MONTH`: local first-of-month midnight through the injected `now` rounded to a stable
  explicit end instant selected by the UI/controller;
- `CUSTOM`: exact user-provided aware bounds after validation;
- `ALL_AVAILABLE`: minimum confirmed discovery/source-observation time through the injected stable
  end bound; records with unknown legacy time stay in `unknown_time` evidence and do not move bounds.

The documented default is `LAST_30_COMPLETE_DAYS`, grain `DAY`, all available sources/statuses/laws,
and active records only. Reset returns exactly that query for the same injected `now`.

## Legacy and ambiguous time

Storage text is parsed once at the analytics boundary:

- aware ISO text is converted through UTC to the display timezone;
- naive text receives no offset and is classified `unknown_time`;
- malformed, absent, or impossible time is `unknown_time`/missing evidence;
- a source-supplied explicit timezone may be used only through the existing
  `TenderFreshnessService` deadline normalization;
- `first_seen_at` never falls back to `published_at` or `last_seen_at`;
- deadline never falls back to execution deadline;
- freshness observation never becomes the current UI/render clock.

Unknown time contributes to denominator/excluded counts and export reason codes. It is not silently
placed into the first, last, current, or `unknown` date bucket.

## Filter validation and normalization

Filter tuples are copied to immutable tuples, whitespace-trimmed, case-normalized where their
existing source contract is case-insensitive, deduplicated, and sorted by stable machine ID.

- `source_ids`: existing configured/source IDs; unknown IDs fail closed.
- `statuses`: closed `TenderStatus` values including `unknown`; unknown status filters fail closed.
- `laws`: bounded canonical law tokens only when the audited payload restore exposes them; unknown
  or unsupported law filters fail closed and are not treated as free text.
- `include_archived`: explicit boolean; no tri-state coercion.
- Empty tuple means “all available/applicable,” not “no rows.”
- No raw SQL, field name, predicate, regex, callable, arbitrary mapping, or localized label enters
  the query.

The query applies the same population constraints to aggregation, chart translation, textual
equivalent, contributor selection, export, and drill-down. Metric-specific time semantics remain
declared in the catalog: TA-01/TA-03 use interval buckets; TA-02/TA-04 are current `as_of` views and
must not invent historical status/deadline snapshots.

## Deterministic fingerprint

The semantic query projection has fixed key order and contains:

```text
contract_version
interval.start ISO 8601
interval.end ISO 8601
timezone_name
grain
source_ids in canonical order
statuses in canonical order
laws in canonical order
include_archived
```

Compact UTF-8 JSON with fixed separators is hashed with SHA-256. The lowercase hex digest is the
query fingerprint. Locale, preset label, theme, current widget draft, wall clock, object address,
and repository row order are excluded.

## Filter UI and applied state

- Controls edit a draft; charts and export continue using the visibly identified applied query.
- Apply is disabled for an invalid range/filter and shows an allowlisted local reason.
- Applied bounds, timezone, grain, source/status/law filters, and archive mode are visible in text.
- Reset creates the documented default via the injected clock.
- Navigation context carries a bounded code-owned serialization of the applied query fields (or
  equivalent explicit closed fields) and is validated by the existing `RouteContext`; no arbitrary
  dict or SQL is stored.
- Back/return restores the applied query and focus token. A deleted/invalid context fails safely to
  the documented default without starting collection/network work.
- Keyboard order is interval, grain, sources, statuses, laws where enabled, archive, Apply, Reset,
  refresh, charts, contributors, export.

## Export and evidence

JSON and CSV include exact aware ISO bounds, timezone name, grain, and query fingerprint. They never
emit a localized date as the sole bound. Each metric/point includes unknown-time/excluded counts and
safe reason codes so time ambiguity remains reviewable.

## Stop conditions

Stop for any required invented timezone, locale-dependent boundary, open-ended mutable predicate,
unsupported law owner, historical status reconstruction, fallback timestamp, query/export mismatch,
or need to persist filters outside the accepted navigation/QSettings ownership.
