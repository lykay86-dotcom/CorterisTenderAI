# RM-142 information architecture contract

Contract version: `information-architecture-v1`

Baseline: `999354c892326765792308b2c40a0c8b7236f717`

Status: implementation target

## Canonical ownership

`app.ui.navigation` owns exactly one immutable route registry and pure validation/resolution types.
The existing `DashboardLayout` is the sole production navigation owner: it resolves requests,
activates its existing stack, coordinates registered embedded/modal handlers, owns bounded in-memory
history, publishes snapshots/results, updates Sidebar selection and supplies the TopBar title.

`ModernMainWindow` remains the physical composition/binding root. Sidebar, TopBar, Dashboard and
QAction/legacy string entry points emit navigation intent only. There is no second stack/router,
repository, service or controller in the navigation package.

## Required types

- `RouteId`: closed stable canonical identities below.
- `RouteKind`: `PRIMARY`, `SECONDARY`, `EMBEDDED`, `MODAL`, `COMPATIBILITY`.
- `RouteAvailability`: `AVAILABLE`, `PLANNED`, `DISABLED`, `CONTEXT_REQUIRED`.
- `NavigationCause`: `SIDEBAR`, `TOPBAR`, `QUICK_ACTION`, `SHORTCUT`, `DEEP_LINK`, `BACK`,
  `RETURN`, `COMPATIBILITY`, `PROGRAMMATIC`.
- `NavigationStatus`: `NAVIGATED`, `UNAVAILABLE`, `INVALID_CONTEXT`, `UNKNOWN_ROUTE`, `NO_CHANGE`.
- `RouteSpec`: frozen metadata only; no runtime object.
- `RouteContext`: frozen closed fields; no unrestricted dict.
- `RouteRequest`: target, cause, optional origin/context/focus token and history policy.
- `RouteResult`: status, resolved route, safe reason/message, resulting snapshot, history flag and
  optional recovery route.
- `NavigationSnapshot`: canonical route, route context and safe focus-return token.

Normal unknown/unavailable/context failure is represented by `RouteResult`, not exception control
flow. Programmer-invalid registry construction fails immediately.

## Canonical taxonomy

| Canonical ID | Kind | Availability | Parent | Physical destination | Legacy alias | Primary | Context / disposition |
|---|---|---|---|---|---|---|---|
| `workspace.dashboard` | PRIMARY | AVAILABLE | — | `dashboard` page | `dashboard` | yes | no context |
| `workspace.tenders` | PRIMARY | AVAILABLE | — | `tenders` page | `tenders` | yes | optional `tender_id`, `search_query`, embedded IDs |
| `workspace.workflow` | PRIMARY | AVAILABLE | — | workflow page binding | — | yes | one coherent proposal/estimate/project area |
| `workspace.workflow.proposals` | SECONDARY | AVAILABLE | workflow | `quotes` physical page | `quotes` | no | `workflow_kind=proposal` |
| `workspace.workflow.estimates` | SECONDARY | AVAILABLE | workflow | `estimates` physical page | `estimates` | no | `workflow_kind=estimate` |
| `workspace.workflow.projects` | SECONDARY | AVAILABLE | workflow | workflow physical page | — | no | `workflow_kind=project` |
| `workspace.tenders.ai` | EMBEDDED | AVAILABLE | tenders | tender settings / AI tab | `ai` | no | real AI settings/recheck entry |
| `workspace.tenders.settings` | EMBEDDED | AVAILABLE | tenders | tender settings section | `settings` | no | real embedded settings entry |
| `workspace.tenders.documents` | MODAL | CONTEXT_REQUIRED | tenders | existing documents/controller destination | `documents` | no | exact `tender_id`; recovery `workspace.tenders` |
| `workspace.tenders.scheduler` | MODAL | AVAILABLE | tenders | existing scheduler QAction | — | no | preserves `Ctrl+Shift+P` |
| `workspace.tenders.notifications` | MODAL | AVAILABLE | tenders | existing notification QAction | — | no | topbar and `Ctrl+Shift+N` converge here |
| `workspace.profile` | MODAL | AVAILABLE | dashboard | existing shell profile information | — | no | compatibility modal, no data owner |
| `future.clients` | COMPATIBILITY | PLANNED | — | none | `clients` | no | safe planned result; target RM-156 |
| `future.analytics` | COMPATIBILITY | PLANNED | — | none | `analytics` | no | safe planned result; target RM-147 |

Display titles, deterministic order, icons, allowed context fields, capability/reason codes,
history support and target journey IDs are part of each `RouteSpec`. Titles may change without
changing identity. One alias maps to one canonical route. Duplicate IDs/aliases, missing parents,
cycles, invalid primary configuration, unowned available destinations and planned routes without a
target RM fail registry validation.

The three primary Sidebar areas are Dashboard, Tenders and Business Workflow. Embedded, modal,
context-required and planned compatibility routes are not presented as peer primary workflows.

## Route metadata and availability

`RouteSpec` contains only stable ID, title, parent, kind, availability, order, destination owner key,
allowed context fields, aliases, precondition/reason code, primary visibility, history support,
journey IDs and optional planned RM. It never contains QWidget, QAction, repository, service,
controller, secret, domain object or callable.

- `AVAILABLE`: its bound user job exists.
- `PLANNED`: returns `UNAVAILABLE` with fixed reason/message and target RM; it does not activate a
  placeholder.
- `DISABLED`: returns a fixed local safe reason/recovery and does not change state.
- `CONTEXT_REQUIRED`: missing/invalid required identity returns `INVALID_CONTEXT`; valid context may
  invoke the registered existing destination.

Unavailable/invalid/unknown requests do not change current route, history, selection or focus.
Messages and reason codes are code-owned, bounded and do not echo raw input.

