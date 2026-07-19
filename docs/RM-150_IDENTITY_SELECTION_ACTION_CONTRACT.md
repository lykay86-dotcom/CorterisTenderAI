# RM-150 identity, selection and action contract

Baseline: `c7b9c2210dbcbb5db7b9b24fc81f0809d05f8d6b`

## Identity

Every actionable row has one `TableRowId(namespace, value)` and one `TableRevision`. Accepted
namespaces are bounded per adapter, for example `registry`, `legacy_orm`, `workflow_record`,
`provider`, `backup`, `estimate_line`, `catalog_line`, `chart_point` and `analytics_contributor`.
Namespace and value are passed unchanged from the existing owner. Row index, display title,
procurement number, path label or equal-looking value in another namespace is never a bridge.

## Selection

- Selection state is zero or one exact row ID; indexes are disposable view coordinates.
- Sort/filter never changes the selected identity. A hidden selected row remains the logical
  selection but produces no visible-index action until visible again.
- Snapshot update preserves selection only when the exact ID still exists.
- If the selected identity disappears, selection becomes `None`; no first/next/previous row fallback
  is permitted.
- Initial automatic selection is prohibited unless a site contract explicitly names an identity.
- Keyboard and pointer selection use the same identity resolver. Enter/double-click dispatch the same
  primary action and never a stale index.
- Focus restoration is by surface ID and row ID, not by row number.

## Action token and revalidation

An enabled row action yields an immutable token containing surface ID, row ID, row revision,
snapshot fingerprint and action ID. Before any mutation or external side effect, the existing
controller/service must reload or inspect its current exact entity and verify:

1. namespace and domain ID still match;
2. entity still exists and is eligible;
3. revision/fingerprint still matches the confirmation context;
4. the requested action is still available.

Failure closes the action without retargeting and requests an exact refresh. Destructive restore,
delete and archive confirmations display the exact entity label from the validated token, but the
label is not identity. Confirmation followed by a sort/filter/refresh cannot change the target.

## Availability and precedence

Availability is supplied by the existing owner and is fail-closed. Table code may hide or disable an
unavailable action but may not infer eligibility. A critical stop factor remains visually and
semantically superior to score/recommendation and sorting cannot demote it. Opening or selecting a
row performs no score, AI, network or repository mutation.
