# RM-150 immutable table contract

Baseline: `c7b9c2210dbcbb5db7b9b24fc81f0809d05f8d6b`

## Qt-free value boundary

The common contract lives in `app/ui/tables/contracts.py` but imports no PySide6 symbol. Its public
values are frozen dataclasses/enums and immutable tuples:

- `TableSurfaceId`: stable audited surface ID.
- `TableColumnId`: stable semantic column ID, independent of translated header text or position.
- `TableRowId(namespace, value)`: non-empty opaque domain identity; namespace comparison is exact.
- `TableRevision`: non-empty source revision/fingerprint used for revalidation.
- `TableCell`: safe display text plus typed sort/export value and explicit accessibility text.
- `TableRow`: exact row ID, revision, cells and immutable action metadata.
- `TableColumn`: ID, header, value kind, sort/filter/export policy and accessible description.
- `TableSnapshot`: surface ID, source fingerprint, explicit state, columns, rows and status metadata.

Construction rejects duplicate column IDs, duplicate row IDs, missing cells, invalid state/payload
combinations and mutable collections. Display values are not parsed back into domain values.

## Roles and adapters

The Qt model exposes stable roles for row identity, row revision, column identity, typed sort value,
typed export value, action availability, state and accessible text. `DisplayRole` is presentation
only. No action, selection restore, sort, filter or export reads identity from `DisplayRole` or row
position.

`QAbstractTableModel` is the common projection target. Bounded adapters may consume existing
RM-146/RM-147/RM-148/RM-149 snapshots without replacing their owners. `QTableWidget` compatibility
is allowed only during a listed migration and must store/read the same exact roles.

## Value semantics

- Money/ratio/score values retain `Decimal`; float conversion is forbidden at the contract boundary.
- Date/time values use existing aware domain values or canonical text; mixed implicit coercion is
  forbidden.
- Text filtering uses deterministic Unicode `casefold()` over explicitly filterable fields.
- Missing values are explicit and sort with the column's declared null policy.
- Stable row identity is the final total-order tie-breaker; input arrival order is not a hidden key.
- Critical stop-factor priority and approved recommendation are immutable cell facts from RM-107/
  RM-149 owners; table code cannot calculate either.

## State and update invariants

The only states are `LOADING`, `EMPTY`, `ERROR`, `PARTIAL` and `READY`. State content is outside the
row collection. `READY`/`PARTIAL` may contain rows; `EMPTY` contains none; `ERROR` cannot masquerade
as an empty success. Snapshot replacement is atomic from the view's perspective and selection is
restored only by exact row identity under the identity contract.

## Security and ownership

Cell text is plain text unless an existing audited renderer explicitly sanitizes it. The contract
does not open URLs, paths or rich text. Adapters perform no repository, filesystem, network, keyring,
AI, score, decision or FX operation. Existing dependency-injection and controller paths remain the
only action owners.
