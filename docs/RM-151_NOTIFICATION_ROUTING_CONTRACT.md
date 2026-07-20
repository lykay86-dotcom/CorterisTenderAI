# RM-151 notification routing contract

## Canonical owners

`CollectorNotificationRepository` remains the only persisted in-app notification store and
`TenderCollectorSchedulerUiController` remains its construction/routing owner. The modern top bar,
`Ctrl+Shift+N`, tender menu and toolbar already converge through RM-142 route
`TENDER_NOTIFICATIONS` to the controller's existing `notifications_action`; no message-box stub is
present on the accepted baseline.

RM-151 adds a Qt-free notification envelope/projection and a compatibility adapter over schema-v1
collector notifications. It does not construct another repository or shell router.

## Envelope

An immutable envelope contains notification ID, operation event ID, optional episode/correlation
IDs, closed kind/severity, safe title/summary, optional typed subject, ordered actions, aware
created time, positive revision and optional aware read/dismiss times. It contains no QObject,
callback, raw exception, path, row index, display-only target or credential.

## One routing decision

| Event | In-surface | Status bar | Persistent center | Modal |
|---|---:|---:|---:|---:|
| queued/start | yes | optional | normally no | no |
| progress | yes | coalesced | no | no |
| partial terminal | yes | yes | when user left or action is needed | no |
| success | yes | transient | policy only | no |
| failure | yes | yes | persistent/actionable | blocking decision only |
| cancelled | yes | transient | normally no | no |
| destructive recovery | yes | optional after result | result by policy | confirmation before action |

Generic `QMessageBox` is not a notification transport. Existing blocking confirmations remain with
their action owner.

## Dedupe and revision

Dedupe key is `(event_id, episode_id, terminal_state, revision, subject identity)`, never title or
message alone. Equal revision/fingerprint is idempotent; conflicting equal revision fails closed;
newer revision replaces presentation without clearing read/dismiss. Progress never persists.
Retry creates a new episode/event and is not deduped with its parent. Repository retention remains
capped at 200.

## Read, dismiss and delete

Read means the item was viewed. Dismiss hides it from active presentation but preserves audit/
diagnostic relation. Delete/clear, where retained for compatibility, is a separate confirmed owner
action. Failed open actions keep the item. Bulk operations are bounded/deterministic. Schema-v1
supports only `read` and clear; per-item dismiss persistence is deferred unless an audited schema
decision is approved.

## Actions and exact identity

Each action has typed ID, RM-142 route ID, stable subject identity, freshness token, safe and
accessible labels, confirmation policy, disabled reason and single-shot/idempotency policy.
Before action, the existing domain owner revalidates identity/freshness. Missing/stale targets yield
safe `STALE_TARGET`; no adjacent/current row is selected. Registry actions use RM-149 identity and
RM-150 action/selection contracts.

Initial accepted action catalog:

- open collector run/registry by exact run or registry identity;
- open exact tender detail through existing controller;
- open schedule/profile editor by stable profile ID;
- open crash report center by exact report identity;
- open workflow health/backup center through existing shell action;
- open diagnostics by correlation ID.

No action embeds a filesystem path or external URL. HTTPS external actions, if later required,
need an explicit validated policy and user click.

## Legacy schema adapter

Schema-v1 `CollectorNotification(id, created_at, title, message, kind, read, run_id)` is read without
rewrite. The adapter validates aware time, safe text and derives only the accepted collector-run
subject from non-empty `run_id`; it never guesses a tender/profile/report identity from title/body.
Legacy rows with invalid/unsafe text fail to a generic safe envelope and correlation record.
Ordinary reads do not migrate storage. Any unknown future schema or need for new persisted fields is
a stop condition.

## Dialog and accessibility

The existing dialog becomes an envelope consumer with explicit empty state, stable notification
row identity, accessible title/summary/severity/read state and typed action controls. Opening it
marks items read only according to the explicit controller policy; close/reopen does not duplicate
connections, timers or repositories. Badge count remains a canonical repository query.

## Expected-red lineage

Tests fail before production because envelope/dedupe/action APIs and the compatibility adapter do
not exist. Integration additionally proves topbar/shortcut/menu invoke the same owner, malicious
legacy text is not rendered, duplicate terminal events produce one item, read state survives
duplicate insert and stale action cannot open a neighboring row.

