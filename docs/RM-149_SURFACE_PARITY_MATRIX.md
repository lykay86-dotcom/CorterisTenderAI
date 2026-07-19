# RM-149 surface parity matrix

The same persisted registry fixture must be assembled once and projected without further repository
reads. All migrated surfaces compare exact identity, decision fingerprint, critical warning,
primary-action ID, price projection, evidence/conflict state and snapshot fingerprint.

| Field / behavior | Dashboard registry card | Persisted search result | Registry detail | Analytics drill-down | Full detail |
|---|---|---|---|---|---|
| Identity | exact `registry_key` | exact saved `registry_key` | exact `registry_key` | contributor unchanged | exact `registry_key` |
| Title/number/source | card projection | card projection | snapshot | snapshot | snapshot |
| Price/currency | RM-148 projection | RM-148 projection | RM-148 projection | same detail | RM-148 projection |
| Search relevance | separate labelled fact | separate labelled fact | occurrence context only | not a recommendation | provenance only |
| Approved decision | same persisted summary | same | same | same | same |
| Critical warning | first/card accessible text | first/card accessible text | first detail section | same detail | first section |
| Verification/freshness/conflicts | compact statuses | compact statuses | full statuses/evidence | full statuses/evidence | full evidence |
| Primary action | policy v1 ID | same ID | same ID | same ID | same ID |
| Secondary actions | hidden/summary | bounded | full available catalog | full detail | full catalog |
| Fingerprint | same snapshot fingerprint | same | same | same | same |

## Golden fixture

The deterministic fixture includes a long title/customer, exact Decimal RUB price, aware deadline,
partial/stale provider evidence, unresolved critical conflict, partial documents, persisted positive
score, persisted blocking stop-factor, contrary AI tone, occurrence history and archive variant.

Expected invariants:

- critical warning remains dominant despite the positive score/AI tone;
- `search_relevance` is never labelled recommendation;
- `view_verification` is the primary action for the conflicted blocking fixture;
- shuffled inputs produce identical ordering/fingerprint;
- missing decision is `UNAVAILABLE`, not `NOT_RECOMMENDED`;
- unsafe URL/text/control/bidi inputs fail safely;
- stale action fingerprint cannot mutate archive/verification state.

## Compatibility surfaces

Legacy ORM Dashboard/workspace rows are explicitly `legacy_orm` and are excluded from registry-value
parity unless a future audited persisted bridge exists. Their existing exact-ID navigation remains a
neighboring regression contract; they never receive guessed registry decisions/actions.

## Read and performance parity

One detail assembly uses one exact record read, bounded existing state reads, and at most 100
occurrences. Card projection performs zero repository reads. Batch projection of 0/1/100/1,000/10,000
already assembled snapshots is measured without sampling; repository/service/UI N+1 reads remain zero.
