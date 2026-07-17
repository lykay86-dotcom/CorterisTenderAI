# RM-138 Parallel Search Contract

Contract version: 1  
Status: implementation target

## Boundary

The contract applies to the production Collector search run created by `CollectorRunSession` and
executed by the existing asynchronous provider coordinator. The synchronous
`TenderSearchEngine.search(...)` API remains source-compatible for legacy callers.

## Run identity and time

- Each run has one opaque non-empty `run_id` generated before provider dispatch.
- Wall-clock timestamps are timezone-aware UTC.
- Timeout/deadline arithmetic uses a monotonic clock only.
- Each published snapshot has an integer `revision`, starting at zero or one and increasing by
  exactly one for every accepted state change.
- A snapshot is immutable after publication.

## Run lifecycle

The run states are:

`queued -> running -> {completed | partial | failed | timed_out | cancelled}`

Terminal states are final. No provider result, partial item, counter change, or progress event may
be accepted after a terminal snapshot has been published.

`partial` means at least one usable canonical tender was retained while at least one selected
provider ended unsuccessfully. `completed` permits successful empty providers. `failed` means no
usable result survived and the run did not terminate by cancellation or overall timeout.

## Provider lifecycle

Every admitted provider appears exactly once in every snapshot, in immutable deterministic order.
The provider states are:

`queued -> running -> {success | empty | not_configured | unsupported | failed | timed_out |
cancelled | skipped | circuit_open}`

An optional retry presentation state is allowed only for transport retry telemetry:

`running -> retry_wait -> running`

The coordinator itself must not repeat the logical provider invocation. HTTP transport owns retry.
Provider terminal states are immutable.

For every snapshot:

- `total == len(providers)`;
- `completed == count(provider.terminal is true)`;
- `0 <= completed <= total`;
- queued and running counts are derived from exact provider states;
- percent is engine-owned, bounded to `0..100`, monotonic, and equals `100` only in a terminal run
  state;
- no UI code may recompute business progress from phases or counters.

## Admission and selection

- Provider settings are loaded and frozen once at run start.
- Corrupt or unsupported-future settings fail closed.
- Disabled providers are not runnable through the production run path.
- Manual providers remain unavailable until the existing verification lifecycle admits them.
- Duplicate aliases resolve to one canonical provider id.
- Provider order is descriptor priority, normalized display name, then provider id.
- A provider added or enabled after the run snapshot is created cannot join that run.

## Parallelism and deadlines

- Concurrency is bounded by the configured positive `max_concurrency`.
- At most `max_concurrency` provider calls may be in `running` simultaneously.
- Queued providers do not acquire provider/request resources.
- Each provider call has a positive provider timeout.
- The whole run has a positive overall timeout/deadline.
- Provider and overall timeout decisions use monotonic time.
- Overall timeout prevents new dispatch, cancels cooperative work, retains accepted completed
  results, and publishes one `timed_out` terminal snapshot.

## Cancellation

- Cancellation is cooperative, thread-safe, and idempotent.
- The first cancellation request prevents new provider dispatch.
- Awaitable provider I/O and retry backoff observe the token promptly.
- Completed results accepted before cancellation are retained.
- Results that finish after the terminal cancellation boundary are discarded.
- Exactly one terminal cancellation snapshot is published.
- Cancellation latency is measured from token transition to terminal snapshot and is covered by a
  deterministic test with a bounded tolerance.
- A blocking legacy sync adapter may finish its private worker thread later; that late result is
  never surfaced as accepted run output.

## Error contract

Public provider/run failures contain only:

- typed category;
- stable code;
- fixed safe message;
- optional safe HTTP status;
- bounded positive attempt count;
- retryable flag.

Categories are at least `configuration`, `authentication`, `authorization`, `rate_limit`,
`timeout`, `network`, `remote_service`, `cancelled`, `protocol`, and `internal`.

Raw `str(exception)`, traceback text, credentials, secrets, tokens, response bodies, and URLs with
query/fragment/user-info are forbidden in progress events, returned outcomes, persisted run state,
and UI messages. Unknown exceptions map to a fixed internal-error code/message.

## Retry contract

- `AsyncHttpClient` is the only retry owner.
- Retry is limited to its typed transient transport failures and configured transient status codes.
- Authentication, authorization, validation, cancellation, and permanent protocol failures are not
  retried.
- Attempts, delay, and `Retry-After` are bounded.
- Backoff sleep is cancellation-aware.
- The coordinator performs one logical provider invocation and cannot multiply transport attempts.
- A successful first attempt performs no sleep.

## Partial results

- After each accepted provider completion, the engine may publish an immutable partial snapshot.
- Partial tenders have already passed the canonical RM-137 normalizer and
  `TenderDeduplicator`.
- Invalid individual provider items are isolated and represented through typed safe diagnostics;
  they do not corrupt accepted valid items from that or another provider.
- The same accepted raw set produces byte-for-byte-equivalent canonical identities and ordering,
  regardless of provider completion schedule.
- The final Collector pipeline consumes the same canonical batch; it must not introduce a second
  normalization/dedup implementation.
- UI may render partial items but may not rank, deduplicate, normalize, score, or change business
  recommendations.

## Progress delivery

- Providers publish state to the engine; they do not call Qt or UI objects.
- The engine publishes immutable snapshots through one bounded dispatcher.
- A slow or failing subscriber cannot hold a provider semaphore slot or stop provider execution.
- Subscriber delivery preserves snapshot revision order.
- Queue overflow coalesces obsolete nonterminal snapshots while retaining the newest state and the
  terminal snapshot.
- The dispatcher is drained or closed within a bounded time at run termination.

## Deterministic merge and business authority

- Provider outcomes use immutable provider order, never completion order.
- Canonical tender output uses RM-137 deterministic identity, representative selection, provenance,
  and ordering rules.
- Provider priority is only an approved deterministic tie-break input.
- Search parallelism cannot modify approved score, recommendation, ranking, or critical stop-factor
  priority.
- AI output cannot override deterministic decision logic.

## Persistence and compatibility

- Existing repositories and schema remain the persistence authority; RM-138 adds no database.
- Safe typed error values replace arbitrary exception messages in persisted provider/run outcomes.
- Legacy sync imports, constructor defaults, `search(...)` parameters, and result properties remain
  compatible.
- Existing saved profiles and provider ids remain readable.
- New fields use defaults where required to keep existing test doubles and integrations viable.

## Acceptance properties

The implementation is complete only when tests prove bounded concurrency, queued/running truth,
overall and provider deadlines, cancellation idempotence and latency, late-result rejection,
partial success, safe errors, no double retry, schedule-independent output, slow-subscriber
isolation, UI thread non-blocking behavior, sync compatibility, clean executor/dispatcher shutdown,
and unchanged deterministic decision authority.
