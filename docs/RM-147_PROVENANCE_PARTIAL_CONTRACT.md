# RM-147 provenance, coverage, partial, and conflict contract

Contract version: `tender-analytics-evidence-v1`

## Evidence types

Public contracts are frozen, Qt-free, bounded, and use stable machine IDs:

```python
class AnalyticsEvidenceQuality(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    STALE = "stale"
    CONFLICTED = "conflicted"
    UNKNOWN = "unknown"

@dataclass(frozen=True, slots=True)
class AnalyticsSourceCoverage:
    source_id: str
    requested: bool
    enabled: bool
    outcome: str
    observed_at: datetime | None
    freshness: str
    item_count: int | None
    reason_code: str

@dataclass(frozen=True, slots=True)
class AnalyticsEvidence:
    quality: AnalyticsEvidenceQuality
    source_ids: tuple[str, ...]
    run_ids: tuple[str, ...]
    contributor_count: int
    missing_count: int
    excluded_count: int
    unknown_time_count: int
    conflict_count: int
    reason_codes: tuple[str, ...]
```

Metric/point identity, version, query fingerprint, snapshot generation/as-of, and exact contributor
IDs live in the enclosing analytics contracts and exports. Evidence contains no raw mapping/payload.

## Source coverage mapping

Coverage reuses existing provider outcomes and source-monitoring semantics. It does not invent a
new health policy.

| Existing evidence | Coverage outcome | Item count | Effect |
|---|---|---|---|
| provider `success` | `success` | persisted non-negative count | usable current coverage |
| provider `empty` | `empty` | exact `0` | complete zero only for that observed source/run |
| `failed` | `failed` | `None` | partial/error, never zero |
| `timed_out` | `timed_out` | `None` | partial/error, distinct from failed |
| `cancelled` | `cancelled` | `None` | incomplete/neutral, distinct from zero |
| `not_configured` | `not_configured` | `None` | requested source unavailable |
| `disabled` readiness | `disabled` | `None` | visible when applicable/requested |
| `unsupported` | `unsupported` | `None` | visible safe reason |
| `skipped` | `skipped` | `None` | incomplete/neutral |
| `circuit_open` | `circuit_open` | `None` | incomplete operational evidence |
| no valid outcome | `unknown` | `None` | unknown coverage |

`observed_at` is the persisted completed/monitoring time. A refresh/render clock cannot replace it.
Naive, malformed, or excessive-future evidence is classified invalid/unknown using existing source
monitoring rules. Source order is the stable configured/source-ID order, followed by unknown IDs.

Coverage contains only allowlisted `reason_code`. Raw error message, exception, SQL, provider URL,
query/fragment, credential, response body, and local path are excluded from UI and export.

## Snapshot and metric states

Closed states are `LOADING`, `READY`, `EMPTY`, `PARTIAL`, `STALE`, `CONFLICTED`, `ERROR`, and
`TOO_LARGE`.

- `LOADING`: a generation is active; no mixed-generation publication is allowed.
- `READY`: usable current snapshot with complete applicable coverage and no unresolved
  bucket-defining conflict.
- `EMPTY`: local read succeeded with complete applicable coverage and exact contributors are empty.
- `PARTIAL`: at least one requested/applicable source lacks a current successful/empty outcome, but
  usable current facts remain.
- `STALE`: only the last usable snapshot is displayed after a failed/currently unavailable refresh;
  original source observation/as-of values are retained.
- `CONFLICTED`: an unresolved conflict affects a bucket-defining field and remains visible.
- `ERROR`: no usable snapshot exists or safe local reading failed.
- `TOO_LARGE`: explicit RM-146/RM-147 limit exceeded; no hidden sampling/truncation.

State precedence follows the metric catalog. Source coverage may be partial while a specific metric
is still complete only when the catalog proves that source is not applicable; this disposition is
explicit, never inferred from a zero count.

## Freshness and last-known data

- Existing persisted verification/freshness state remains authoritative.
- A failed refresh may retain a previously displayed immutable snapshot as `STALE`; it cannot
  rewrite its generation-independent semantic content or original observation time.
- Current controller generation and retained snapshot generation remain separately visible.
- Repeated failures do not reset source age.
- Missing freshness evidence is `UNKNOWN`, not fresh.
- `TenderFreshnessService` remains the deadline normalization/reverification owner; analytics uses
  its values and flags but does not reschedule verification.

## Conflict resolution semantics

The service reads existing `list_field_conflicts`, `list_field_candidates`,
`list_field_resolutions`, verification state, and accepted manual selections.

- An accepted manual resolution may supply the effective bucket value already represented by the
  existing collector contract.
- A conflict with `unresolved=True` and no accepted manual selection is never resolved by latest
  row, source priority invented by analytics, lexical order, or UI choice.
- If the conflicting field defines a bucket (`status`, `application_deadline`, source identity, or
  discovery time), the contributor goes to the catalog's unknown/conflicted disposition.
- The contributor remains selectable and drillable by exact `registry_key`.
- Point evidence increments `conflict_count`, includes an allowlisted reason such as
  `unresolved_status_conflict` or `unresolved_deadline_conflict`, and uses
  `AnalyticsEvidenceQuality.CONFLICTED`.
- Metric state becomes `CONFLICTED` when any visible point/population is affected. If conflict is
  non-bucket metadata, it remains point evidence without changing membership according to the
  catalog.
- Export includes conflict count/flag and safe reason code. Chart uses text/pattern/accessible
  description in addition to color.

## Missing and excluded distinctions

The following remain separate in contracts, presentation, and export:

- exact zero from a successful complete read;
- missing value;
- unknown category;
- deliberately excluded by query/catalog;
- partial source coverage;
- stale retained evidence;
- unresolved conflict;
- invalid/naive legacy time.

`None` is never coerced to zero. Denominator/record count, missing, excluded, unknown-time, and
conflict counts are shown. A tooltip or chart gap is not the sole explanation; the textual
equivalent and selection summary carry the same limitation.

## Deterministic aggregation of evidence

- source IDs and run IDs are deduplicated and sorted by stable ID;
- contributors are sorted by `registry_key`;
- safe reason codes use a closed precedence/order;
- evidence quality is derived by explicit precedence, never average confidence;
- no invented percentage/confidence score is computed;
- shuffled repository rows produce identical points, evidence projections, and JSON bytes.

## Security and privacy

Allowed: stable provider/source/run IDs, exact registry keys, safe status/freshness enums,
allowlisted reason codes, aware timestamps, non-negative counts, and conflict field categories.

Forbidden: raw canonical payload, customer-data dump, provider response, source URL, exception,
traceback, SQL text, database/private path, credentials/tokens, and AI-generated confidence.

## Acceptance

Fixtures must prove complete zero, failed source as partial not zero, timeout/cancel/disabled/not
configured distinction, stale original time retention, unresolved/accepted conflict behavior,
unknown legacy time, deterministic ordering, safe export, and source coverage visible beside the
chart and in textual data.
