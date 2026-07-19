# RM-150 table migrate/keep matrix

Baseline: `c7b9c2210dbcbb5db7b9b24fc81f0809d05f8d6b`

The authoritative site IDs and the complete 35-site inventory are in
`RM-150_TABLE_SURFACE_AUDIT.md`. This matrix defines delivery waves and ownership, not a second
inventory.

| Wave | Stable site IDs | Contract branch | Existing owner preserved | RM-150 result |
|---|---|---|---|---|
| A | 007, 010, 014 | model/view foundation | chart, Dashboard, workflow models/controllers | shared roles, stable selection, deterministic sort/filter/update |
| B | 020, 024 | tender identity | RM-149 detail/controller and registry repositories | exact typed registry/legacy IDs; no row-index action |
| C | 022, 023 | analytics/export | RM-147 snapshot/export and RM-148 Decimal | same snapshot, order, fields, IDs and fingerprint |
| D | 008 | provider state | provider manager/service | explicit ready/partial/error state; exact provider action ID |
| E | 026, 027 | editable tables | workspace estimator/catalog handlers | stable edit identity; no action retarget after sort/filter/update |
| F | 003 | destructive action | backup catalog/service | identity + revision revalidation before restore/delete |

`KEEP` sites 001, 002, 005, 011, 012, 015, 016, 017, 028, 031, 032 and 035 receive no
production rewrite. Tests may characterize their boundary where a migrated adapter interoperates
with them.

`DEFER` sites 004, 006, 009, 013, 018, 019, 021, 025, 029, 030, 033 and 034 receive no RM-150
production changes. Their current owner, identity namespace and lifecycle remain explicit. A future
package must re-audit them; RM-150's common contract does not silently opt them in.

## Migration rules

- Adapt source data once into an immutable `TableSnapshot`; widgets do not query repositories.
- Domain identity remains namespaced and opaque. Display text, title, row number and equal-looking
  strings are never identity bridges.
- Migrations replace row-position action lookup before changing appearance.
- Existing controllers receive exact domain identity and revalidate mutations; table adapters do not
  perform repository, network, filesystem, AI, scoring or FX work.
- Existing business exporters remain owners. The shared export projection supplies exactly the
  visible snapshot defined in the parity matrix.
- A migrated site may retain its visual class temporarily if it consumes the contract through a
  tested adapter. Completion is behavioral, not a blanket widget-name replacement count.

## Stop conditions

Stop the package on ambiguous identity, an action that can retarget after refresh, Decimal coercion,
decision/critical precedence drift, fake state rows, export divergence, unbounded UI-thread work,
required schema/dependency/network expansion, or red neighboring/full/frozen gates.
