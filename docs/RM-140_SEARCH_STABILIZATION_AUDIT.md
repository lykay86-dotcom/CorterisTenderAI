# RM-140 — аудит стабилизации универсального поиска

Дата аудита: 18 июля 2026 года  
Baseline SHA: `f14ba84d754a4c84f1173812731e36ec274200f4`  
Ветка: `feat/rm-140-search-stabilization`  
Статус: audit завершён до изменения application-кода и тестов.

## 1. Entry gate и baseline

RM-139 закрыт полностью до старта RM-140:

- feature PR #86 merged как `41b547f67020b9645d915694c943b962b46ddc08`;
- feature merge gate: Actions run `29624355650`, Python 3.12/3.13 успешны;
- docs-only closeout PR #87 merged как baseline SHA `f14ba84...`;
- exact closeout gate: Actions run `29624885521`, Python 3.12/3.13 и dependency audit успешны;
- `origin/main`, local `main` и новый worktree начинались на одном SHA;
- root worktree содержит только пользовательские untracked `.agents/` и `skills-lock.json`; они не
  переносились и не изменялись.

Изолированный worktree: `.worktrees/rm140`. Baseline full suite после создания repository-local
`.tmp`:

```text
1908 passed, 2 warnings in 110.22s
```

Первый запуск с отсутствующим parent каталога `--basetemp .tmp/...` дал fixture-level
`FileNotFoundError` до выполнения кода. После создания gitignored `.tmp` тот же SHA прошёл.
Workflow-derived baseline также прошёл secret scan, Ruff check, Ruff format (`620 files already
formatted`), mypy (`20 source files`), offline smoke (`2 passed`), migration (`5 passed`), import,
composition (`1 passed`) и build/release (`6 passed`). Local `pip-audit` после явного разрешения
пользователя всё равно был запрещён tenant policy для обращения к PyPI; fallback evidence —
успешный dependency-audit job run `29624885521` на точно том же SHA.

## 2. Подтверждённые владельцы

| Область | Фактический owner | Вывод RM-140 |
| --- | --- | --- |
| Async run/network | `CollectorRunSession` | Fresh runtime на run и `finally: await runtime.aclose()` уже каноничны. |
| Parallel lifecycle | `AsyncProviderSearchEngine` + `_SearchLifecycle` | Bounded concurrency, monotonic elapsed/deadline, ordered terminal snapshot и bounded progress уже существуют. |
| Pipeline | `CollectorService` | Единственный canonical normalize/dedup/verify/freshness/rank/persist owner. |
| Admission/UI | `TenderSearchUiController._try_start_collector_query` | Unified panel, Collector dialog и scheduler уже используют один `_collector_worker`; saved profile обходит owner. |
| Scheduler | `TenderCollectorSchedulerUiController` | Existing `QTimer` и busy callback; shutdown API отсутствует. |
| Provider state/monitoring | `CollectorProviderManager` + RM-139 projection | Переиспользовать; passive monitoring не выполняет network. |
| History | `CollectorStateRepository` / Collector schema v14 | `collector_runs` — target writer; legacy run tables требуют retention boundary. |
| Tender registry | `TenderRegistryRepository` | `tender_records` и legacy occurrence readers должны остаться читаемыми. |
| Normalization/dedup | RM-137 `TenderNormalizer` / `TenderDeduplicator` | Не создавать второй boundary и не повторять merge в UI/facade. |
| Public errors | `classify_search_error` + async outcome | Closed safe mapping есть, но health и `error_type` ещё принимают raw exception class/text. |
| App lifecycle | `TenderSearchUiController` under `ModernMainWindow` | Это ожидаемый application owner, но shell сейчас вызывает shutdown только dashboard. |
| Decision authority | RM-107 deterministic services | Не изменять score/recommendation/critical stop-factor; AI остаётся advisory. |

Новый engine, repository, history DB, scheduler, monitor, credential vault, normalizer или provider
catalog не требуется.

## 3. Search entry points и consumer map

| Entry point | Current route | Network/history/cancel/close | Class | Решение |
| --- | --- | --- | --- | --- |
| Unified panel | UI → `_try_start_collector_query` → `_CollectorRunWorker` → `CollectorRunSession` | async; `collector_runs`; cooperative cancel; no app shutdown | production | reuse |
| Direct Collector action | тот же `_try_start_collector_query` | как выше | production | reuse |
| Scheduled run/startup opt-in | scheduler callback → `try_start_collector` → тот же worker | как выше; timer survives close path | production | reuse + stop timer |
| Saved profile dialog | `run_profile` → `_TenderSearchWorker` → `TenderSearchProfileRunner` | sync; `tender_search_runs`; no cancel; global pool | production duplicate | migrate to canonical admission |
| Legacy result rerun | result dialog → `run_profile` | тот же legacy route | production only after legacy result | retire production creation |
| Legacy sync API | `TenderSearchEngine`, service, runner public exports | own executor, normalize/dedup/history | tests/external compatibility unknown | retain deprecated compatibility-only API, no production composition |
| Bootstrap | `create_tender_search_runtime` builds legacy graph and UI also builds Collector session | composes two engines offline | production duplicate | stop composing legacy engine/service/runner |
| Provider connection check | separate `_ProviderCheckWorker` | explicit network, cancel token, busy guard; no close owner | operations, not search run | cancel/wait via tender controller shutdown |
| Passive RM-139 monitoring | read-only projection/history hydration | no network and no live run | production | unchanged |
| Registry/history UI | legacy occurrences/statistics plus canonical tender records | local SQLite only | production compatibility reader | retain old rows; do not write new legacy runs |
| Tests/scripts/public imports | direct legacy constructors and `app.tenders` exports | test-controlled | compatibility | keep imports/signatures during rollback window |
| Frozen import/self-test | imports application graph; no search call | offline | release | preserve |
| Support bundle | business DB summaries + redacted logs; no tender SQLite payload | may include application logs | support | ensure search never logs raw exception; existing redactor remains defense-in-depth |

