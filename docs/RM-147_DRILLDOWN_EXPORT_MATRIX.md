# RM-147 drill-down and export matrix

Contract versions: `tender-analytics-v1`, `tender-analytics-export-v1`

## Selection contract

```python
@dataclass(frozen=True, slots=True)
class TenderAnalyticsSelection:
    metric_id: str
    point_id: str
    snapshot_fingerprint: str
    contributor_ids: tuple[str, ...]
```

Selection is resolved from the displayed `TenderAnalyticsSnapshot`, never from chart coordinates,
row index, localized label, a fresh repository query, or a recomputed predicate.

- Chart mouse and keyboard selection both carry the RM-146 stable `point_id`.
- The view model finds the exact metric/point in the displayed snapshot and creates the typed
  analytics selection.
- Count metrics require `len(contributor_ids) == value`, except TA-03 where `value` is exact source
  observation count and parent tender contributors may be fewer; that distinction is explicit.
- Contributor order is `registry_key` ascending.
- A changed snapshot fingerprint rejects the prior selection as `stale_selection` unless the view
  model re-resolves the same point ID and identical contributor tuple in the new snapshot.
- Unknown point/metric/key fails closed; it never selects the first item.

## Chart adapter matrix

| Analytics metric | RM-146 kind/X | Series | Point identity | State mapping |
|---|---|---|---|---|
| `tenders_discovered` | LINE / aware TIME | one ordered count series | exact analytics point ID and bucket start | direct except `CONFLICTED` -> chart `PARTIAL` with explicit conflict detail |
| `tenders_by_status` | BAR / CATEGORY | one ordered count series | exact analytics point ID/status key | same |
| `source_observations` | BAR / CATEGORY | one ordered observation series | exact analytics point ID/source ID | same |
| `application_deadline_horizon` | BAR / CATEGORY | one ordered count series | exact analytics point ID/horizon key | same |

The adapter converts integer values to exact `Decimal`, passes existing labels/order/unit, and
projects safe source coverage into the RM-146 `ChartSourceEvidence` alias. It never aggregates,
filters, sorts business contributors, invents confidence, samples, queries repositories, or changes
RM-146 limits. Analytics `CONFLICTED` has no direct RM-146 enum, so visual chart state is `PARTIAL`
with conflict text/pattern; the authoritative analytics metric/text/export state remains
`CONFLICTED`.

## Drill-down matrix

| Metric point | Exact contributor population | Existing destination | Activation |
|---|---|---|---|
| discovery period | registry keys first discovered in exact bucket | `TenderRegistryDialog` | open contributor list; exact selected key opens/preselects registry record |
| current status | current exact registry keys in normalized status | same | same |
| source observations | unique parent registry keys for exact source-reference point | same | value remains labelled observations; list shows parent tenders |
| deadline horizon | current exact registry keys in horizon bucket | same | same |

One contributor may open immediately through the exact registry-record seam. Multiple contributors
remain in the analytics contributor list; Enter/Space on a selected row calls the same seam. The
controller-owned path is:

```text
TenderAnalyticsPage contributor activation
 -> ModernMainWindow / installed TenderSearchUiController
 -> TenderSearchUiController.open_registry_record(registry_key)
 -> existing TenderRegistryDialog.refresh_records()
 -> exact key preselection
```

The seam verifies the key exists in the registry. It does not open a source URL, infer an ORM ID,
create a second dialog, or execute analysis/score actions. Navigation retains `future.analytics`
and focus origin through the existing route/history owner.

The contributor list displays only safe fields already in the snapshot: registry key as internal
identity, procurement number separately, title, canonical source ID, current status, and evidence
state. It is a focused RM-147 list, not a generic RM-150 table framework.

## Exact JSON export

Top-level fixed key order:

1. `contract_version`;
2. `query_fingerprint` and exact query projection;
3. interval start/end/timezone/grain;
4. snapshot generation/as-of/fingerprint/state;
5. ordered source coverage;
6. ordered metrics and points;
7. safe summary counts/reason codes.

Each point contains metric ID/version/title/unit/state, point ID, bucket key/label, exact integer
value, ordered contributor IDs, evidence quality, source/run IDs, missing/excluded/unknown-time/
conflict counts, and safe reason codes. Encoding is UTF-8, compact deterministic JSON, fixed key
order/separators, and one trailing LF. No generated export time is added.

## Exact CSV export

Fixed header/order:

```text
metric_id,metric_version,point_id,bucket_key,bucket_label,value,unit,state,
interval_start,interval_end,timezone,contributor_count,contributor_ids,
source_ids,evidence_quality
```

One row per analytics point in metric/point order. Contributor/source IDs use a deterministic
delimiter/escaping contract. UTF-8 and LF are fixed. Text cells beginning with `=`, `+`, `-`, or
`@` are prefixed with a single apostrophe. Input contracts reject control and bidi characters;
export rechecks before serialization. Exact integer text is never altered by spreadsheet safety.

## Visual export

PNG/SVG use only RM-146 `export_chart_png`/`export_chart_svg` with the already displayed chart spec,
active RM-143 palette, checked viewport/device scale, and RM-146 pixel limit. Visual artifacts do
not replace JSON/CSV. The analytics interval/state/source summary is visible in the page or included
as deterministic sidecar metadata supplied from the same snapshot. Decode/dimensions/no-script/
no-external-reference/privacy smokes are mandatory.

## File policy

Export functions return immutable bytes plus media type, extension, and a safe suggested filename.
Filenames use bounded ASCII-safe metric/date tokens, never title/customer/private path content.
The UI chooses a user path. Writing uses a temporary sibling file, flush/close, and atomic replace;
on failure the temporary file is removed and the prior target remains intact. Overwrite requires
the existing dialog policy. Errors exposed to UI are fixed `export_failed` messages with no raw path
or exception.

## Parity invariants

For every displayed snapshot:

```text
analytics point value == chart Decimal value == textual table value == JSON value == CSV value
analytics point ID == chart point ID == textual point ID == exported point ID
snapshot contributors == selection contributors == JSON/CSV contributors
metric/point order == chart/table order == JSON/CSV order
displayed snapshot fingerprint == selection fingerprint == exported fingerprint
```

JSON/CSV export accepts a `TenderAnalyticsSnapshot` argument only. It cannot access repositories,
controller refresh methods, current filters, chart widget state, wall clock, or provider runtime.
Repeated shuffled source rows normalize to byte-identical semantic JSON/CSV.

## Security and privacy matrix

| Input | JSON/CSV | Visual | UI error |
|---|---|---|---|
| stable registry/source/run IDs | allowed, bounded | safe summary only | not echoed |
| procurement number/title | only where contributor contract requires and validated | bounded label | not echoed on failure |
| raw canonical/provider payload | forbidden | forbidden | forbidden |
| source URL/query/fragment | forbidden | forbidden | forbidden |
| credential/token/secret-shaped value | forbidden | forbidden | forbidden |
| exception/traceback/SQL/private path | forbidden | forbidden | forbidden |
| formula-leading text | apostrophe-neutralized in CSV | plain validated text | not echoed |
| control/bidi text | rejected | rejected | fixed safe reason |

## Acceptance fixtures

Tests cover every metric point, one/many/unknown contributor activation, selection after refresh,
mouse/keyboard identity, exact registry preselection, TA-03 observation/contributor distinction,
byte determinism, formula injection, bidi/control rejection, no re-query, atomic write failure,
PNG/SVG dimensions/privacy, RM-146 `TOO_LARGE`, and exact fingerprint parity.
