# PRE-RM-156 Collector P1 — audit-first baseline

Дата аудита: 22 июля 2026 года.

Baseline: `origin/main` / `c20bed32492dc80b48748c79a87da73107533ddd`.

Scope: P1 из
[`PRE_RM156_TENDER_COLLECTOR_ALL_PLATFORMS_TZ.md`](PRE_RM156_TENDER_COLLECTOR_ALL_PLATFORMS_TZ.md).
Аудит не меняет application-код, schema, зависимости, настройки или persisted data.

## 1. Итог

Существующий Collector пригоден как единственная архитектурная основа. Создавать второй engine,
service, catalog, settings owner, checkpoint store или network runtime не требуется и запрещено.
Production composition уже соединяет один `CollectorRunSession`, один
`CollectorNetworkRuntime`, один `AsyncProviderSearchEngine`, один `CollectorService` и один
`CollectorStateRepository` на существующей `tender_registry.sqlite3`.

До третьего рабочего источника обязательны expected-red contracts и исправления:

1. engine не обходит `next_page_token` и вызывает `search()` каждого provider только один раз;
2. ЕИС и Портал поставщиков записывают checkpoint внутри provider до `save_batch()`;
3. zero-success и timeout run ошибочно проецируются сервисом в `PARTIAL`;
4. checkpoint не типизирован версиями parser/contract и не имеет commit/replay marker;
5. raw artifact contract отсутствует; EIS debug snapshots не связаны с DB commit/retention;
6. built-in identity неполна и для трёх существующих источников перевёрнута alias-модель;
7. schema version 14 создаётся общим `CREATE TABLE IF NOT EXISTS`, без последовательных
   old-to-current migration steps, dry-run/backup/rollback contour;
8. две рабочие реализации имеют offline fixtures, но ещё не проходят единый page/artifact/
   checkpoint contract и поэтому не могут быть объявлены полностью `WORKING` по новому ТЗ.

## 2. Runtime ownership

| Область | Канонический owner | Production composition | Решение |
|---|---|---|---|
| Сессия запуска | `app.tenders.collector.run_session.CollectorRunSession` | создаёт runtime на один run и закрывает его в `finally` | KEEP |
| Network lifetime | `CollectorNetworkRuntime` | один shared `AsyncHttpClient`, limiter и health monitor | KEEP |
| Параллельный поиск | `AsyncProviderSearchEngine` | один provider task на источник, bounded concurrency/timeouts | EXTEND |
| Pipeline/решения | `CollectorService` | discovery gate, normalize/dedup, verification, score, stop-factor, persistence | REPAIR |
| Provider contract | `AsyncTenderProvider` | EIS, Mos Supplier, manual/commercial adapters | EXTEND backward-compatibly |
| Provider composition | `create_default_async_providers()` | создаётся из snapshot настроек и shared runtime | KEEP |
| Service composition | `create_default_collector_service()` | repository + providers + engine + deterministic ranker/stop-factor | KEEP |
| Provider identity | `canonical_provider_definitions()` | UI/settings/factory используют этот read model | REPAIR/EXPAND |
| Enablement/settings | `ProviderEnablementRepository` schema 6 | `collector_provider_settings.json`; legacy split-file migration | KEEP/MIGRATE |
| Credentials | `app.tenders.provider_credentials` и `app.security.secrets` | environment/Windows Credential Manager, без DB/plaintext | KEEP |
| Health | `ProviderHealthMonitor` + existing provider/control read models | shared runtime и passive history hydration | KEEP |
| State/database | `CollectorStateRepository` | существующая `tender_registry.sqlite3` | KEEP |
| Collector DDL | `CollectorSchemaMigrator` version 14 | вызывается при repository initialize | REPAIR before schema change |
| Checkpoints | `CollectorStateRepository` + provider coordinators | таблица `collector_checkpoints` | REPAIR |
| Scheduler | `CollectorScheduler` + `TenderCollectorSchedulerUiController` | scheduled/manual entry идут через один UI admission owner | KEEP |
| UI admission | `TenderSearchUiController._try_start_collector_query()` | `_collector_worker`/generation не допускают overlap | KEEP |
| Discovery queue | `AggregatorDiscoveryRepository` | те же DB и schema owner; discovery items исключены до dedup | KEEP + expected-red guard |
| Normalization/dedup | `TenderNormalizer` / `TenderDeduplicator` | engine строит partial projection; service сохраняет final projection | KEEP boundary, test parity |
| Verification/trust | `TenderVerificationService` / `SourceTrustLevel` | deterministic priority, все candidates/conflicts сохраняются | KEEP |
| Decision authority | deterministic ranker + stop-factor | AI не участвует в выборе | IMMUTABLE |

### 2.1. Production path

