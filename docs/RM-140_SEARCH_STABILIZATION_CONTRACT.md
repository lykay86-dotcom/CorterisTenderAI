# RM-140 — контракт стабилизации универсального поиска

Contract version: `universal-search-stabilization-v1`  
Baseline: `f14ba84d754a4c84f1173812731e36ec274200f4`  
Статус: implementation target

## 1. Canonical production boundary

Каждый production search entry point — unified panel, Collector dialog, saved profile, rerun и
scheduler — проходит через один admission owner в existing `TenderSearchUiController`, затем через
`CollectorRunSession` → `CollectorService` → `AsyncProviderSearchEngine`.

`TenderSearchEngine`, `CorterisTenderSearchService` и `TenderSearchProfileRunner` остаются только
deprecated import/test/rollback compatibility API. Bootstrap/runtime/UI их не создают и не
вызывают. Compatibility API не получает нового executor, normalization, dedup или history bridge.

Provider order, selection, Decimal, provenance, verification, RM-107 scoring/recommendation,
hard exclusions и абсолютный приоритет critical stop-factor не меняются. AI не может изменить
verified fact, score или recommendation.

## 2. Application lifecycle

Application owner публикует immutable snapshot с одним состоянием:

```text
IDLE -> QUEUED -> RUNNING -> CANCELLING -> CANCELLED
                         -> COMPLETED
                         -> FAILED
                         -> TIMED_OUT
```

Правила:

- только `IDLE`/terminal owner принимает новый manual/scheduled/saved-profile run;
- один admission generation имеет не более одного terminal transition;
- repeated cancel и repeated shutdown идемпотентны;
- progress/result с устаревшей generation или после terminal boundary игнорируется;
- partial data сохраняется только canonical pipeline до принятого terminal boundary;
- scheduler tick, manual action и saved profile используют один busy/admission guard;
- passive monitoring не является run и не занимает admission slot;
- UI только отображает snapshot и не считает progress/retry/freshness/decision.

Default Qt pool принадлежит tender controller, не global singleton. Injected test pool сохраняется.
Worker предоставляет completion event/handle; cancellation остаётся cooperative, `terminate()`
запрещён.

## 3. Bounded shutdown

`TenderSearchUiController.shutdown(timeout_ms)` вызывается shell `closeEvent` и повторно после
выхода Qt loop как defense-in-depth. Последовательность:

1. запретить admission;
2. idempotently остановить scheduler timer и startup callback;
3. закрыть monitoring/progress subscriptions и пометить terminal generation;
4. cancel active Collector и provider-check tokens;
5. перейти `RUNNING/QUEUED -> CANCELLING -> CANCELLED` не более одного раза;
6. bounded wait worker/pool completion;
7. `CollectorRunSession.finally` закрывает network runtime даже при error/cancel;
8. закрыть owned SQLite connection scopes;
9. очистить references только после terminal boundary;
10. позволить закрытие shell только после successful bounded shutdown.

Target timeout: 3,000 ms по умолчанию; unit/race tests используют меньший injected timeout. Если
worker не завершился в budget, shutdown возвращает `False`, сохраняет admission closed и shell не
уничтожает UI owner. Бесконечный wait и orphan signal delivery запрещены.

## 4. Time and clocks

- Active run `started_at`, `completed_at`, error/snapshot time — ISO 8601 aware UTC с offset.
- Caller-supplied malformed/naive active run timestamp отклоняется до persistence.
- Elapsed/deadline/timeout/cooldown используют `perf_counter`, event-loop time или injected
  monotonic clock; wall-clock jump/DST не меняет timeout и `elapsed_ms >= 0`.
- Adapter timestamp с explicit zone нормализуется в UTC с сохранённой provenance.
- Naive source deadline остаётся `timezone_status=unknown`, исходная строка/diagnostic сохраняется;
  region/language/machine timezone не используются для догадки.
- Existing naive `tender_search_runs` не переписываются и не получают `UTC` через `replace`;
  compatibility reader маркирует их `unknown`.
- UI преобразует только aware values в user timezone; unknown отображается честно без смещения.

## 5. Safe typed errors

Existing `SearchErrorCategory`, stable code mapping and async outcome are the public owner. Failure
projection имеет bounded:

- category;
- stable allowlisted code;
- fixed safe localizable message;
- canonical provider ID;
- retryable и terminal semantics;
- aware event/batch timestamp;
- safe correlation/run ID.

Unknown exception всегда становится `internal/provider_internal_error` с фиксированным сообщением.
Поле compatibility `error_type` содержит stable code, а не Python class. До health, persistence,
log, notification, UI и export отбрасываются raw `str/repr`, nested cause, traceback, URL
userinfo/query/fragment, response body, request headers/cookies, absolute path, SQL values,
token/password/API key/keyring text.

