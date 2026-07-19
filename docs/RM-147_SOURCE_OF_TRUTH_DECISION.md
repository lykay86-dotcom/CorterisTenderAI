# RM-147 source-of-truth decision

Decision ID: `rm147-tender-analytics-source-v1`

Baseline: `570ef10b9ea0666a09aa267cbcb47bab8882f401`

## Decision

Tender analytics reads the existing `tender_registry.sqlite3` through the accepted pair:

1. `TenderRegistryRepository` for canonical current tender records and search-run occurrences;
2. `CollectorStateRepository` for source references, provider outcomes, verification, provenance,
   conflicts, resolutions, and freshness evidence.

`TenderRegistryRecord.registry_key` is the sole contributor identity. Procurement number, title,
source URL, row index, ORM ID, and localized labels are attributes only and never identity.

## Why this source is authoritative

- `registry_key` is the existing SQLite primary key and already connects collector, verification,
  documents, analysis, scoring, and Tender Registry UI paths.
- `first_seen_at`, `last_seen_at`, `seen_count`, current status, archive state, canonical payload,
  and source references are persisted together.
- Collector evidence uses the same physical database and the same key, so provenance and conflict
  visibility do not require a lossy bridge.
- The production search runtime already creates both repository objects for this exact database.
- Exact drill-down is already expressed in `registry_key` by `TenderSearchUiController` and
  `TenderRegistryDialog` actions.

## Rejected alternatives

### SQLAlchemy `TenderRepository`

Rejected for RM-147. It owns ORM `Tender.id` and Dashboard `created_at`/score cohorts in another
lineage. No exact audited mapping to `registry_key` exists, and its time field is not collector
`first_seen_at`. Mixing would create identity, deduplication, provenance, and drill-down ambiguity.

### New analytics repository or database

Rejected. The required facts already exist, and a new owner would duplicate persistence, create
freshness/cache invalidation policy, and require schema/lifecycle/rollback work outside RM-147.

### Direct SQL in service or UI

Rejected. SQL remains encapsulated by existing repositories. Analytics service accepts a typed
read snapshot and owns formulas only; UI never opens the database.

### Persisted/materialized analytics cache

Rejected. The first implementation is local read/aggregate over bounded fixtures and measured
sizes. No evidence currently justifies a cache/table. If later performance evidence requires one,
it needs a separate audited schema and invalidation decision.

## Typed repository projection

The existing repositories may expose narrow immutable read models required by analytics, with
these rules:

- one stable ordered record collection keyed by `registry_key`;
- exact current record fields only, including canonical payload where deadline normalization needs
  the existing service;
- source observations keyed by `registry_key + source + external_id`;
- latest safe provider outcome/coverage evidence by stable source ID;
- unresolved conflict field names/counts and accepted manual resolution state;
- freshness/verification state as persisted, without recomputation in repositories;
- no metric formula, bucket, presentation label, or state precedence inside repository code;
- read-only behavior; no initialization/migration as a side effect when a passive read path is
  requested and the file does not exist;
- deterministic ordering and explicit unavailable/error result rather than raw SQLite exceptions.

## Identity and deduplication rules

- TA-01, TA-02, and TA-04 deduplicate by exact `registry_key`.
- TA-03 counts exact source observations identified by `(registry_key, source_id, external_id)`;
  it is explicitly non-additive as a tender total.
- Contributor IDs are unique and sorted by `registry_key` in every point.
- Source observation identities are not used as tender drill-down identities; they retain the
  parent `registry_key`.
- An unknown key is never replaced with the first row, procurement number, source URL, or ORM ID.

## Time-owner decision

| Fact | Authoritative field | Forbidden substitute |
|---|---|---|
| discovery | `tender_records.first_seen_at` | `published_at`, `last_seen_at` |
| repeated observation | occurrence/run time or source observation time | `first_seen_at` |
| publication | canonical payload `published_at` | `first_seen_at` |
| deadline | canonical payload `application_deadline` plus existing freshness normalization | `execution_deadline` |
| source coverage | persisted provider outcome/monitoring observation | current render clock |

Naive or invalid legacy time remains unknown evidence. The analytics layer never attaches a
fabricated offset.

## Runtime composition

The production shell receives the existing runtime repositories through a narrow installation
seam after `TenderSearchUiController` is installed. If analytics is constructed before the search
runtime is available, it shows a safe local unavailable/error state and accepts the same repository
objects later. It must not construct a parallel provider/search runtime.

## Security and privacy

Only stable IDs, safe labels, normalized values, allowlisted outcome/reason codes, timestamps,
counts, and conflict flags enter the snapshot/export. Raw payloads, provider responses, exception
text, SQL, URLs with query/fragment, credentials, and private paths are excluded.

## Rollback

Rollback is a revert of RM-147 code/tests/docs. No schema, cache, setting, credential, or user data
is created or transformed, so no persistent downgrade is required.