`TenderSearchUiController` создаёт один `CollectorRunSession`. Manual, run-now, startup и timer
schedule проходят через один admission method. Сессия получает один settings snapshot, создаёт
один network runtime, гидратирует existing health monitor, собирает один service и гарантированно
закрывает HTTP runtime. `CollectorService` открывает run, получает batch от engine, отделяет
discovery-only records, выполняет deterministic pipeline и транзакционно сохраняет batch.

Внутрипроцессное UI mutual exclusion существует. Межпроцессного DB-backed lease нет; запуск двух
экземпляров приложения остаётся отдельным риском и должен быть решён общим run-admission contract,
а не вторым scheduler.

## 3. Duplicate и residual map

| Кандидат | Наблюдение | Классификация | Действие |
|---|---|---|---|
| `app.tenders.provider_factory` + `providers.placeholders.create_builtin_providers()` | legacy sync registry с отдельным неполным catalog | LEGACY RESIDUAL | сохранить для старого search runtime до consumer audit; не расширять Collector через него |
| `canonical_provider_definitions()` | фактический Collector catalog | CANONICAL OWNER | расширять только его и связанные compatibility migrations |
| `CommercialProviderSettingsRepository` | старый `commercial_provider_settings.json`; manager всё ещё создаёт repository object | MIGRATION RESIDUAL | чтение только для migration; удалить runtime owner после characterization |
| `ProviderEnablementRepository` | schema 6, canonical enablement/config/manual registration store | CANONICAL OWNER | сохранить |
| `enablement_repository` alias в manager | same-object compatibility alias | NOT DUPLICATE | сохранить до consumer retirement |
| `sber_a -> sber_commercial`, `rts_tender -> rts_commercial`, `roseltorg -> roseltorg_commercial` | старые доменные IDs ошибочно считаются aliases новых commercial IDs | IDENTITY DEFECT | канонизировать в `sber_a`, `rts_tender`, `roseltorg`; старые `_commercial` оставить aliases |
| `TenderSource.COMMERCIAL` и provider `commercial` | legacy generic placeholder | LEGACY ID | не использовать для built-in platform identity; мигрировать только с доказанным mapping |
| manual providers с `TenderSource.CUSTOM` | declarative extension contour | DISTINCT OWNER | сохранить; запретить collision с built-ins и aliases |
| EIS sync provider и `AsyncEisTenderProvider` | две реализации для разных runtimes | TRANSITION RESIDUAL | Collector использует только async; legacy retirement — отдельный audited change |
| `LegacySyncProviderAdapter` | `asyncio.to_thread`, cancellation не останавливает thread | TRANSITION ADAPTER | допустим для совместимости, не эталон нового provider |
| EIS `EisSnapshotWriter` | opt-in debug files вне DB | DEBUG FACILITY, NOT RAW STORE | не считать target artifact owner; заменить/адаптировать после schema contract |

## 4. Provider identity и readiness

Целевой built-in набор содержит 13 платформ. `discovery` и `custom` — отдельные contours и не
подменяют built-in adapters. Статусы ниже описывают доказанное состояние baseline, а не намерение.

| Canonical ID | Наличие baseline | Доказанное состояние | Access/readiness gap |
|---|---|---|---|
| `eis` | async public HTML provider | `IMPLEMENTED_OFFLINE` | не официальный API; нет общего page/artifact/commit checkpoint contract и свежей live acceptance |
| `mos_supplier` | async official bearer API provider | `IMPLEMENTED_OFFLINE` | нужен законный token; server pagination contract не зафиксирован; нет свежей live acceptance |
| `zakaz_rf` | отсутствует в enum/catalog | `NOT_REGISTERED` | provider identity, access method, fixtures и legal audit отсутствуют |
| `roseltorg` | source enum есть, catalog ID — `roseltorg_commercial` | `REGISTERED_WITH_IDENTITY_DEFECT` | contract/API/credentials/fixture не подтверждены |
| `rad` | отсутствует | `NOT_REGISTERED` | identity/access/contract/fixtures отсутствуют |
| `tek_torg` | disabled commercial placeholder | `REGISTERED` | access audit required; working adapter отсутствует |
| `ets_nep` | отсутствует | `NOT_REGISTERED` | identity/access/contract/fixtures отсутствуют |
| `sber_a` | source enum есть, catalog ID — `sber_commercial` | `REGISTERED_WITH_IDENTITY_DEFECT` | access audit required; working adapter отсутствует |
| `rts_tender` | source enum есть, catalog ID — `rts_commercial` | `REGISTERED_WITH_IDENTITY_DEFECT` | access audit required; working adapter отсутствует |
| `gazprombank` | disabled commercial placeholder | `REGISTERED` | access audit required; working adapter отсутствует |
| `b2b_center` | disabled commercial placeholder | `REGISTERED` | access audit required; working adapter отсутствует |
| `fabrikant` | disabled commercial placeholder | `REGISTERED` | access audit required; working adapter отсутствует |
| `otc` | disabled commercial placeholder | `REGISTERED` | access audit required; working adapter отсутствует |