Direct code search found no production consumer of `TenderSearchEngine` outside
`create_tender_search_runtime` and saved-profile UI. Public exports and direct tests prove that
physical deletion is premature; compatibility implementation stays, but cannot be composed by
bootstrap or called by a production UI entry point.

## 4. Current lifecycle and ownership gaps

Canonical run today:

```text
UI/scheduler -> controller admission -> global QThreadPool QRunnable
 -> asyncio.run -> CollectorRunSession -> fresh network runtime
 -> CollectorService/AsyncProviderSearchEngine -> persistence
 -> finally runtime.aclose -> Qt result signal
```

Positive evidence:

- one `_collector_worker` rejects manual/scheduled overlap;
- async provider tasks are bounded by `max_concurrent_providers`;
- cancellation/timeout cancels outstanding tasks and rejects provider completion after terminal
  `_SearchLifecycle` state;
- progress uses a bounded queue of 64 and a 0.2 s dispatcher close timeout;
- network runtime closes in `finally` on success/failure/cancel.

Gaps:

- controller has no typed application-level `IDLE/QUEUED/RUNNING/CANCELLING/terminal` snapshot;
- default pool is `QThreadPool.globalInstance()`, so worker ownership and bounded join are unclear;
- scheduler timer has no idempotent stop/shutdown method;
- provider-check and Collector tokens are not cancelled by window close;
- `ModernMainWindow.closeEvent()` invokes only `dashboard_controller.shutdown()`;
- bootstrap does not call tender shutdown after the event loop;
- signal slots accept late results without an application terminal-generation guard;
- saved-profile QRunnable has no cancellation token and legacy nested threads can continue after
  `executor.shutdown(wait=False, cancel_futures=True)`;
- `CollectorStateRepository` and `TenderRegistryRepository` use `with sqlite3.Connection`, which
  commits/rolls back but does not close the Windows file handle. The audit benchmark reproduced a
  locked temp DB during immediate cleanup.

## 5. Clock and timestamp map

| Boundary | Current clock | Finding |
| --- | --- | --- |
| Async batch `started_at/completed_at` | `datetime.now(timezone.utc)` | aware UTC, accepted |
| Async elapsed/provider timeout | `perf_counter()` / `asyncio.timeout()` | monotonic, accepted |
| RM-138 progress snapshot | aware UTC validator | accepted |
| Collector store defaults | aware UTC string | accepted, but caller-supplied strings are not validated |
| Health cooldown/rate limits | injected `monotonic` | accepted |
| Health snapshot wall clock | injected aware `utcnow` by default | accepted; validate custom clock |
| RM-137 normalization | aware → UTC; naive rejected with diagnostic | accepted |
| Freshness | explicit/source-zone/unknown model | accepted; no region guessing |
| Legacy `TenderSearchEngine` | naive `datetime.now()` | unsafe but will be compatibility-only; fix public result serialization |
| Legacy registry `_iso_timestamp` | silently `replace(tzinfo=UTC)` for naive input | unsafe; reject new naive values |
| Existing legacy DB rows | arbitrary historical strings | preserve raw; classify naive as `UNKNOWN`, never rewrite as UTC |

Durations remain monotonic. Wall clock is used only for user/audit timestamps. Active persistence
must reject malformed/naive run times. Existing legacy naive data is read without mutation and
explicitly classified unknown.

## 6. Error flow and security/privacy findings

Canonical safe path is provider exception → `classify_search_error` → async outcome →
`CollectorStateRepository.complete_run` → UI/source monitoring. Known HTTP/cancel/timeout and
unknown exceptions already map to fixed Russian messages and stable codes.

Confirmed leaks/gaps inside the RM-140 contour:

- async outcomes still set `error_type=type(error).__name__`;
- `ProviderHealthMonitor.register_failure` persists `type(error).__name__` and `str(error)`;
- `register_not_configured` accepts raw message;
- legacy engine/profile worker/runner store or render raw type/text;
- timeout override embeds only a numeric code-owned timeout and is safe, but should use the same
  closed failure value;
- Qt Collector failure renders a code plus safe message; the code must be bounded and allowlisted;
- support bundle does not include tender SQLite, but includes logs after redaction, so no search
  logger may receive the sentinel in the first place.

