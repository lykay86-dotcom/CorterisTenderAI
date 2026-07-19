# RM-147 tender analytics metric catalog

Catalog version: `tender-analytics-metrics-v1`

Contract source: `rm147-tender-analytics-source-v1`

## Catalog rules

The catalog is one immutable tuple/map owned by `app.tenders.analytics.metric_catalog` and
consumed by `TenderAnalyticsService`. Every metric declares its formula and order here. Widgets,
the chart adapter, textual equivalent, selection, drill-down, and exporters consume completed
metric points and cannot redefine membership.

All count contributors use exact `registry_key`. Contributor tuples are unique and sorted by that
key. Source-observation identity additionally includes stable source/provider ID and external ID,
but drill-down retains the parent `registry_key`. Missing is never zero. Financial values, score
bands, recommendation, probability, and arbitrary composites are absent from this catalog.

## TA-01 — Tenders discovered

| Field | Contract |
|---|---|
| metric ID/version | `tenders_discovered` / `tender-discovery-v1` |
| Russian title | `Обнаруженные тендеры` |
| user question | How many unique canonical tenders were first discovered in each period? |
| owner/input | `TenderAnalyticsService`; `TenderRegistryRepository` read snapshot |
| identity | exact `TenderRegistryRecord.registry_key` |
| timestamp | `first_seen_at` only |
| interval | aware half-open `[start, end)` after conversion to display timezone |
| filters | source IDs, normalized status, law when safely restored, archive flag |
| formula | one canonical tender in the bucket containing its confirmed `first_seen_at` |
| unit | `count` |
| missing/time policy | naive, invalid, or absent time is excluded from time buckets and counted as `unknown_time`; no fallback |
| state policy | source partial/stale/conflict state is retained; discovery-time conflict/unknown raises evidence/state |
| order | ascending period start for DAY/WEEK/MONTH |
| drill-down | exact contributor keys from selected period |
| export | standard metric/point/evidence columns plus period bounds |
| exclusions | `published_at`, `last_seen_at`, repeated occurrences, money, score |

The sum of visible points equals the unique contributors with confirmed discovery time inside the
query interval. `unknown_time` is evidence, not an invented extra date bucket.

## TA-02 — Current tenders by normalized status

| Field | Contract |
|---|---|
| metric ID/version | `tenders_by_status` / `tender-status-current-v1` |
| Russian title | `Текущий состав по статусу` |
| user question | What is the current canonical tender population by normalized status? |
| owner/input | `TenderAnalyticsService`; current registry records |
| identity | exact `registry_key` |
| timestamp | snapshot `as_of`; no historical reconstruction |
| interval | shown as query context but does not fabricate historical status; filters current population at `as_of` |
| filters | source IDs, requested statuses, law where confirmed, archive flag |
| formula | count each current canonical record once in its normalized status bucket |
| unit | `count` |
| missing policy | absent/invalid/unrecognized status becomes `unknown`, never excluded silently |
| conflict policy | unresolved status conflict enters `unknown` and is flagged `CONFLICTED` |
| order | `published`, `accepting_applications`, `applications_closed`, `review`, `completed`, `cancelled`, `unknown` |
| drill-down | exact contributors in the selected current bucket |
| export | standard columns with normalized status key |
| exclusions | historical status changes, score/recommendation, localized-label sorting |

The `unknown` point is always present in deterministic catalog order, including a truthful zero
when the current read completed successfully.

## TA-03 — Source observations

