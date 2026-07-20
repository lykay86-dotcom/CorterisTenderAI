# RM-152 keyboard interaction contract

Baseline: `9cb37b9a83f50ac9f8f8e34fdeb582c2ed76e257`

## Ownership boundary

Qt native controls retain their native key behavior. RM-142 remains the route/shortcut owner,
RM-146 the interactive-chart owner, RM-150 the table identity/action owner, RM-151 the operation
capability owner, and each dialog/controller remains the only domain-action owner. RM-152 may make
an existing action reachable and understandable; it cannot infer eligibility, create a second
shortcut, bypass confirmation, retarget a row, or alter RM-107 decisions.

No application-wide key event filter is permitted. A bounded control may override a key only when
the behavior is listed here and a test proves pointer/key action parity.

## Canonical control behavior

| Control | Required keys and result |
|---|---|
| button/tool button/card/tile | Tab/Shift+Tab traverse; Space activates; Enter activates only for the accepted component contract; disabled does nothing |
| checkbox/toggle | Space toggles; checkable tool buttons expose checked state; group arrows only for native group semantics |
| radio group | Tab enters/leaves one group stop; arrows select within the group |
| line/plain/rich edit | native text selection and `Ctrl+A/C/V`; Enter submits only when the visible action contract says so; Escape never discards implicitly |
| password/credential edit | same input behavior, but saved/current secret is never populated, copied, named, described, or announced |
| combo | arrows/Home/End/type search; Escape closes popup before parent; selection does not execute a separate destructive action |
| date/spin editor | native subcontrol/section traversal is bounded; tests allow same QWidget focus while the active section advances, then require exit |
| tabs | arrows/Home/End change tab; Tab enters current page; hidden pages are not focus stops |
| table/list/tree | native arrows/Home/End/PgUp/PgDn; selection resolves exact RM-150 identity; Enter invokes one documented primary action; context actions are keyboard reachable |
| menu | arrows navigate; Enter/Space activates enabled item; Escape closes menu before dialog/window |
| notification row | arrows or Tab reach row/action; Enter uses typed subject; Escape closes the center, not the application |
| chart canvas | exact RM-146 arrows/Home/End/Ctrl variants, Enter/Space, Escape, F2; textual equivalent remains reachable |
| dialog | bounded Tab chain; safe default; Escape rejects/closes by policy; Alt+F4 equals close/X policy |

`QTableWidget`/`QTableView` must not consume an unbounded number of Tabs to cross every cell. Cell
navigation uses arrows. A table is one task-flow Tab stop unless an explicitly editable site needs
a documented editor sequence. When selected identity disappears, focus returns to the table/status
container without selecting a neighbor.

## Shell and route order

The stable high-level order is:

1. primary sidebar routes in registry order;
2. top-bar global search, AI, notifications, theme, profile;
3. current page primary/meaningful input;
4. current page content and contextual actions in visual task order;
5. status/footer controls;
6. return to the first shell control.

Only the current physical page participates. A route opened by shortcut must focus the invoked
task, while mouse and shortcut dispatch the same existing action. A page may define its internal
chain, but it must not create a subcycle. Dynamic empty/loading/partial/error/success replacement
must reconnect predecessor and successor.

## Existing shortcut catalog

| Binding | Owner | Destination/action | Context rule |
|---|---|---|---|
| `Ctrl+Shift+F` | tender controller action | profiles/search | same action in menu/toolbar; no duplicate dialog |
| `Ctrl+Shift+R` | tender controller action | registry | exact existing registry owner |
| `Ctrl+Shift+S` | tender controller action | providers | never reads a credential |
| `Ctrl+Shift+C` | tender controller action | collector | RM-140 admission/lifecycle applies |
| `Ctrl+Shift+P` | scheduler controller | scheduler | existing owner and schedule identity |
| `Ctrl+Shift+N` | scheduler controller | notifications | identical target/focus as top-bar action |
| `Ctrl+F` | Dashboard shortcut manager | tender search | only inside Dashboard descendants |
| `Ctrl+A/K/S/R` | Dashboard shortcut manager | advisor/quick/status/refresh actions | only visible/enabled accepted owner acts |
| `Alt+1`–`Alt+5` | Dashboard shortcut manager | bounded quick-action catalog | key and tile emit same stable action key |
| `Esc` | Dashboard shortcut manager | dismiss Dashboard status | cannot close app or confirm another surface |