Текущие commercial adapters честно возвращают `NOT_CONFIGURED`/ошибку и `is_working=False`.
Ни один endpoint нельзя считать подтверждённым только по hostname из catalog/network settings.
До внешнего access evidence соответствующие provider packages остаются `REGISTERED` либо
`BLOCKED_EXTERNAL`, но не `WORKING`.

## 5. Correctness audit

### P1-AUD-001 — pagination не исполняется (`critical`)

`TenderSearchResult.next_page_token` формируется EIS и Mos Supplier, но `AsyncProviderSearchEngine`
вызывает `provider.search(query)` один раз. Результат bulk run ограничен первой страницей. Для Mos
Supplier pagination дополнительно локальная: один server response фильтруется и режется по page,
пока параметры server pagination не закреплены контрактом.

### P1-AUD-002 — checkpoint опережает durable commit (`critical`)

Оба native providers вызывают `checkpoints.mark_success(prepared, result)` до возврата результата
engine. `CollectorService` сохраняет authoritative batch позднее отдельной транзакцией. Crash,
cancellation или ошибка normalize/verify/save между этими точками продвинет cursor мимо
несохранённых данных.

### P1-AUD-003 — terminal status нечестен (`critical`)

Engine различает `FAILED`, `PARTIAL`, `TIMED_OUT`, `CANCELLED`, но
`CollectorService._status_for_batch()` возвращает только `CANCELLED`, `PARTIAL` или `COMPLETED`.
Любой non-success outcome даёт `PARTIAL`, включая zero-success/all-failed и timeout. В
`CollectionRunStatus` отсутствует `TIMED_OUT`.

### P1-AUD-004 — checkpoint contract недостаточен (`high`)

`CollectorCheckpoint` содержит только строки `provider_id/scope_key/cursor/watermark`, свободный
`state` и timestamp. Нет `contract_version`, `parser_version`, query fingerprint, accepted page,
commit marker, replay attempt или reset audit. Query scope coordinators исключают page/date fields
и применяют overlap window, но это не обеспечивает commit/replay semantics.

### P1-AUD-005 — raw artifact owner отсутствует (`high`)

EIS умеет opt-in запись HTML/debug error в timestamped files с коротким content digest. Записи не
имеют DB reference, full digest contract, request/query fingerprint, response metadata, parser/
contract version, retention и связи с accepted page. Mos Supplier raw body не сохраняет.

### P1-AUD-006 — identity catalog неполон (`high`)

В `TenderSource` нет `zakaz_rf`, `rad`, `ets_nep`. Catalog использует `_commercial` как canonical
IDs для Sber/RTS/Roseltorg и объявляет требуемые canonical IDs aliases в обратную сторону.
Legacy placeholder catalog — отдельный неполный список. Любая правка требует settings/DB/export
inventory и compatibility mapping, без переименования persisted rows на месте.

### P1-AUD-007 — schema migration contour недостаточен (`high`)

Collector schema version 14 отвергает future version и idempotently создаёт таблицы, но не имеет
последовательных migration functions для 1→…→14, dry-run inventory или Collector-specific backup/
restore/rollback evidence. Старое значение меньше 14 приводит к выполнению всего current DDL и
перезаписи meta version. Future rejection покрыт тестом; corrupt/old/current/backup contour неполон.

### P1-AUD-008 — discovery gate есть, но нужен expected-red regression (`medium`)

Engine исключает `is_aggregator_discovery()` из partial normalization/dedup. Service повторно
отделяет discovery до final normalization, складывает его в queue и не сохраняет как официальный
tender. Это правильная граница. Её следует закрепить expected-red тестом именно для нового
multi-page acceptance path, чтобы page-level refactor не вернул aggregator values в dedup.

### P1-AUD-009 — trust metadata нуждается в fail-closed contract (`medium`)

Детерминированный `SourceTrustLevel` и field candidates существуют. Однако provider-controlled
`raw_metadata.source_trust`/field provenance могут задавать явный numeric trust level. Новый
adapter contract должен разрешать trust только из audited provider identity/mapping owner, а не из
непроверенного payload. AI не участвует и не будет участвовать в выборе.

### P1-AUD-010 — process-wide run lease отсутствует (`medium`)

UI worker/generation предотвращает overlap manual/scheduled runs в одном процессе. Отдельные
процессы могут начать run одновременно против одной SQLite DB. P2 должен сначала охарактеризовать
реальный риск; если lease необходим, он добавляется в существующую DB/session admission path.

## 6. Migration и persistence inventory