| Field | Contract |
|---|---|
| metric ID/version | `source_observations` / `source-reference-observations-v1` |
| Russian title | `Наблюдения по источникам` |
| user question | How many exact persisted source references contributed observations? |
| owner/input | `TenderAnalyticsService`; collector source-reference snapshot and safe provider coverage |
| observation identity | `(registry_key, source_id, external_id)` |
| timestamp | source reference `first_seen_at` for interval membership; unknown remains `unknown_time` evidence |
| interval | half-open `[start, end)` for confirmed first observation time |
| filters | source IDs, parent tender status/law/archive constraints |
| formula | one count per exact source-reference identity; a tender may contribute to several source points |
| unit | `observation_count` |
| missing policy | unavailable source/outcome is partial/error evidence, not zero; unknown source ID uses `unknown` |
| conflict policy | source identity is not resolved from a conflicting display label; unresolved identity is unknown/partial |
| order | stable configured/source ID order, then `unknown`; never count-descending |
| contributors | unique parent `registry_key` tuple per source point; `value` is observation count and may exceed contributor count only when distinct exact references exist |
| drill-down | deterministic parent tender list; UI explicitly labels the value as observations |
| export | observation count, contributor IDs, source ID, coverage and reason codes |
| exclusions | additive total of unique tenders, provider item-count sum, failed source as zero |

UI and export must never title this metric “tenders by source”. Its points are not additive as a
unique-tender total.

## TA-04 — Application deadline horizon

| Field | Contract |
|---|---|
| metric ID/version | `application_deadline_horizon` / `deadline-horizon-v1` |
| Russian title | `Горизонт сроков подачи` |
| user question | How soon do current application deadlines occur in the application timezone? |
| owner/input | `TenderAnalyticsService`, using existing `TenderFreshnessService` normalization |
| identity | exact `registry_key` |
| timestamp | normalized `application_deadline`; `execution_deadline` is forbidden |
| interval | horizon is evaluated at snapshot `as_of`; query filters current population, not historical deadline state |
| filters | source IDs, normalized statuses, law where confirmed, archive flag |
| formula | one current canonical tender in exactly one fixed horizon bucket |
| unit | `count` |
| missing/time policy | missing, invalid, naive without explicit source timezone, or otherwise unconfirmed deadline enters `unknown_or_unconfirmed` |
| conflict policy | unresolved deadline conflict enters `unknown_or_unconfirmed` and raises `CONFLICTED` evidence |
| order | fixed catalog order below |
| drill-down | exact contributors in selected bucket |
| export | standard columns plus confirmed deadline category/evidence counts |
| exclusions | money, execution deadline, second timezone/deadline policy |

Fixed buckets use the display timezone calendar and `[start, end)` boundaries:

1. `expired`: confirmed deadline `< start_of_today`;
2. `due_today`: `[start_of_today, start_of_tomorrow)`;
3. `due_1_3_days`: `[start_of_tomorrow, start_of_today + 4 days)`;
4. `due_4_7_days`: `[start_of_today + 4 days, start_of_today + 8 days)`;
5. `due_later`: `>= start_of_today + 8 days`;
6. `unknown_or_unconfirmed`: no confirmed normalized deadline or unresolved bucket-defining conflict.

The same existing freshness normalization supplies confirmed UTC/user-local values and timezone
status. The catalog groups those values; it does not replace freshness or reverification policy.

## Shared state precedence

Metric state is the highest applicable condition in this order:

1. `ERROR` when no usable local snapshot exists;
2. `TOO_LARGE` when an explicit measured contract limit is exceeded without sampling;
3. `STALE` when only a retained last-known snapshot is displayed;
4. `CONFLICTED` when an unresolved bucket-defining conflict remains visible;
5. `PARTIAL` when requested/applicable source coverage is incomplete;
6. `EMPTY` when the read succeeded and the metric has no contributors;
7. `READY` otherwise.

`CONFLICTED` and `PARTIAL` policy is recorded per point as well as per metric. State is expressed by
text/pattern/accessibility, never color alone.

## Stable point identity

Every point ID is a bounded deterministic digest/token derived from:

```text
metric_id + metric_version + query_fingerprint + bucket_key
```

Labels, locale, theme, row index, and process hash do not participate. The same semantic input gives
the same point ID; the snapshot fingerprint additionally covers contributors, values, evidence,
coverage, generation-independent semantic content, and ordering.

## Conditional metrics deferred

Publication time, law/region distribution, score bands, profile outcomes, change frequency, and
verification breakdown are not part of the mandatory v1 catalog. Law remains a query field only if
the repository read snapshot can restore a confirmed canonical value without another source owner;
otherwise the UI exposes it as unavailable and the implementation stops rather than guessing.
