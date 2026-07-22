# PRE-RM-156 Collector — normative contract

Версия: `pre-rm156-collector-contract-v1`.

Дата: 22 июля 2026 года.

Baseline: `c20bed32492dc80b48748c79a87da73107533ddd`.

Этот документ фиксирует обязательные границы P2–P9 до application changes. При конфликте с
реализацией реализация считается дефектной. Решения RM-107 по score, recommendation и абсолютному
приоритету critical stop-factor не изменяются.

## 1. Единственные владельцы

1. `CollectorRunSession` владеет lifetime одного production run.
2. `CollectorNetworkRuntime` владеет shared HTTP client, rate limiter и health monitor.
3. `AsyncProviderSearchEngine` владеет bounded parallel provider execution.
4. `CollectorService` владеет authoritative pipeline и run result.
5. `CollectorStateRepository` и `CollectorSchemaMigrator` владеют Collector persistence/DDL в
   существующей `tender_registry.sqlite3`.
6. `canonical_provider_definitions()` владеет built-in provider identity.
7. `ProviderEnablementRepository` владеет enablement/config/manual registration settings.
8. Existing credential, verification, ranker, stop-factor, scheduler и UI admission owners
   сохраняются.

Второй engine, service, catalog/factory, settings store, credential vault, health monitor,
checkpoint DB или новая tender DB запрещены.

## 2. Provider identity

Built-in canonical IDs:

`eis`, `mos_supplier`, `zakaz_rf`, `roseltorg`, `rad`, `tek_torg`, `ets_nep`, `sber_a`,
`rts_tender`, `gazprombank`, `b2b_center`, `fabrikant`, `otc`.

Правила:

- один canonical ID соответствует одной юридически и технически определённой площадке;
- несколько API/schema одной площадки — strategies одного provider owner, не новые providers;
- разные площадки не делят один generic source ID;
- `discovery` и `custom` не являются built-in platform IDs;
- persisted legacy IDs сохраняются либо получают versioned compatibility mapping;
- `_commercial` IDs становятся aliases canonical platform IDs, а не наоборот;
- factory/catalog/manual registration отвергают duplicate ID, duplicate source, alias collision и
  duplicate normalized display name;
- неизвестный или неоднозначный legacy ID fail closed и требует manual migration review.

## 3. Readiness state machine

Единственная допустимая последовательность:

`REGISTERED -> ACCESS_AUDITED -> FIXTURE_ACCEPTED -> IMPLEMENTED_OFFLINE -> LIVE_VERIFIED -> WORKING`.

`BLOCKED_EXTERNAL` допустим из любого состояния после `REGISTERED`, если отсутствует договор,
token, официальная документация, разрешённый endpoint или внешняя доступность. Переходы требуют
append-only evidence. `WORKING` требует одновременно:

- confirmed identity и lawful access method;
- redacted real fixture с provenance;
- offline parser/mapping/page/checkpoint/artifact contract;
- safe health mapping;
- live diagnostic evidence вне обычного pytest/CI;
- disable и rollback procedure.

Placeholder, наличие hostname, заполненный token или единичный live response не равны `WORKING`.
Provider без внешнего доступа остаётся `BLOCKED_EXTERNAL`, не симулирует success и не блокирует
приёмку общей технической основы.

## 4. Backward-compatible page contract

`AsyncTenderProvider.search()` сохраняется. Общий extension предоставляет async page iterator или
эквивалентный typed adapter со следующей семантикой:

```python
@dataclass(frozen=True, slots=True)
class ProviderPage:
    provider_id: str
    contract_version: str
    parser_version: str
    query_fingerprint: str
    page_identity: str
    items: tuple[UnifiedTender, ...]
    next_cursor: str
    terminal: bool
    artifacts: tuple[RawArtifactReference, ...]
    warnings: tuple[str, ...] = ()
```

Конкретные имена могут измениться до P3, семантика — нет:

- legacy/fake provider по умолчанию даёт ровно одну terminal page через существующий `search()`;
- engine, а не UI/service/provider-global loop, выполняет page iteration;
- provider строит и разбирает один bounded request/page;
- page identity детерминирована provider, contract, query fingerprint и cursor;
- duplicate/repeated cursor, cursor cycle и non-progress page fail closed;
- cancellation проверяется до request, между retry attempts, после parse и до page acceptance;
- page/item/time/byte limits проверяются до следующего request;
- completion order providers не меняет output ordering;
- документы не скачиваются search path без явного audited provider requirement.

