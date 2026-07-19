# RM-150 export parity matrix

Baseline: `c7b9c2210dbcbb5db7b9b24fc81f0809d05f8d6b`

## Common parity rule

`VisibleTableSnapshot` is derived once from a validated source snapshot plus the active sort/filter
specs. Rendering and export receive that same immutable value. Export preserves visible row IDs,
row order, column IDs, typed export values, source fingerprint and visible fingerprint. It may add
format metadata, but it cannot re-query, re-sort, parse display text, include filtered rows or omit a
visible semantic column without an explicit site rule below.

| Sites | Existing export owner | Rows/order required | Values/identity required | RM-150 disposition |
|---|---|---|---|---|
| 007 chart table | RM-146 chart exporter | exact table projection order | series/point IDs, chart fingerprint, typed values | bind common visible snapshot; retain exporter |
| 014 workflow | workflow Excel exporter | exact visible proxy order | record IDs, RM-148 Decimal values, active filters | adapt exporter input; retain reporting owner |
| 022 financial analytics | RM-148 financial snapshot/export path | exact visible metric order | Decimal and unit, no float round-trip | common projection |
| 023 text analytics | RM-147 snapshot/export | exact contributor/source order | contributor IDs, source/partial/conflict facts, fingerprint | common projection |
| 010 dashboard | no table export | not applicable | selection/open identity still shares snapshot | explicit `NO_EXPORT` |
| 020/024 tender | existing detail/report actions, no generic row export | not applicable | registry/legacy namespaces remain exact | explicit `NO_EXPORT` |
| 008 provider | no export | not applicable | provider ID and partial/error metadata | explicit `NO_EXPORT` |
| 026/027 editable grids | existing workspace save/calculation paths, not export | not applicable | stable line IDs and exact edited values | explicit `NO_EXPORT` |
| 003 backup | backup catalog/service, not export | not applicable | exact backup ID/revision | explicit `NO_EXPORT` |

## Failure rules

Export is disabled for `LOADING` and `ERROR`. `EMPTY` exports only when the existing format owner
explicitly supports a header-only artifact. `PARTIAL` export includes an explicit partial marker and
the same available rows, never a silent claim of completeness. A fingerprint mismatch, missing typed
value, unknown column or stale visible snapshot aborts export without producing a misleading file.

Parity tests use duplicate display labels, equal sort keys, filtered rows, nulls, Unicode text,
critical rows and exact Decimal fixtures. Tests compare IDs/order/fingerprints and typed values, not
only rendered strings.
