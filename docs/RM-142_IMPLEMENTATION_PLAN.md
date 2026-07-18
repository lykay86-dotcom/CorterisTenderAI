# RM-142 implementation plan

## Scope and order

Implement only findings UI-141-001 and UI-141-002 after the audit/contract/plan commit. Preserve all
RM-127–RM-140 composition, identity, offline, lifecycle, persistence and deterministic-decision
guards. Do not start RM-143 work.

## Phase 1 — audit-first gate

1. Commit this audit, contract and plan as `docs(rm-142): audit information architecture`.
2. Confirm the commit changes documentation only and the worktree is otherwise clean.
3. Push the branch so local and GitHub state remain synchronized before application work.

## Phase 2 — characterization and expected-red

Add a small characterization commit for current compatibility inputs:

- nine legacy keys and current `add_page`/`.sidebar.select` consumers;
- one `ModernMainWindow`, one page stack and public tender-page import;
- Dashboard quick-action signals, tender-ID pass-through and topbar search delegation;
- tender tab/action/shortcut/object-name identity;
- workflow stable record/filter APIs and RM-140 close order.

Then add a separate expected-red commit with:

- `test_rm142_route_contract.py` — frozen types, safe statuses and closed context;
- `test_rm142_route_registry.py` — unique IDs/aliases, parent graph, deterministic primary order,
  planned/context-required dispositions and no orphan destination;
- `test_rm142_navigation_history.py` — bounded/coalesced history, failed-request exclusion,
  back/return and deleted focus token;
- `test_rm142_navigation_context.py` — allowlist, exact identities and hostile/private input;
- `test_rm142_shell_navigation_integration.py` — one registry/owner/stack, Sidebar/TopBar metadata,
  legacy adapters, planned failure and offline composition;
- `test_rm142_workflow_navigation.py` — proposal/estimate/project intent and stable filter/selection;
- `test_rm142_navigation_security.py` — no runtime objects/secrets/paths/raw errors or I/O.

Expected-red must fail only on absent RM-142 symbols/behavior. Existing tests remain green.

## Phase 3 — pure route package

Create `app/ui/navigation/` with the smallest cohesive modules:

1. frozen enums/dataclasses for route ID/kind/availability, cause/status, context, request, result
   and snapshot;
2. one immutable registry containing the accepted taxonomy;
3. constructor-time validation for IDs, aliases, parents/cycles, order, visibility, planned target
   and context policy;
4. pure canonical/legacy resolution with fixed safe reason codes/messages;
5. bounded in-memory history with maximum 32 and duplicate coalescing.

No PySide6, repository, service, network, filesystem, database, keyring or domain imports belong in
the pure contract/registry modules.

## Phase 4 — one activation owner

Adapt existing `DashboardLayout` rather than adding another router:

- accept/use the canonical registry;
- build Sidebar primary entries and TopBar title from `RouteSpec`;
- bind physical pages/embedded/modal handlers by destination owner key;
- expose typed `navigate`, `back` and `return_to_origin`;
- own current snapshot/history and safe focus-token restoration;
- retain `add_page` and `_page_index` as generated thin compatibility views;
- retain `.sidebar.select(str)` as a signal adapter, including hidden legacy aliases;
- reject unknown/unavailable/context-invalid requests without stack/focus/history mutation.

Do not create another `QStackedWidget` or keep independent titles/order/availability lists.

## Phase 5 — shell and mature destinations

Update `ModernMainWindow` composition/wiring only:

- bind Dashboard, tender and both workflow physical pages to route destinations;
- remove five placeholder page instances and hard-coded peer-route metadata;
- route Dashboard quick actions through the canonical API while preserving their public signals;
- route tender deep links with exact pre-activation validation;
- route topbar search through the same Tenders route and existing unified-search seam;
- route AI/settings to stable embedded tender tabs;
- route topbar notifications and scheduler/notification shortcuts to the same existing QAction
  instances;
- keep profile informational behavior as its registered modal destination;
- keep status-bar feedback and `ui/theme` unchanged;
- keep close/shutdown code ordering unchanged.

## Phase 6 — workflow presentation state

Add a narrow page-owned frozen navigation-state DTO/seam without changing repository ownership:

- capture search/kind/status/archive and selected stable record ID;
- apply typed route intent and saved presentation state;
- preserve ID only if visible, otherwise clear selection explicitly;
- suppress implicit first-row replacement during navigation restore;
- preserve normal non-navigation refresh/create/edit/status/history/archive/restore/import/export
  behavior.

Keep two physical page instances and their timers/services until RM-144. Do not alter JSON schema,
money types, repository transactions or exports.

## Phase 7 — focused journey and regression gates

Run all RM-142 tests plus:

- RM-127 page/modern composition;
- RM-128 unified-search contract/composition;
- RM-140 shutdown/offline/lifecycle/compatibility;
- Dashboard feed/quick-actions/controller;
- workflow model/filter/history/import/export/archive;
- AI provider settings no-readback;
- scheduler and notification tests;
- isolated one-window/one-stack/no-network composition.

Exercise offline J03, J04, J08, J10 and J12 with temporary repositories and fake adapters only.

## Phase 8 — local acceptance and publication

Use the exact current Quality Gate commands:

```powershell
python scripts/check_repository_secrets.py
python -m ruff check .
python -m ruff format . --check
python -m mypy
python -m pytest -q
python -m pip_audit --skip-editable
git diff --check
```

Also run workflow offline/migration/import/composition/build selections from
`.github/workflows/quality-gate.yml`. Record exact commands, counts, warnings, environment and any
approved remote dependency-audit evidence in `docs/RM-142_ACCEPTANCE.md`.

Commit in reviewable stages: characterization, expected-red, typed registry, state/history,
shell integration, offline journeys and acceptance. Push each accepted local commit to the same
branch. Open a feature PR, require Windows Python 3.12/3.13 Quality Gate, merge, verify the exact
merge-SHA gate, then use a separate docs-only closeout PR to mark RM-142 `DONE` and activate RM-143.

## Rollback and stop conditions

Rollback is a revert of RM-142 code/tests/docs. Navigation state is memory-only, so no data/schema
rollback exists. Existing workflow/tender/provider/search/user data remains untouched.

Stop if implementation needs persisted history/context, DB/schema migration, a second page
stack/router/route map, a new repository/service/controller, action recreation, business ownership
movement, live I/O during resolution/composition, credential readback, workflow data conversion,
RM-143 styling, or any change to RM-107 deterministic authority or RM-140 lifecycle.