Collector использует существующую `tender_registry.sqlite3`; новая БД запрещена. Version 14
содержит run/provider/item history, aliases, source observations, versions, changes, scores,
stop-factors, matching/commercial estimates, verification candidates/conflicts/resolutions/history,
freshness, rates, checkpoints, discovery queue/attempts, decisions и summaries.

`save_batch()` выполняет `BEGIN IMMEDIATE` и атомарно сохраняет tender/alias/source/version/change/
verification/freshness/score/run-item данные. `complete_run()` — последующая отдельная транзакция.
Checkpoint сейчас сохраняется третьей независимой операцией ещё до `save_batch()`, что и создаёт
P1-AUD-002.

Provider settings schema 6 поддерживает migration v2–v5, legacy split v1 и future rejection.
Canonical file — `collector_provider_settings.json`. Legacy
`commercial_provider_settings.json` должен быть только migration input; секреты в обоих файлах
запрещены. Identity expansion обязана мигрировать keys с readback verification и сохранять aliases.

## 7. Offline baseline

Все успешные измерения выполнены на clean baseline SHA с Python 3.12, Windows, без live provider
requests. Из-за sandbox ACL системный pytest temp дал инфраструктурный `WinError 5`; валидные
повторы использовали scoped `--basetemp` внутри worktree. Это не изменение CI-команд.

| Gate | Результат |
|---|---|
| repository secret scan | passed |
| Ruff | `All checks passed!` |
| Ruff format | `794 files already formatted` |
| mypy | `Success: no issues found in 20 source files` |
| focused Collector/RM131/RM138–140 | `107 passed in 41.39s` |
| mandatory provider/diagnostic pair | `2 passed in 16.50s` |
| DB migration/schema | `5 passed in 10.94s` |
| bootstrap composition | `1 passed in 0.57s` |
| build/frozen | `9 passed in 8.28s` |
| RM-155 compatibility | passed |
| full suite | `2411 passed, 2 warnings in 264.42s` |
| pip-audit | `No known vulnerabilities found` |
| P0 exact merge-SHA Quality Gate | run `29922814088`, success on Python 3.12/3.13 |

Первый focused attempt (`58 passed, 49 setup errors`) и второй (`58 passed, 49 setup errors`)
классифицированы как environment-only: соответственно unreadable system temp и отсутствующий
parent для scoped basetemp. Третий запуск с существующим scoped parent полностью успешен.

## 8. Performance baseline и утверждённые P1 budgets

Детерминированный RM-140 fixture: 10,000 raw records, 5,000 merged records, два source records на
identity. После одного warm-up выполнено 5 измерений полного normalize+deduplicate cycle. Peak RSS
семплировался каждые 10 ms через `psutil`; это process RSS, не Python allocation peak.

- p50: `7,583.978 ms`;
- p95 nearest-rank (n=5): `8,096.375 ms`;
- min/max: `7,529.505 / 8,096.375 ms`;
- baseline RSS: `166,424,576 bytes`;
- sampled peak RSS: `199,512,064 bytes`;
- sampled delta RSS: `33,087,488 bytes`.

Предыдущая попытка 20 timing samples + one `tracemalloc` cycle превысила 240 секунд и не считается
результатом. Для сравнения P3 используется тот же 5-sample protocol на том же host.

До P3 утверждаются следующие regression/resource budgets:

| Контур | Budget |
|---|---|
| exact-data normalize/dedup | ровно 10,000 raw / 5,000 merged; без sampling |
| same-host p95 | не более `10,000 ms` и не хуже baseline более чем на 20% |
| sampled RSS delta | не более `64 MiB` для 10,000 fixture records |
| global provider concurrency | максимум 6; per-domain — максимум 2, для EIS/Mos — 1 |
| progress queue | максимум 64 events |
| HTTP response | максимум 50 MiB на response до provider-specific снижения |
| retry | максимум 3 HTTP attempts; retry только audited transient classes |
| interactive run | максимум 20 pages, 10,000 accepted items и 180 seconds overall |
| scheduled bulk run | максимум 200 pages, 100,000 accepted items и 900 seconds overall |
| page size | максимум 500, существующий `TenderSearchQuery` contract |
| cancellation | check до request, между retries/pages и до commit; terminal wait ≤ 1 second offline |
| lifecycle soak | 25 create/run/close cycles; zero remaining owned tasks/threads/timers/files |

Scheduled budgets не разрешают держать 100,000 items или raw bodies в памяти: P3 обязан применять
page/chunk acceptance и commit. Provider contract может задать меньший лимит, но не больший без
нового measured audit.

## 9. P1 exit decision

P1 может считаться зафиксированным после merge отдельных docs-only audit/contract/plan commits и
успешного Quality Gate. Application changes всё ещё запрещены в этой ветке. Следующий пакет — P2
expected-red, который должен доказуемо падать только на перечисленных отсутствующих boundaries.
P3 implementation не начинается до фиксации P2.
