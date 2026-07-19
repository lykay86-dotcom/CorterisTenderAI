# RM-145 drill-down matrix

## Typed action contract

Every actionable `DashboardKpi` carries a typed immutable action containing an existing `RouteId`,
one closed `DashboardFilterId`, and an optional focus token. The Dashboard page emits the action
object; `ModernMainWindow` forwards an existing typed route request. The router validates and
transports context but never calculates KPI membership.

Closed filter IDs:

- `workflow_profit_contributors`
- `tenders_created_today`
- `tenders_score_80_plus`
- `workflow_active_proposals`
- `workflow_active_projects`
- `workflow_attention`

Unknown filter IDs fail validation and are not silently ignored. Route context permits tender
filters only on the tender route and workflow filters only on the workflow route.

## Value-to-filter matrix

| KPI key | Route | Filter ID | Destination owner | Exact parity assertion |
|---|---|---|---|---|
| `potential_profit` | `RouteId.WORKFLOW` | `workflow_profit_contributors` | `BusinessWorkflowPage` + existing model/repository | Visible stable IDs equal source contributor IDs and `sum(Decimal(profit)) == raw_value` |
| `new_tenders` | `RouteId.TENDERS` | `tenders_created_today` | `TenderWorkspacePage` + `TenderRepository` | Visible tender IDs equal source IDs and row count equals raw value |
| `recommended` | `RouteId.TENDERS` | `tenders_score_80_plus` | `TenderWorkspacePage` + `TenderRepository` | Visible tender IDs equal score-threshold IDs and row count equals raw value |
| `proposals_in_work` | `RouteId.WORKFLOW` | `workflow_active_proposals` | `BusinessWorkflowPage` + existing proxy/repository | Visible IDs equal active-proposal contributor IDs and count equals raw value |
| `active_projects` | `RouteId.WORKFLOW` | `workflow_active_projects` | `BusinessWorkflowPage` + existing proxy/repository | Visible IDs equal active-project contributor IDs and count equals raw value |
| `attention` | `RouteId.WORKFLOW` | `workflow_attention` | `BusinessWorkflowPage` + existing proxy/repository | Visible IDs equal blocked/due-soon contributor IDs and count equals raw value |

The current route registry maps `RouteId.WORKFLOW` and its child route IDs to the unified business
workflow destination. RM-145 reuses that identity and does not create another route or page.

## Shared-selection rule

Parity is proven by a single selection rule per KPI source:

- repository/query owner returns typed values plus stable contributor IDs;
- Dashboard uses those values and IDs as evidence;
- destination owner applies the corresponding closed selector or exact contributor-ID scope;
- tests feed both paths the same temporary-repository fixtures and compare stable sets;
- the money test additionally recomputes the `Decimal` total from filtered contributors.

The page must not reconstruct membership from formatted text. The router must not query a
repository. A filter must not broaden because of pagination, a 100-row cap, implicit timezone,
archive visibility, or a different status set.

## Navigation and restoration

- Mouse click, Enter, and Space emit the same typed action.
- The action becomes an ordinary typed route request and participates in RM-142 history/context.
- The destination restores the Dashboard filter before selecting/focusing a record.
- Existing search, kind, status, archive, and record-focus context continues to work. A Dashboard
  filter is a closed additional scope; incompatible combinations are validated or cleared by the
  destination owner rather than silently widening the population.
- Browser-style back/forward and direct typed navigation restore the same scope.
- Refresh reruns the same selector against current repository state; it does not retain phantom rows.

## State-dependent activation

| KPI state | Action behavior |
|---|---|
| `LOADING` | disabled; loading announced |
| `READY` | enabled |
| `ZERO` | enabled; opens an exact empty cohort |
| `PARTIAL` | enabled; limitation announced before/with destination context |
| `STALE` | enabled; stale age announced |
| `ERROR` | disabled; failure reason announced |

## Acceptance fixtures

Focused tests must include:

- more than 100 active tenders so the “today” count cannot regress to the old projection cap;
- naive and aware timestamps around the Europe/Moscow day boundary;
- score 79.99, 80, missing score, and a score-80 tender with a critical stop to prove cohort wording
  does not become a recommendation;
- proposals/projects at every included and excluded status plus archived rows;
- blocked, due today, due in three days, due in four days, completed, and cancelled workflow rows;
- multiple workflow records for one tender to prove project priority and one-profit-contributor rule;
- fractional money values to prove exact `Decimal` parity;
- empty, partial, stale, and failed source states;
- route/context round-trip and keyboard activation for all six typed actions.