## Closed route context

Allowed fields are explicit optional scalars/enums:

- `tender_id`;
- `workflow_kind`, `workflow_status`, `workflow_archive_mode`, `workflow_search`;
- `workflow_record_id`;
- `search_query` draft for the existing unified-search seam;
- `tender_section`, `settings_section`;
- `focus_token`.

Strings are normalized only at their presentation boundary, length bounded and free of control/bidi
characters where applicable. Tender/workflow identities are otherwise passed exactly; no numeric,
URL/title or row-index inference is allowed. Unknown mapping keys fail closed.

QWidget/QObject references, domain records, arbitrary dictionaries, repository/service/controller,
credentials, filesystem paths, raw exceptions, HTTP material, URL queries/fragments and stale AI
output are prohibited. Context/history is never serialized in RM-142.

## Navigation, history and return

- Registry lookup is deterministic, side-effect-free and bounded by the fixed registry size.
- `DashboardLayout.navigate(request)` returns a typed `RouteResult` for every request.
- Page/embedded/modal destination handlers are registered by physical owner key; binding does not
  create pages or copy route metadata.
- `DashboardLayout.add_page(key, title, widget)` and `Sidebar.select(str)` remain thin documented
  adapters. `_page_index` is a generated compatibility binding view, not a second title/route map.
- TopBar title and Sidebar entries/selection use the resolved canonical `RouteSpec`.
- Consecutive identical snapshots return `NO_CHANGE` and do not grow history.
- History is in memory, fixed at a code-owned maximum of 32 snapshots, and contains no runtime/domain
  objects.
- Only successful, history-enabled navigation records the previous snapshot. Failed and modal
  requests do not pollute page history unless an explicit successful return snapshot is defined.
- `back()` and `return_to_origin()` return typed results, skip invalid/unbound historical targets
  safely, never rerun search/business operations, and cannot restore stale state at startup.

## Focus-origin contract

Focus origin is a bounded safe token (stable object/action name), never a strong QWidget reference or
user text. After successful back/return, the owner resolves the token against live registered
controls and focuses it; if absent/deleted, it uses a documented page-level fallback. Failed routes
preserve focus. Successful tender deep links focus the tender table/current target surface. This is
navigation focus only, not an RM-152 accessibility-conformance claim.

## Workflow state contract

Proposal, estimate and project are typed child intents of one workflow domain. Existing physical
pages and the single repository remain unchanged through RM-142.

Each workflow page exposes a narrow immutable capture/apply seam for search, kind, status, archive
mode and selected stable record ID. Applying a route:

- restores the requested typed kind/filter without repository logic in the router;
- preserves the selected ID only when it remains visible;
- represents no selection or deleted/out-of-scope record as explicit none;
- never selects a neighboring/first row as an implicit replacement;
- does not alter create/edit/status/history/archive/restore/import/export behavior or JSON schema.

Legacy `quotes` and `estimates` aliases continue to open the correct physical view/intent. Quick
actions create proposal/estimate intent through the canonical navigation API and preserve their
existing public Dashboard signals.

## Tender, search, AI, settings and notification contract

- Dashboard feed/activity/advisor tender IDs are sent unchanged to
  `TenderWorkspacePage.open_tender`. A missing ID returns typed failure before outer route/history is
  committed and does not replace the previous selection.
- Global search resolves `workspace.tenders`, then delegates the safe draft through the existing
  `submit_unified_search_text` seam. It never changes equipment `catalog_query`, bypasses the
  controller or replays on back.
- `ai` selects the existing `settings` / `ai` embedded tabs; `settings` selects existing settings.
- Topbar notifications and `Ctrl+Shift+N` invoke the same existing QAction/controller destination;
  scheduler preserves `Ctrl+Shift+P` and its action identity.
- AI disabled/offline behavior, no secret readback, provider settings, RM-140 admission/cancel/CLOSED
  lifecycle and tender-before-dashboard shutdown remain unchanged.
- No modal/action is recreated or reparented by navigation.

## Compatibility and invariants

Mandatory guards remain green:

- RM-127 public import, 8 tender tabs, 6 settings tabs, object names and QAction identities;
- one `ModernMainWindow`, one stack, no hidden/nested production `QMainWindow`;
- all nine legacy route keys have the explicit disposition above;
- existing `DashboardLayout.add_page()` and `.sidebar.select(key)` callers;
- Dashboard quick-action signals, exact tender-ID opening and RM-128 global-search delegation;
- shortcuts/object names and existing menu/toolbar action identity;
- `ui/theme`, status-bar feedback and tender/workflow page attributes used by bootstrap/tests;
- RM-140 offline, one admission owner, bounded shutdown and `CLOSED` behavior;
- workflow stable IDs, repository, JSON/import/export/history/archive/restore contracts;
- RM-107 score/recommendation/hard exclusions and absolute critical stop-factor priority.

Navigation resolution/activation performs no network, keyring, database or filesystem I/O. No DB,
schema, migration, data copy, dependency, design-system, shell extraction, chart, money or business
ownership change belongs to RM-142.

## Acceptance

Expected-red and feature tests must prove unique registry/aliases/parents/order, typed failures,
closed context/security, three primary items, no successful placeholder route, one navigation owner,
one stack, bounded history, back/return/focus deletion safety, workflow stable-state round trip,
exact tender deep link, global search, AI/settings/notification/scheduler convergence and offline
J03/J04/J08/J10/J12.

Stop on a second route map/stack/owner, required persisted navigation state, schema migration, new
service/repository/controller, raw/private context leakage, orphan mature entry point, bypassed
RM-140 lifecycle, changed deterministic decision, or unexplained regression.