## 5. Query fingerprint

Fingerprint — SHA-256 canonical JSON следующих semantic fields:

- canonical provider ID;
- provider contract version и parser version;
- keywords/exclusions/regions/laws;
- price/currency filters;
- explicit date window либо normalized incremental scope;
- provider-specific typed filters.

Текущая page number, transient retry state, UI presentation и secrets в fingerprint не входят.
Любая несовместимая contract/parser/filter semantics меняет fingerprint или version.

## 6. Page acceptance и persistence

Accepted page — минимальная durable unit. Для каждой page порядок неизменен:

1. получить bounded raw response;
2. зарегистрировать artifact metadata/content digest;
3. распарсить provider DTO;
4. отделить discovery-only items;
5. normalise/verify/deduplicate только authoritative items;
6. транзакционно сохранить accepted items, provenance, artifacts и page receipt;
7. в той же транзакции записать следующий checkpoint/commit marker;
8. только после commit публиковать durable counters и запрашивать следующую page.

Page не считается принятой при parse/mapping/verification/persistence error. Cancellation во время
page оставляет предыдущие accepted pages, отбрасывает незавершённую page и не продвигает cursor.
Повтор после crash обязан безопасно replay последнюю неподтверждённую page; identity/dedup делают
операцию идемпотентной.

Для текущего single-batch service P3 может добавить chunk/page repository method, но не второй
repository. Final run completion остаётся отдельной terminal boundary после всех page commits.

## 7. Checkpoint contract

Checkpoint содержит минимум:

- canonical `provider_id`;
- `contract_version` и `parser_version`;
- `query_fingerprint` и human-readable scope key;
- committed cursor/watermark;
- last accepted page identity/digest;
- accepted item/page counters;
- committed timestamp;
- replay/reset generation.

Инварианты:

- checkpoint обновляется только атомарно с accepted page;
- future/unknown contract version не используется старым кодом;
- несовместимый fingerprint не переиспользуется автоматически;
- overlap window не заменяет commit marker;
- empty terminal page может завершить run, но не скрывает предыдущую uncommitted page;
- reset — явная подтверждённая user action с append-only audit record;
- rollback к старому parser сохраняет несовместимый checkpoint для диагностики и начинает
  совместимый scope; данные не удаляются.

## 8. Raw artifact и provenance

Raw bytes хранятся в scoped content-addressed store под lifecycle owner Collector. DB сохраняет
immutable reference:

- SHA-256 полного content;
- byte length и media type/encoding;
- canonical provider ID;
- sanitized request method/URL без secret query/user-info;
- status code и retrieval time UTC;
- query fingerprint, page identity, contract/parser versions;
- parse outcome и accepted page/run link;
- retention class.

Одни bytes не дублируются. Temporary file пишется bounded streaming path и атомарно публикуется
после digest/size verification. HTML login/captcha/error body классифицируется contract/auth error,
а не tender page. Raw artifacts не входят в AI context автоматически и не удаляются rollback-
командой; удаление выполняет отдельная retention procedure после проверки DB references.

## 9. Discovery-only gate

Любой aggregator/discovery record отделяется сразу после provider mapping и до normalization,
identity aliases, dedup, verification, scoring, recommendation и stop-factor. Он может:

- создать/обновить discovery queue record;
- породить запрос к разрешённому official provider;
- сохранить собственный raw artifact/provenance как discovery evidence.

Он не может создавать или изменять official tender/field candidate/score/recommendation. Только
повторно полученные official data проходят authoritative pipeline. Match decision не копирует
aggregator field values.

## 10. Trust, merge и deterministic decisions

Порядок доверия:

`OFFICIAL_DOCUMENTATION > EIS > OFFICIAL_PLATFORM > OFFICIAL_API > CUSTOMER_SITE > PUBLIC_CARD > AGGREGATOR > UNKNOWN`.

Trust назначается audited provider/mapping contract. Непроверенный response field
`source_trust`, numeric trust или provenance flags не повышают authority. Все field candidates,
conflicts и manual resolutions сохраняются. Merge выбирает representative/candidates
детерминированно и не зависит от task completion order. `Decimal` не преобразуется во float,
timestamps остаются timezone-aware. AI не меняет selected field, score, recommendation или
critical stop-factor.

## 11. Terminal run status

Успешный provider outcome — только `SUCCESS` или `EMPTY`. Truth table применяется после
нормализации requested set:

