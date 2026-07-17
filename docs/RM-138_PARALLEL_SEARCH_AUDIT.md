# RM-138 Parallel Tender Search Audit

Date: 2026-07-18
Baseline: `d576f862aab13fa68ea752e479df5c518ff6af42`
Branch: `feat/rm-138-parallel-search`

## Entry gate

RM-138 starts only after the RM-137 feature merge, exact-merge Windows gate, closeout merge,
and the corrective roadmap-summary merge. The accepted evidence is:

- RM-137 feature PR `#81`, merge SHA `e38c8c13f0ec822fde76bdbc6319a18a05fd500b`;
- exact-merge Windows gate run `29615080804`, successful on Python 3.12 and 3.13;
- RM-137 closeout PR `#82`, merge SHA `fd7418540c2baac8979e0af96e3bbb2f8391c403`;
- roadmap-summary correction PR `#83`, merge SHA
  `d576f862aab13fa68ea752e479df5c518ff6af42`;
- post-merge Windows gate run `29617118615`, successful on Python 3.12 and 3.13;
- local Windows baseline at `d576f862...`: `1879 passed, 2 warnings in 146.83s`.

Canonical roadmap documents identify RM-138 as the only active stage. No RM-139 implementation
is in scope until RM-138 satisfies the Definition of Done.

## Audited ownership map

| Concern | Existing owner | Finding | RM-138 decision |
| --- | --- | --- | --- |
| Production provider execution | `collector/async_engine.py::AsyncProviderSearchEngine` | Bounded async execution already exists and is the production path selected by RM-126. | Extend this coordinator in place. Do not add another engine. |
| Legacy synchronous API | `search_engine.py::TenderSearchEngine` | Public sync API uses a thread pool and has legacy merge/dedup logic. A timed-out running thread cannot be force-stopped. | Preserve its public API and behavior as a compatibility facade; do not expand it into a competing production pipeline. |
| Run composition/admission | `collector/run_session.py::CollectorRunSession` and `collector/provider_settings.py` | Settings are snapshotted once per run; corrupt/future settings fail closed; manual providers require verified admission. | Keep this as the only admission boundary. No RM-138 bypass. |
| Provider construction | `collector/async_provider_factory.py` | EIS and Moscow have native async adapters; optional commercial/manual adapters follow existing lifecycle rules. | Reuse the factory and per-run network runtime. |
| Cooperative cancellation | `collector/cancellation.py::CollectorCancellationToken` | Thread-safe, idempotent cancellation and interruptible async sleep already exist. | Reuse and make terminal publication authoritative. |
| HTTP timeout/retry | `collector/async_http.py::AsyncHttpClient` | Bounded transient-only retry, Retry-After handling, cancellation-aware backoff, and per-request timeouts already exist. | HTTP transport remains the sole retry owner. The coordinator must not double-retry. |
| Normalization | RM-137 `collector/normalizer.py::TenderNormalizer` | Canonical normalization owner is already accepted. | Normalize through this owner exactly once for the canonical batch/partial accumulator. |
| Deduplication | RM-137 `collector/deduplicator.py::TenderDeduplicator` | Canonical deterministic alias-aware merge already exists. | Reuse it for final and partial results. The legacy sync dedup is not a new production owner. |
| Business pipeline | `collector/collector_service.py::CollectorService` | Discovery, verification, freshness, deterministic ranking/stop factors, and persistence occur after provider collection. | Preserve ordering and deterministic decision authority. AI must not override score/recommendation/critical stop factors. |
| Persistence | `collector/store.py::CollectorStateRepository` | Existing run/provider outcome columns can retain typed safe failures without a schema change. | Reuse current schema; persist only safe error category/code/message. |
| UI worker | `_CollectorRunWorker` in `ui/tender_search_ui_controller.py` | `asyncio.run(session.run(...))` executes in `QThreadPool`; the UI thread is not blocked. | Keep one worker and one cancellation token per run. |
| UI presentation | Collector dialog and unified panel | Current widgets derive percentages from phases and completed counts; partial tenders are not exposed before terminal completion. | Consume immutable engine snapshots and partial items; remove UI business calculations. |
| Legacy profile UI | `_TenderSearchWorker` / `TenderSearchProfileRunner` | Older profile screens still invoke the synchronous compatibility path. | Preserve compatibility in RM-138; do not silently change saved-profile semantics. Migration remains explicit follow-up work. |

## Execution audit

The production coordinator already sorts selected providers by descriptor priority, normalized
name, and provider id; uses `asyncio.Semaphore` for bounded concurrency; emits queued/running/
completed phases; isolates provider failures; and returns completed provider results when another
provider fails or the run is cancelled.

The following RM-138 gaps remain:

1. There is no immutable run snapshot with a run id, monotonic revision, exact provider states,
   total/completed counters, and engine-owned percent.
2. There is no overall monotonic run deadline in addition to provider/request deadlines.
3. A slow async progress subscriber is awaited inline and can delay provider execution.
4. Normalization/dedup currently begins only after all provider tasks terminate, so no canonical
   partial results are published.
5. Raw exception text can cross the provider outcome, persistence, or UI boundary.
6. Terminal cancellation must explicitly reject all late provider results and post-terminal events.
7. Cancellation latency and executor shutdown need measurable contracts.
8. Retry attempts owned by the HTTP layer are not represented in the lifecycle snapshot.

## Concurrency and cancellation limits

Native async providers cooperate with cancellation because request waits, timeout handling, and
retry sleeps are awaitable. `LegacySyncProviderAdapter` uses `asyncio.to_thread`; Python cannot
safely terminate a third-party blocking thread that has already entered provider code. RM-138
therefore guarantees:

- prompt terminal cancellation of the coordinator;
- no acceptance or publication of a result that arrives after the terminal snapshot;
- no additional provider dispatch after cancellation/deadline;
- bounded wait during coordinator shutdown;
- explicit documentation that the underlying legacy thread may finish privately later.

The same physical limitation exists in the synchronous compatibility engine. It is not disguised
as a successful hard kill.

## Retry decision

`AsyncHttpClient` is the single retry layer. It retries only classified transient transport/status
failures, respects bounded attempts and delay, clamps `Retry-After`, and makes backoff cancellable.
The provider coordinator performs one logical provider invocation and never retries it. This avoids
multiplying attempts (for example, 3 transport attempts times 3 coordinator attempts).

Lifecycle snapshots may report the safe attempt count carried by a typed transport error. They do
not expose URLs, credentials, response bodies, or raw exception strings.

## Determinism decision

Completion order must not affect observable data. Every snapshot uses the immutable run provider
order. Partial canonical items are recomputed from the accepted completed-provider prefix set and
sorted by the RM-137 canonical dedup result order. Final provider outcomes and tenders are likewise
ordered independently of task completion timing.

Provider priority may break an already-approved deterministic merge tie; it must not alter score,
recommendation, or critical stop-factor priority. AI output remains downstream evidence only.

## Security boundary

All exception-to-contract conversion occurs before progress, persistence, or UI publication.
Allowed public fields are a stable category, stable code, provider id, attempt count, and fixed safe
message. Raw exception text remains available only to local structured logging where existing
logging policy permits it. Tokens, credentials, query strings, arbitrary URLs, response bodies,
and traceback text are forbidden in public/persisted search outcomes.

## Scope conclusion

RM-138 is an in-place extension of the accepted asynchronous Collector execution owner, with the
existing synchronous `TenderSearchEngine` retained as a compatibility facade. It introduces no
second provider registry, provider model, normalizer, deduplicator, repository, database, scoring
engine, or retry loop.