The baseline runtime inventory found no duplicate sequence. Tests must reject newly duplicated
effective bindings and object-less shortcut definitions. Standard edit shortcuts cannot be
shadowed when an editor owns focus.

## Journey keyboard matrix

| Journey | Required keyboard path |
|---|---|
| J01 | launch, enter Dashboard, traverse shell/page, reach safe empty recovery |
| J02 | open safe mode/crash center, read summary, choose recovery/exit, Escape/Alt+F4 follow policy |
| J03 | feed arrows/select/Enter, open exact tender, Back returns to same stable feed/card origin |
| J04 | top search focus, type, Enter explicit submit, route focus lands in search task |
| J05 | `Ctrl+Shift+F`, labels/fields/sources, first-invalid focus, Save/Cancel |
| J06 | `Ctrl+Shift+S`, provider selection, credential input, replace/delete confirmation with safe default |
| J07 | start, progress without focus steal, cancel request vs confirmed cancel, retry creates new attempt |
| J08 | `Ctrl+Shift+P/N`, scheduler/notification traversal and exact typed action |
| J09 | registry table to documents/requirements/full analysis/score and stable nested return |
| J10 | AI settings/recheck with disabled/offline reason and no secret readback |
| J11 | verification evidence, conflict action, cancel/resolve, critical warning first |
| J12 | workflow filter/table/create/edit/history/import/export/archive/restore by exact identity |
| J13 | data menu, backup/health/import/recovery, safe confirmation and stable return |
| J14 | theme button announces current/next state; Space/Enter invokes one toggle |
| J15 | damaged/future schema summary, safe recovery/exit; no destructive default |
| J16 | Alt+F4/close during idle/running/terminal uses RM-144/RM-140 close policy |

## Automated traversal artifact

The test harness records for each stop only stable values:

```text
surface_id, route_id, control_id, class/role, name, enabled, visible,
focus_policy, logical subject/row identity, forward index, reverse index
```

It constructs synthetic surfaces with temporary settings/data and blocked network/keyring. It
sends Tab/Shift+Tab with Qt test APIs, allows a documented bounded native composite to retain the
same QWidget temporarily, and fails on:

- an unreachable required control;
- a hidden, disabled, deleted, or `NoFocus` target;
- a page-local cycle before shell exit;
- inconsistent forward/reverse membership;
- a duplicate unstable control ID;
- a keyboard action whose typed identity differs from pointer activation;
- an action during a state where the owner reports it unavailable.

No arbitrary sleep, memory address, localized display string as identity, or current row index is
permitted. Offscreen traversal is not physical-keyboard acceptance.

## Destructive and lifecycle rules

- Escape never accepts archive/delete/restore/import/recovery/credential deletion.
- A destructive button is never auto/default; `No` or `Cancel` is the confirmation default.
- Enter in a table/editor cannot bypass exact target/revision/fingerprint revalidation.
- Repeated submit while an RM-151 episode is active is rejected by owner capability.
- Cancel requests `CANCELLING`; keyboard feedback cannot claim `CANCELLED` before owner terminal.
- Background progress, terminal notification, refresh, and table update never steal focus.
- Alt+F4 uses the same unsaved/busy/shutdown result as close/X and the visible close action.

## Acceptance evidence

Automated evidence covers mappings, traversal, parity, and state guards. Native evidence separately
records physical keyboard behavior for every J01–J16 path in the required DPI/theme cells. A cell
that is blocked or not run remains `BLOCKED`/`NOT_EXECUTED`, never PASS.
