# RM-148 margin semantics

Contract version: `workflow-revenue-margin-v1`.

Margin is revenue margin percentage, expressed in percentage points:

```text
margin_percent = profit / total × 100
```

It is derived and read-only. `total` and `profit` are the only authoritative operands; the persisted
v3 margin is an optional derived cache tagged with the formula version and must equal recomputation.
An imported/manual margin is validation evidence only. A mismatch is `CONFLICTED` and blocks commit
or migration; RM-148 does not introduce override semantics.

Rules:

- available compatible RUB `total > 0` and profit → exact Decimal calculation;
- `total == 0` → `MISSING`/undefined, not `0%`;
- missing operand → `MISSING`; invalid operand → `INVALID`;
- different/unknown currency → `UNSUPPORTED_CURRENCY`;
- negative total/profit → `OUT_OF_RANGE` under the current non-loss contract;
- projection quantizes once to `0.01` with `ROUND_HALF_UP`;
- weighted aggregate margin is `sum(profit) / sum(total) * 100` for compatible included records;
- excluded record IDs and reasons are retained as evidence.

The UI stops calculating or editing margin. Import checks any supplied margin against this owner.
Audit history records operand edits and the canonical derived before/after value without inventing a
user edit for technical migration.

