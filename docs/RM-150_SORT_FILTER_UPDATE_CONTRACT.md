# RM-150 sort, filter and update contract

Baseline: `c7b9c2210dbcbb5db7b9b24fc81f0809d05f8d6b`

## Typed sort

`SortSpec` is an immutable ordered tuple of `(TableColumnId, direction, null_policy)`. Only sortable
declared columns are accepted. Comparisons use the cell's typed sort value: `Decimal` for exact
financial values, canonical date/time values for dates, booleans/integers in their own domains and
Unicode-casefolded text for text. The exact `(namespace, value)` row ID is always appended as the
final ascending tie-breaker, producing a total deterministic order.

No formatted currency, localized date, status label or display string is parsed for sorting. NaN,
mixed incomparable types and undeclared columns fail closed during adaptation.

## Deterministic filter

`FilterSpec` contains a normalized query and explicit column predicates. Free text is stripped and
`casefold()` is applied once; it searches only columns marked filterable. Structured predicates use
typed values and declared operations. All predicates combine deterministically with AND; any
multi-value predicate declares its own OR semantics. Filtering never changes the source snapshot or
selection identity.

Provider `PARTIAL` and `ERROR` metadata, critical status and action availability are not discarded
by a text filter; status presentation remains outside rows or in explicit filterable columns.

## Atomic updates

An update accepts one complete immutable snapshot. The adapter computes identity-based inserts,
removals, moves and changed rows, or performs a bounded reset when the existing model protocol cannot
safely express the delta. At no point may a visible index refer to a different identity under an
outstanding action token.

After update:

- sort/filter specs remain when their referenced columns still exist, otherwise they fail closed;
- exact selection is restored only if its ID exists;
- vanished selection becomes `None` without neighbor fallback;
- scroll/focus restoration is best-effort by ID and never changes logical selection;
- source fingerprint and visible fingerprint change together atomically;
- stale action tokens fail revalidation.

Duplicate IDs, duplicate columns, an unchanged fingerprint with changed content or a revision change
without source-fingerprint change are contract violations.

## Concurrency boundary

Repository/network/AI/file work remains outside the model and UI thread. Snapshot publication is the
only table update input. The adapter owns no timer, worker or cache that can outlive its existing page
or dialog owner.