Health monitor принимает classified failure или сам классифицирует exception без чтения его text.
Not-configured health хранит fixed safe message. SQLite хранит только safe code/message. Search
logging использует code/phase/provider ID; support-bundle redactor остаётся дополнительной защитой.
Code/message/provider/correlation fields имеют явные length bounds.

## 6. History and compatibility

`CollectorStateRepository` и Collector schema v14 остаются единственным target writer всех новых
production runs. Saved-profile origin записывается как bounded non-secret context в existing
versioned query JSON; отдельная column/table/schema family не создаётся.

`tender_search_runs`/`tender_search_run_items`:

- не получают новых production writes;
- не мигрируются и не удаляются;
- сохраняют PK/FK/linkage и rollback readability;
- public compatibility writer остаётся только для direct legacy API;
- readers показывают existing data, naive timestamps как unknown;
- двойная запись запрещена.

No-migration acceptance: Collector schema остаётся 14, registry schema остаётся 1, row/link counts
до/после initialization совпадают, old/current data читаются, future Collector schema fail-closed,
corrupt/missing read-only monitoring evidence даёт empty/unknown. Так как mutation схемы и data copy
нет, migration backup не создаётся; rollback — revert code с untouched DB.

Обе repository `_connect` boundaries гарантированно закрывают SQLite handles на success/error;
после метода файл можно rename/delete на Windows.

## 7. Offline and network isolation

Import, runtime composition, bootstrap graph creation, modern shell open/close, dialog open,
profile/provider/history load, passive monitoring and shutdown-before-run запрещают DNS, socket,
HTTP(S), FTP(S), keyring read и live health probe. Scheduler startup run возможен только через
existing explicit persisted opt-in.

Network допускается только после explicit accepted run/check action. Каждый accepted run имеет
ровно один fresh runtime и ровно один `aclose`, включая success/error/cancel/timeout и close error;
close exception проходит safe typed boundary.

## 8. Progress, concurrency and race bounds

- Provider task concurrency не превышает configured maximum и не зависит от item count.
- Progress queue остаётся bounded 64; slow/failing subscriber не удерживает provider semaphore.
- Progress dispatcher close остаётся bounded; subscriber exception не меняет search result и не
  содержит raw exception в public log message.
- После terminal/shutdown task/thread/timer/runtime/SQLite handle count возвращается к baseline.
- Cancellation на 25%, 50% и непосредственно перед terminal publication даёт один terminal state.
- Scheduler tick racing manual admission допускает ровно один run.
- Five-cycle gate выполняется последовательными отдельными pytest invocations на одном SHA.

## 9. Performance budgets

Same-machine feature measurement использует seed `rm140-baseline-v1`, те же warmups/repeats,
0/100/1,000/10,000 raw items и 50% duplicates.

- normalize/dedup p95 не хуже baseline более чем на 10%; thresholds: 0.052, 153.868, 1,438.330 и
  15,933.804 ms соответственно;
- peak traced allocation не хуже более чем на 15%; thresholds: 0.002, 1.102, 10.345 и 102.704 MiB;
- history write/read не хуже baseline более чем на 10% на одной машине, но сравнительное время не
  является единственным CI gate;
- deterministic CI проверяет counts/order/complexity bounds, configured concurrency, bounded
  progress, handle/task/thread cleanup и shutdown;
- ten-provider cancel-to-terminal target p95 <= 100 ms locally and always <= 1,000 ms test bound;
- application shutdown target <= 3,000 ms;
- UI thread не выполняет network, normalization или bulk DB work.

Небольшие значения набора 0 считаются smoke, а не стабильным microbenchmark. Любое превышение
budget требует recorded explanation и не может быть скрыто увеличением threshold после feature.

## 10. Acceptance and stop conditions

Required guards:

- public import/signature and offline/frozen compatibility;
- one production owner and one production history writer;
- state/late-result/repeated shutdown and Windows handle cleanup;
- aware UTC/monotonic/naive unknown/DST-wall-jump behavior;
- sentinel absent from outcome repr, health, SQLite/JSON, log, UI, notification and support bundle;
- old/current/future/corrupt history behavior and unchanged row/link counts;
- RM-107 decision/AI/Decimal/provenance parity;
- focused/neighbor/full pytest, secret scan, Ruff check/format, mypy, migration/import/composition/
  build, dependency audit, performance and five race cycles;
- Windows Quality Gate Python 3.12/3.13 on feature and exact merge SHA.

Stop on any orphan worker/runtime/handle, secret persistence, unexplained performance regression,
data-link loss, full/Windows gate failure, need for a new owner/schema family, or RM-141+ scope.
