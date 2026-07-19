# RM-149 navigation and context matrix

## Context contract

RM-142 remains the sole route/history owner. RM-149 adds a bounded tender identity kind to the
existing closed `RouteContext`; it does not add a second router, primary route or persisted history.

| Origin | Identity kind | Destination | Preserved context | Return/focus |
|---|---|---|---|---|
| Dashboard legacy feed | `legacy_orm` | existing Tenders workspace | Dashboard route + stable feed focus token | Back restores Dashboard and feed focus; no registry action |
| Dashboard registry card seam | `registry` | common registry detail | exact key, generation, focus token | Back restores card identity/focus |
| Persisted search results | `registry` | common registry detail | profile/run/query + selected key in dialog owner | close/return restores same result row |
| Transient search result | none/transient | local bounded preview only | run/query/row | cannot masquerade as registry detail |
| Registry table | `registry` | embedded common detail panel | filters/sort/exact selection | nested dialog close restores detail action; selection unchanged |
| RM-147 analytics | `registry` | common registry detail | immutable analytics fingerprint/query/point/key | close returns to same point/contributor focus |
| Legacy workspace | `legacy_orm` | existing overview/analysis tab | section/filter/legacy ID | RM-142 back behavior unchanged |
| Detail → documents/requirements/full/score/verification/commercial | `registry` | existing modeless dialog/controller | exact identity + action focus token | close returns focus to emitting detail action |

## Admission rules

- New registry requests require `tender_id` plus `tender_identity_kind=registry`.
- Existing context without a kind remains legacy compatibility and may only call
  `TenderWorkspacePage.open_tender()`.
- A target handler rejects a mismatched kind before navigation/history changes.
- Unknown/deleted/stale identity returns a typed failure and leaves current route/selection/focus.
- History contains only bounded scalar context/focus tokens; no QWidget/domain/service references.

## J03 Dashboard

Enter/Space activates exact card identity. A successful registry request opens the common detail;
Back returns to the Dashboard snapshot and stable card/feed focus token. Legacy ORM rows keep their
accepted workspace behavior. Missing identity does not replace the current route.

## J09 Registry and analysis

Registry filters, sort and exact selected key remain owned by `TenderRegistryDialog`. Documents,
requirements, full analysis and decision dialogs are delegated using that same key. Each nested
dialog close resolves a bounded action focus token; refresh republishes only the exact identity.

## J11 Verification

Unresolved conflict selects `view_verification` as primary. The existing verification dialog owns
review/resolution. On committed resolution the detail assembler reloads exact state; on cancel/error
it retains the last safe snapshot and selection. Focus returns to the verification action or critical
banner.

## Analytics

RM-147 contributor IDs are passed byte-for-byte. No analytics-only detail or re-aggregation is
created. A disappeared contributor fails closed. Multiple contributors remain the RM-147 list owner.

## Keyboard and accessibility

Tab order follows critical → identity → decision/primary → statuses → evidence → secondary actions.
Enter/Space activates enabled actions; Escape closes the modeless detail/dialog according to its
existing owner; disabled actions do not run by shortcut. Critical explanation, all status text and
full action descriptions are keyboard reachable and not color-only.