| Условие | Run status |
|---|---|
| user cancellation/shutdown | `CANCELLED` |
| overall deadline исчерпан | `TIMED_OUT` |
| requested provider set пуст/недопустим | admission error, run не стартует |
| successful providers = 0 | `FAILED` |
| successful > 0 и non-success > 0 | `PARTIAL` |
| все requested providers successful | `COMPLETED` |

Accepted pages до cancellation/timeout/partial failure сохраняются. `FAILED` не означает rollback
ранее committed pages, но UI/notifications не называют такой run partial success. Один provider
failure не отменяет остальных. Provider outcomes, safe errors и counters сохраняются полностью.

## 12. Errors, retries и security

- public errors используют bounded safe category/code/message; raw exception/URL/body не выходит
  в UI/log/history;
- secrets не попадают в DB, settings, artifacts metadata, fixtures, logs, warnings или query
  fingerprint;
- HTTP uses shared `AsyncHttpClient`; provider не создаёт global client/loop/thread pool;
- retries разрешены для audited transient transport/status errors и honour `Retry-After`;
- auth/contract/parse/captcha/access-denied errors не маскируются retries;
- default maximum — 3 attempts, response ≤ 50 MiB, global concurrency ≤ 6, domain concurrency ≤ 2;
- robots/terms/rate limits/contracts соблюдаются; CAPTCHA, WAF, MFA и платный доступ не обходятся;
- live diagnostics explicit opt-in, sanitized и никогда не запускаются обычным pytest/CI.

## 13. Migration contract

Любое schema изменение:

1. увеличивает `COLLECTOR_SCHEMA_VERSION` ровно на один;
2. реализует explicit old→current step в existing `CollectorSchemaMigrator`;
3. имеет inventory/dry-run до записи;
4. создаёт verified backup до destructive/shape-changing step;
5. выполняется одной транзакцией/atomic replace, затем readback/integrity check;
6. покрывает empty/current/old/future/corrupt/partial failure/backup/restore tests;
7. сохраняет IDs, aliases, versions, candidates/conflicts/resolutions, scores, decisions, run
   history, `Decimal` и aware datetimes;
8. не запускается обычным read-only path;
9. не делает automatic downgrade.

Provider settings migration применяет те же fail-closed/readback правила и не хранит secrets.

## 14. Resource budgets

Нормативные budgets из P1 audit:

- interactive: 20 pages, 10,000 accepted items, 180 seconds overall;
- scheduled: 200 pages, 100,000 accepted items, 900 seconds overall;
- page size ≤ 500;
- response ≤ 50 MiB;
- progress queue ≤ 64;
- provider concurrency ≤ 6 global/2 domain; EIS и Mos Supplier ≤ 1 domain;
- same-host 10k fixture p95 ≤ 10,000 ms и regression ≤ 20%; sampled RSS delta ≤ 64 MiB;
- 25-cycle lifecycle: zero owned resource growth;
- cancellation terminal wait ≤ 1 second в offline deterministic contour.

Provider contract может только уменьшить budgets без нового audit. Scheduled path обязан быть
streaming/chunked; лимит 100,000 не разрешает materialize full run.

## 15. P2 expected-red acceptance

До implementation создаются отдельные tests, каждый падающий по одной отсутствующей границе:

| ID | Ожидаемый contract |
|---|---|
| `C-PAGE-001` | engine consumes all pages deterministically |
| `C-PAGE-002` | repeated/cyclic cursor fails boundedly |
| `C-CANCEL-001` | cancellation between pages drops unaccepted page |
| `C-CP-001` | checkpoint advances only with page DB commit |
| `C-CP-002` | crash replay is idempotent and does not skip data |
| `C-STATUS-001` | zero-success is `FAILED` |
| `C-STATUS-002` | overall timeout is `TIMED_OUT` |
| `C-DISC-001` | discovery never reaches normalize/dedup/decision on multi-page path |
| `C-ORDER-001` | provider/page completion order does not change canonical result |
| `C-IDENT-001` | duplicate provider/source/alias identity rejected everywhere |
| `C-ART-001` | artifact metadata/content and accepted page are commit-coupled |
| `C-SEC-001` | secrets/raw URL/body are redacted from every public error/artifact field |
| `C-MIG-001` | old/current/future/corrupt/backup/restore schema contract |
| `C-LEASE-001` | overlapping production run admission is deterministic |

Existing passing characterization tests остаются зелёными. Expected-red commit не содержит
implementation и фиксируется до P3.
