# RM-144 workflow health lifecycle contract

## States and transitions

`SystemHealthMonitor` exposes an immutable typed lifecycle snapshot or equivalent observable
state with terminal semantics:

```text
OPEN --request_refresh--> RUNNING
RUNNING --job finished--> OPEN
OPEN/RUNNING --shutdown--> CLOSING --owned job drained--> CLOSED
CLOSED --shutdown--> CLOSED
```

`RUNNING` may be represented as an activity flag alongside an `OPEN` lifecycle state, provided the
combination is unambiguous. `CLOSING` begins before sources are stopped or disconnected. No path
returns from `CLOSING`/`CLOSED` to open.

## Allowed methods and request semantics

| Operation | OPEN idle | OPEN running | CLOSING/CLOSED |
|---|---|---|---|
| `request_refresh()` | starts one job, returns `True` | no duplicate, returns `False` | rejects, returns `False` |
| read `last_snapshot`/state | allowed | allowed | allowed |
| `shutdown(timeout_ms)` | closes | bounded close of owned job | stable repeated terminal outcome |

Negative timeouts fail before lifecycle mutation. A collector exception is converted to one health
failure signal while open; it never escapes the Qt event loop and never changes workflow data.
Health collection remains offline by contract.

## Worker ownership, generation, and delivery

Each monitor owns a dedicated injected-or-created `QThreadPool` used only for its health jobs. An
injected pool is not globally drained or destroyed by the monitor unless ownership is explicit.
The default must not be `QThreadPool.globalInstance()`.

Every accepted request receives a monotonically increasing generation. Only the current generation
may update `last_snapshot`, publish snapshot/failure, or publish busy completion. The monitor keeps
a strong reference to the running worker and its signal source until that exact worker finishes or
is safely removed before start. Close first disables page-facing publication and future requests,
then drains only the monitor-owned job within the supplied fixed budget. A late result during
`CLOSING` is ignored; it cannot call a page/widget slot. Reference cleanup and terminal transition
happen once.

The design does not use `terminate()`, a busy loop, `sleep()`, infinite `waitForDone()`, or a wait on
the global pool. Cooperative cancellation may suppress unnecessary collector work only where the
collector can safely honor it; lifecycle safety must not depend on forcibly stopping arbitrary
Python/DB code.

## Timer and page lifecycle policy

`BusinessWorkflowPage` owns a separate `OPEN -> CLOSING -> CLOSED` terminal lifecycle and an
idempotent `shutdown()`:

1. mark closing;
2. stop `_auto_backup_timer` and `_system_health_timer`;
3. disconnect `workflow_changed` scheduling connections where needed;
4. make startup database-safety and health callbacks lifecycle-guarded so pending single-shots are
   no-ops;
5. prevent health/result/error UI slots from publishing after close begins;
6. close `SystemHealthMonitor` under its bounded contract;
7. mark closed and return the same safe terminal outcome on repeated calls.

The page does not run backup, recovery, import, dialogs, or repository writes during shutdown.
QObject destruction without shell coordination still invokes fail-safe guards, but a destructor is
not the primary owner and never blocks unpredictably.

## Shell bounded-close behavior

Tender search retains the RM-140 preflight/veto position. Only after it accepts close does the shell
disable navigation and invoke workflow then Dashboard shutdown. The workflow monitor budget is
explicit and finite. If an owned health collector cannot finish inside the budget, close returns a
stable failure/veto while the signal source remains retained and delivery stays detached; it is not
deleted underneath the worker. Repeating shutdown continues toward the same terminal state without
starting new work.

Successful close guarantees: timers inactive, refresh rejected, no page-facing late result,
worker/signal source safely completed and released, state `CLOSED`, and no Qt deleted-source,
deleted-receiver, or running-thread warning.

## Error and signal policy

- `busy_changed(True)` is emitted once per accepted generation while open.
- Snapshot or failure is emitted at most once for that generation and only while delivery is open.
- `busy_changed(False)` is emitted only to live/open page-facing receivers; internal state still
  settles if delivery is closed.
- Disconnect races and already-deleted Qt wrappers are handled as safe terminal cleanup, not raw
  errors shown to the user.
- Health failure does not alter workflow records, backup policy, score, recommendation, or
  stop-factor priority.

## Expected-red and evidence plan

Expected-red contracts, added only after characterization, will prove the missing baseline behavior:

- public lifecycle states and refresh rejection after closing/closed;
- duplicate refresh and collector-exception behavior remain stable;
- idempotent monitor shutdown before, during, and after work;
- bounded owned-pool close without global pool waiting or foreign-job interference;
- generation suppression and no snapshot/failure/busy signal after close;
- page shutdown stops both owned timers and guards both pending startup callbacks;
- repeated page/shell shutdown and RM-140 search veto ordering;
- rapid offscreen construct/refresh/close/delete emits no `Signal source has been deleted`, QObject,
  or running-thread warning and leaves no timer/worker growth.

Evidence runs on Windows with `QT_QPA_PLATFORM=offscreen`, temporary repositories, fake blocking or
manually controlled collectors/pools, Qt event-loop deadlines rather than sleeps, and a socket
tripwire. Repeated counts are taken before/after event processing and deletion.
