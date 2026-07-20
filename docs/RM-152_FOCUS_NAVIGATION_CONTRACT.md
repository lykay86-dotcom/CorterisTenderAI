# RM-152 focus and navigation contract

Baseline: `9cb37b9a83f50ac9f8f8e34fdeb582c2ed76e257`

## Sole owners

`DashboardLayout` and the RM-142 route registry/history remain the only shell navigation and route
focus owners. RM-152 extends their validation and fallback behavior; it does not add a router,
global event filter, persisted history, QWidget in route context, or display-text identity.

Dialog owners may use one bounded focus-origin helper. RM-150 table row identity and RM-149 tender
identity remain exact. RM-144/RM-151 close and operation events cannot be reinterpreted as focus
events.

## Focus identity

The logical origin is:

```text
route_id + surface_id + control_id + subject identity? + selection identity?
```

- `control_id` is a unique bounded object/action ID within the surface, not a shared class name.
- subject/selection identities use RM-149/RM-150 namespaces and values, never row indexes.
- tokens contain no QWidget, memory address, user text, secret, path, URL query, or raw exception.
- a visible label may be announced but cannot be the restoration key.

Baseline duplicate values (`CorterisButton`, `QuickActionTile`) and empty sidebar control IDs are
not accepted restoration tokens and must be replaced/adapted at construction.

## Target validity

A target may receive focus only when all are true:

1. QObject is alive and belongs to the expected current surface;
2. widget is visible to the active window and not on a hidden stacked page;
3. widget is enabled;
4. focus policy is not `NoFocus`;
5. subject/selection identity, if any, still matches the current immutable snapshot;
6. modal window ownership permits focus.

The baseline `_restore_focus` checks only object existence. RM-152 adds the remaining checks and a
deterministic fallback resolver through the same `DashboardLayout` seam.

## Initial focus rules

| Surface | Initial focus |
|---|---|
| application launch | selected Dashboard route's first meaningful action/collection; never a text field that captures unexpected typing |
| sidebar route | the activating route control retains focus unless the route contract explicitly moves to a task input |
| top-bar/deep-link task | invoked task's meaningful input/collection after successful admission |
| ordinary form/dialog | first invalid field, otherwise first logical input |
| result/detail dialog | result collection/critical summary, then primary next action |
| notification center | first unread stable row; otherwise first row; empty state uses Close/recovery |
| error/recovery | readable error summary followed by safe recovery action |
| destructive confirmation | safe `No`/`Cancel` default, never destructive action |
| background update | no focus change |

Focus is applied after the surface is active using deterministic Qt lifecycle callbacks, not a
sleep. A failed route/action does not change current route, selection, history, or focus.

## Return algorithm

On dialog close, modal rejection, nested return, or RM-142 Back:

1. resolve the exact saved logical origin;
2. if it is valid, focus it with the appropriate reason;
3. if a selected row/card disappeared, do not choose a neighbor; focus the owning table/list/status
   container;
4. otherwise use the surface-declared fallback action/input;
5. otherwise use the route-level fallback for the current physical page;
6. otherwise focus the selected sidebar route control;
7. never focus a deleted object, hidden legacy page, disabled destructive action, or unrelated
   first child.

Return does not unexpectedly scroll a different surface. If the current route changed while a
modeless dialog was open, the stale dialog origin is rejected and the current route fallback wins.

## Route contract

| Route family | Entry behavior | Return behavior |
|---|---|---|
| Dashboard/sidebar | activating sidebar retains stable route focus | Back restores exact card/feed/control ID and immutable context |
| global search | `TopBarTenderSearch` -> existing Tenders search owner | failure returns search field; successful nested close returns exact search action/result identity |
| registry/detail | exact `registry` identity; no legacy bridge | RM-149 action token or RM-150 table row; removed row -> registry table/status |
| workflow | route preserves kind/filter/search/record identity | exact record/table action; removed record -> workflow table/status |
| analytics contributor | RM-147 point/contributor identity | same point/contributor; disappeared identity -> chart/table container |
| profile/settings | stable action/field token | same invoking action; invalid field remains focused until corrected/cancelled |
| placeholder/unavailable | do not move focus into placeholder | activating control stays focused; safe reason is exposed |

Mouse, sidebar, shortcut, quick action, deep link, Back, and Return converge on the same registered
destination/handler. No route focus operation starts repository, AI, provider, scoring, or network
work.

## Page-level fallbacks

Stable fallbacks to implement/test are:

| Surface | Fallback |
|---|---|
| Dashboard | refresh or current state recovery action, then Dashboard container proxy |
| Tenders workspace | current tab bar, then unified search input where route contract requests it |
| Workflow | `WorkflowTable`, then first filter/primary action |
| Analytics | preset/date filter group, then first chart/text table |
| Notifications | notification table/status, then Close |
| Dialog | first logical safe control or Close/Cancel |

Fallbacks use unique control IDs. A container with `NoFocus` may expose a focus proxy but cannot be
focused directly.

## Dynamic surfaces

- Empty/loading/partial/error/success replacement reconciles focus after the new state is visible.
- If the focused action remains valid, it stays focused; text/state changes do not steal focus.
- If removed, exact stable identity is attempted, then container fallback; never adjacent row.
- A terminal RM-151 event is announced without focus movement.
- Theme, resize, scale, screen change, sorting, filtering, and chart republish do not change logical
  focus identity.
- Closing a parent invalidates nested origins before child callbacks can restore focus.

## Visible focus

Keyboard focus must use RM-143 `focus_ring` and `BorderWidth.FOCUS` or the native high-contrast
equivalent. It must differ from hover, selected, invalid, and semantic status; remain unclipped in
viewports/tables/charts; and survive dark/light/high-contrast and 100–200% DPI. A static token ratio
is only a regression guard. Actual native visibility is recorded separately.

## Characterization and expected-red

Characterization freezes the accepted RM-142 history/context, Dashboard shortcuts, RM-146 chart
selection, RM-150 exact row selection, and RM-151 focus-invariant updates. Expected-red must prove:

- Dashboard's baseline page-local subcycle;
- an empty Tenders table retaining Tab;
- baseline route restore accepting an invalid/hidden target or falling to an unfocusable page;
- representative credential-dialog return focus is absent;
- removed selection has no deterministic container fallback;
- duplicate/empty control IDs cannot satisfy a stable traversal artifact.

Implementation passes only when forward and reverse traversal, initial focus, exact return, removed
focus fallback, nested dialog close, route Back, and background update invariance are green. Native
physical keyboard/Narrator evidence remains independent.