The target boundary will expose stable category/code/message/provider/retryable/terminal and aware
event time through the existing outcome/batch context. Unknown exception class, message, nested
cause, URL user-info/query/fragment, body, headers, local path and credential backend text are
discarded before health, persistence, UI or logging.

## 7. History schema and compatibility decision

### Canonical Collector history

- owner/version: `CollectorSchemaMigrator`, schema v14;
- `collector_runs(run_id PK, status, aware started/completed, query_json, requested providers,
  counts, elapsed, safe run error)`;
- `collector_run_providers((run_id, provider_id) PK, status/count/elapsed/warnings/safe error)`, FK
  to `collector_runs` with cascade;
- `collector_run_items((run_id, registry_key) PK, observation/content/source/duplicate)`, FKs to
  `collector_runs` and `tender_records` with cascade;
- indexes cover run time/status, run-item registry lookup and downstream change/version/score
  joins;
- semantics include running/completed/partial/cancelled/failed.

### Legacy history

- owner/version: `TenderRegistryRepository`, registry schema v1;
- `tender_search_runs` stores profile identity, counts, elapsed and JSON provider outcomes, but no
  run status/cancel semantics and historical timezone is not guaranteed;
- `tender_search_run_items` links legacy run to `tender_records`; index supports occurrence lookup;
- readers: registry metric, occurrence UI, public list/count methods and tests;
- only writer: `TenderSearchProfileRunner.record_profile_run`.

### Decision: no DB migration

Schema does not change. After saved-profile routing and bootstrap retirement, all new production
runs write only `collector_runs`; there is no double write. Legacy tables and public repository
methods remain intact for a rollback/retention window and existing user data, with naive time
reported as unknown. Collector query JSON already preserves query fields and can carry bounded
non-secret saved-profile origin in existing `extra`, avoiding a column/schema change.

A data copy is rejected because schemas are not semantically equivalent: legacy accepted/rejected
filter counts and profile filter rules cannot be truthfully reconstructed as Collector verification,
partial/cancel or RM-107 decision facts. No rows, IDs, money, timestamps or tender links will be
rewritten. Therefore backup/restore is not required for RM-140 application startup; rollback is the
exact baseline code plus untouched legacy and Collector rows.

## 8. Performance baseline

Environment: Windows 10 `10.0.19045`, Python 3.12.7, AMD64 Family 23 Model 1, 8 logical CPUs,
7.93 GiB RAM. Fixture `rm140-baseline-v1`, deterministic items, 50% duplicates, two warmups.
Wall timing excludes `tracemalloc`; peak allocation is one separate traced pass.

| Raw/merged | Repeats | p50 ms | p95 ms | Peak MiB | Thread delta |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0/0 | 12 | 0.033 | 0.047 | 0.001 | 0 |
| 100/50 | 12 | 120.694 | 139.880 | 0.958 | 0 |
| 1,000/500 | 8 | 1,249.849 | 1,307.573 | 8.996 | 0 |
| 10,000/5,000 | 5 | 13,836.030 | 14,485.276 | 89.308 | 0 |

Canonical history write/read: 0 items 20.632/12.574 ms; 100 raw/50 merged 94.601/27.250 ms;
1,000 raw/500 merged 752.515/30.368 ms. RSS 89.180 → 164.176 MiB after all retained benchmark
objects; active threads stayed 1.

Cancellation baseline: ten offline slow providers, concurrency 4, ten runs. Task count 1 → peak 14
→ 1 after terminal; cancel-to-terminal p50 18.421 ms, p95/max 29.348 ms. The first benchmark
attempt exposed the SQLite handle leak described above; it is not counted as pipeline performance.

## 9. Rollback and exact acceptance evidence

Rollback:

1. revert RM-140 feature commits/merge;
2. no schema or data transform to undo;
3. existing legacy and Collector rows remain byte/relationally untouched;
4. public legacy modules/imports remain available for the RM-138/RM-139 rollback window;
5. provider settings, credentials, schedule, notifications and RM-139 monitoring schemas do not
   change.

Planned exact evidence:

- characterization: public imports/order, legacy timeout, current admission/history/FKs/time,
  RM-138 safe outcome/offline composition/RM-107 authority;
- expected-red: app lifecycle and repeated shutdown, scheduler race/stop, late-result rejection,
  runtime/SQLite cleanup, aware/unknown time, sentinel redaction, one production owner/history
  writer, performance bounds and offline composition;
- implementation focus: RM-140 files plus adjacent RM-137–RM-139, profile/UI, store/schema,
  bootstrap/build and decision tests;
- full workflow-derived gates, same-machine performance rerun and five sequential race cycles;
- Windows Actions Python 3.12/3.13, feature merge exact SHA, then separate docs-only closeout.

## 10. Audit conclusion

**ACCEPTED FOR DOCS-ONLY AUDIT COMMIT.** Ownership of both search paths is proven. RM-140 will
reuse the canonical async Collector and existing tender UI controller, remove legacy production
composition without deleting its public compatibility API, retain legacy history read-only, close
application/SQLite resources deterministically, enforce aware/monotonic time, and sanitize the
existing error boundary. No RM-141 work is required.
