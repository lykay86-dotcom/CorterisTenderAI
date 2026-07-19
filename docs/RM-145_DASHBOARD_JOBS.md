# RM-145 Dashboard jobs

## User and operator jobs

RM-145 modernizes the Dashboard only where it improves a real decision or navigation job. It does
not introduce analytics or another workflow.

### J01 -- understand the current portfolio at a glance

The operator needs to see six stable summary measures without guessing what they mean. Each card
must show a localized value, its unit, freshness, completeness, source, and an honest state. A zero
must mean a complete observed zero; unavailable or failed data must never be rendered as zero.

Success evidence:

- all six cards come from one registry and one atomic snapshot;
- money remains `Decimal` and counts remain `int` until presentation formatting;
- loading, ready, zero, partial, stale, and error are visually and programmatically distinguishable;
- “Оценка 80+” cannot be mistaken for an AI or deterministic recommendation.

### J03 -- move from a KPI to the exact records behind it

The operator activates a card using mouse or keyboard and lands on the existing tender or workflow
destination with one typed, closed filter already applied. The records visible under that filter
must be exactly the contributors to the source value.

Success evidence:

- counts equal the number of stable contributor IDs under the destination filter;
- potential-profit total equals the `Decimal` sum for its filtered workflow contributors;
- direct links, history, refresh, and filter restoration use the accepted RM-142 route contract;
- no stringly typed page guessing or widget-side formula exists.

### J12 -- continue ordinary work without regression

Dashboard refresh, tender work, and the unified business workflow must retain RM-144 lifecycle and
composition guarantees. A refresh failure in one source explains the affected cards and preserves
the last usable evidence without blocking unrelated source cards. Closing the shell remains bounded
and idempotent.

Success evidence:

- one physical workflow page and one tender workspace remain production owners;
- rapid refresh/close cannot publish an obsolete generation;
- no live provider call, schema mutation, duplicate timer, page, controller, or repository is added;
- RM-141 through RM-144 journey and lifecycle regression selections remain green.

## KPI-specific jobs

| Stable key | Question answered | User action |
|---|---|---|
| `potential_profit` | What potential profit is represented by current workflow records? | Open the exact contributing workflow records |
| `new_tenders` | How many active tenders were created today in the configured local day? | Open exactly those tenders |
| `recommended` | How many active tenders currently have numeric score 80 or higher? | Open those tenders, without implying a recommendation |
| `proposals_in_work` | How many proposal records are in an active working status? | Open the active proposals |
| `active_projects` | How many project records are in an active execution status? | Open the active projects |
| `attention` | How many workflow records are blocked or due within three days? | Open those workflow records |

## State jobs

| State | What the operator must understand | Interaction rule |
|---|---|---|
| `LOADING` | No complete value has been published for the current load | Card is not activated |
| `READY` | Complete, fresh, non-zero evidence is available | Typed drill-down is enabled |
| `ZERO` | Complete, fresh evidence proves an exact zero | Drill-down may open an empty exact filter |
| `PARTIAL` | A usable value exists, but current evidence is incomplete or a refresh failed | Drill-down is allowed and limitation is announced |
| `STALE` | Last usable evidence is older than the freshness threshold | Drill-down is allowed and age is announced |
| `ERROR` | No usable value exists for the required source | Card is not activated; reason is announced |

`UNAVAILABLE` is not adopted: the audit found no permanently unsupported KPI. Missing data is
represented by `raw_value=None` plus `PARTIAL` or `ERROR`, never by a fabricated zero.

## Acceptance scenarios

1. Fresh complete fixtures publish all six cards together and every action opens the exact set.
2. Complete empty fixtures publish `ZERO`, not empty text, missing, or error.
3. One source failure affects only KPIs owned by that source; the other source remains usable.
4. A recent retained value after a failed refresh is `PARTIAL`; after ten minutes it is `STALE`.
5. Locale-aware money/count formatting does not change raw values or parity calculations.
6. Keyboard focus, Enter/Space activation, accessible name/description, focus indicator, and
   contrast remain usable at supported density.
7. Demo content is explicitly marked DEMO and cannot masquerade as repository evidence.
