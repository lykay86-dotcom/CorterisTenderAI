# RM-149 identity and source-of-truth decision

Decision: **typed identity namespace (RM-149 route option B)**.

## Canonical identity

`TenderIdentity` contains a bounded `kind` and exact `value`:

- `registry`: value is the opaque `TenderRegistryRecord.registry_key`; this is the canonical identity
  for discovered-tender card/detail, analytics drill-down and Collector actions.
- `legacy_orm`: value is the exact existing `Tender.id` string; this is a compatibility identity for
  `TenderWorkspacePage` and Dashboard's existing ORM feed.

Blank, control/bidi-bearing or over-bound identities are rejected. Kinds never auto-convert. An ORM
ID that textually equals a registry key remains a different identity. Title, row index, procurement
number, external ID, source URL and fuzzy similarity are never identity bridges.

## Source of truth

- Registry detail facts: `TenderRegistryRepository.get_record()` and `.get_tender()`.
- Verification, freshness, conflicts, latest persisted score and persisted RM-107 decision:
  existing `CollectorStateRepository` on the same `tender_registry.sqlite3`.
- Occurrence history: bounded `TenderRegistryRepository.list_tender_occurrences()`.
- Financial display: RM-148 `MoneyAmount`/formatter with the record's explicit currency.
- Actions: existing `TenderSearchUiController`, registry repository and existing services.
- Analytics: RM-147 contributor identity is passed unchanged; analytics is never re-queried by detail.

No presentation cache or new repository is introduced.

## Route contract

`RouteContext` gains an optional bounded `tender_identity_kind`. New tender detail requests must
provide both `tender_id` and kind. Existing RM-142 callers without a kind remain legacy-compatible
and are treated only as `legacy_orm`; they are never admitted to registry-only actions.

Registry detail uses the existing Tenders hierarchy and existing registry dialog/controller rather
than a second primary route or page stack. Navigation history stores the kind and exact value as
closed scalars. Back/return preserves the origin route/focus token and does not serialize domain or
QObject instances.

## Search and Dashboard admission

- A transient search `UnifiedTender` may calculate its deterministic candidate key only through the
  existing `tender_registry_key()` owner. Canonical detail is enabled only if
  `TenderRegistryRepository.get_record(candidate)` returns the exact saved row.
- A non-persisted result is explicitly transient and may keep its legacy local view; it cannot invoke
  registry-only decision/actions as though persistence existed.
- Existing Dashboard ORM rows remain `legacy_orm`. A separate injected registry-backed projection may
  display canonical cards; no number/title matching is allowed.

## Fail-closed outcomes

- blank/malformed identity: `identity_invalid`;
- unknown exact registry row: `tender_not_found`;
- unsupported kind for an action: `identity_kind_unsupported`;
- missing bridge for legacy action: `identity_ambiguous`;
- stale snapshot/action fingerprint: `action_stale`.

Failure preserves current route, selection and focus and never opens a neighboring record.

## Compatibility and rollback

RM-142 `RouteContext(tender_id=...)` remains accepted for legacy workspace deep links. Registry
producers adopt the explicit kind. Rollback removes new projection/adapters and the optional context
field; no data/schema rollback is required.
