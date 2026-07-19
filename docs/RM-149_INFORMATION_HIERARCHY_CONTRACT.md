# RM-149 information hierarchy contract

Contract version: `tender-detail-v1`  
Projection version: `tender-card-v1`

## Immutable Qt-free model

The sole presentation model is an immutable `TenderDetailSnapshot` assembled from existing local
owners. It contains an exact `TenderIdentity`, generation/as-of timestamp, semantic source revision,
typed state, ordered facts/statuses/warnings/evidence/history/actions, persisted decision summary,
snapshot fingerprint and a compact `TenderCardProjection` derived without further repository reads.

Missing, invalid, conflicted, unsupported, stale and not-loaded values remain distinguishable.
Strings are bounded and safe for native rendering. Domain text is never trusted HTML. Dates retain
timezone evidence; money remains `Decimal` with explicit currency through RM-148.

## Required section order

1. `critical` — blocking warning/evidence, when present.
2. `identity` — title, procurement number, source, customer, region, law/procedure, archive state.
3. `decision` — latest persisted approved decision/score state and exactly one primary action.
4. `status` — lifecycle, deadline/timezone, verification, freshness, conflicts, documents, analyses.
5. `facts` — exact procurement facts including RM-148 price projection.
6. `decision_evidence` — components, rationale, factors, missing documents, versions/fingerprint.
7. `analysis` — availability/state only; existing dialogs own full results and operations.
8. `provenance` — source/external ID, observations, verification/conflicts and bounded occurrences.
9. `actions` — deterministic secondary action catalog and return action.

Order is stable and fingerprinted. Critical state cannot be collapsed below decorative analytics.

## Identity block

- `registry_key` is identity; title/number are display facts only.
- Official source action is separate from tender text and shows a validated HTTPS host.
- Long title/customer wrap and preserve full accessible text.
- Archive state is explicit text, not a color.
- Missing facts use typed labels such as `Не указано`, `Не загружено`, `Есть конфликт`, rather than
  an ambiguous dash for decision-critical fields.

## Status strip

Stable ordered IDs are `lifecycle`, `deadline`, `archive`, `verification`, `freshness`, `conflicts`,
`documents`, `requirements`, `full_analysis`, `decision`. Each has label, semantic severity,
explanation, source timestamp and accessible text. Deadline uses accepted Collector freshness fields;
unknown timezone is not guessed from the local machine.

## Card projection

`TenderCardProjection` is derived only from its snapshot and includes identity/title/source,
deadline/lifecycle, RM-148 price, verification/freshness/conflict state, persisted decision state,
critical warning, primary action, snapshot fingerprint and one complete accessible summary. It has no
repository/service/QObject reference and cannot recalculate a decision.

## Determinism and fingerprint

Collections are sorted by semantic stable ID, then source timestamp/identity where needed. The
fingerprint covers contract version, exact identity, semantic record revision, decision
version/fingerprint/time, verification/freshness/conflicts, bounded history and action availability.
It excludes locale-only labels, QWidget identity, memory addresses, current row and visual theme.

Shuffled equivalent inputs must produce the same ordered snapshot and fingerprint.

## States

`LOADING`, `READY`, `EMPTY`, `PARTIAL`, `STALE`, `CONFLICTED`, `NOT_FOUND`, `ERROR`, `CLOSED` are
explicit. `NOT_FOUND` never falls through to another row. `PARTIAL` lists missing sections. `ERROR`
uses safe reason codes and may retain the last safe snapshot. `CLOSED` ignores late publication.

## Rendering boundary

Reusable widgets receive typed snapshots/projections only. They use RM-143 tokens/components,
stable object names, text+icon+a11y state, logical focus order and dark/light theme updates. Source
URLs are parsed separately; no remote content is fetched while rendering.
