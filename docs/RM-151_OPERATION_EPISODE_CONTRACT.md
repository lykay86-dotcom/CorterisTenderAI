# RM-151 operation episode contract

## Ownership and dependency boundary

The shared episode core is immutable, deterministic and Qt-free. It receives owner events and
returns accepted snapshots; it does not start, cancel, retry, wait for, persist or authorize work.
Concrete services/controllers from RM-140 and RM-144 retain lifecycle ownership.

## Typed values

- `OperationEpisodeId`: opaque bounded token generated from injected entropy; it encodes no
  subject, path, error, username, URL or timestamp.
- `OperationKind`: stable catalog value, not localized display text.
- `OperationSubject`: typed namespace/value identity plus separately sanitized optional label.
- `OperationGeneration` and `OperationRevision`: positive monotonic integers.
- `OperationAttempt`: positive integer; retry increments it and creates a new episode ID.
- `OperationReasonCode`: closed shared catalog; boundary-specific context remains allowlisted.
- All timestamps are timezone-aware. Dataclasses are frozen/slotted and contain no QObject or
  mutable list/dict.

## Canonical states

`IDLE`, `QUEUED`, `RUNNING`, `PARTIAL`, `CANCELLING`, `SUCCEEDED`, `FAILED`, `TIMED_OUT`,
`CANCELLED`, `CLOSED` preserve RM-140 queued/cancelling/timeout semantics. `PARTIAL` is terminal
only when useful incomplete output is final; provider progress during a continuing run remains
`RUNNING`.

| From | Accepted targets |
|---|---|
| `IDLE` | `QUEUED`, `RUNNING`, `CLOSED` |
| `QUEUED` | `RUNNING`, `CANCELLING`, `CANCELLED`, `FAILED`, `CLOSED` |
| `RUNNING` | `RUNNING`, `CANCELLING`, `PARTIAL`, `SUCCEEDED`, `FAILED`, `TIMED_OUT`, `CLOSED` |
| `CANCELLING` | `CANCELLED`, `PARTIAL`, `SUCCEEDED`, `FAILED`, `TIMED_OUT`, `CLOSED` |
| result terminal | `CLOSED` |
| `CLOSED` | none |

An identical `(generation, revision, state, payload fingerprint)` event is idempotent. Lower
generation/revision is ignored. Equal revision with different content, invalid transitions and a
second result terminal fail closed with a typed diagnostic reason. A late success cannot replace
confirmed cancellation, timeout, failure or close.

## Episode snapshot

An episode contains ID, kind, subject, state, attempt, generation, revision, progress, aware
started/updated/finished timestamps, optional reason, optional safe summary, optional diagnostic
ID, typed capabilities and optional parent episode ID. Result terminals require `finished_at`;
active states forbid it. `CLOSED` closes presentation and does not claim success/cancellation.

## Progress

Progress mode is `NONE`, `INDETERMINATE` or `BOUNDED`. Bounded progress requires integer
`0 <= current <= total`, a finite `Decimal` percent in `[0, 100]`, and consistent completed,
failed and skipped unit counts. `total=0` is valid only at zero progress. Phase is an allowlisted
catalog value. Progress cannot regress in one phase/generation.

## Capabilities and actions

Capabilities are owner-supplied booleans for cancel, retry, close, open-result and
open-diagnostics plus confirmation requirement and typed disabled reasons. UI never infers them
from text, icon, state colour or exception. Capability does not bypass domain authorization or
freshness checks.

Cancel is an idempotent request to the lifecycle owner: the accepted presentation state becomes
`CANCELLING`, not `CANCELLED`, until owner confirmation. Retry validates subject/input/offline/
authorization again and creates a new episode with parent link and incremented attempt. It never
reopens or mutates the terminal episode.

## Fingerprints and serialization

Semantic fingerprint covers contract version, kind, exact subject identity, state, attempt,
generation, revision, progress, reason, safe summary, diagnostic ID and capabilities in stable
field order. Injected wall time and random episode ID are excluded only from semantic-equivalence
tests, never from stored snapshot equality. Serialization uses closed scalar/list-free DTOs and
rejects unknown versions or enum values.

## Owner mappings

- RM-140 `COMPLETED` maps to `SUCCEEDED`; its `QUEUED`, `CANCELLING`, `TIMED_OUT`, stale
  generation and close behavior remain authoritative.
- RM-144 `OPEN/RUNNING/CLOSING/CLOSED` maps only presentation states; its owned pool/timer shutdown
  is unchanged.
- Existing Dashboard and tender worker signals are adapted at their controller boundary and
  rejected when sender/subject/generation no longer matches.
- Synchronous operations publish a bounded start/terminal sequence only when the UI can render
  start before the call; otherwise they retain synchronous lifecycle and use safe terminal
  feedback without pretending to be background work.

## Expected-red lineage

Tests must fail before production because `app.operations` and its transition API do not exist.
They will exhaustively cover transition pairs, terminal immutability, stale generation/revision,
duplicate idempotency, progress/aware-time invariants, capability validation, retry parentage and
deterministic fingerprints.

