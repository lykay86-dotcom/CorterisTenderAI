# RM-126 — обязательный handoff-контракт RM-127–RM-140

Дата решения: 16 июля 2026 года. Baseline: `7d51159a`. Этот документ фиксирует границы будущих
этапов и не является новой реализацией.

## Канонические владельцы

| Область | Source of truth | Правило расширения |
|---|---|---|
| UI раздела «Тендеры» | `ModernMainWindow`/`DashboardLayout`, одна выделяемая tender page | RM-127 извлекает существующий legacy central widget по частям, без второго shell |
| Search application boundary | `CollectorRunSession` + `CollectorService` + `AsyncProviderSearchEngine` | Sync runner остаётся compatibility facade до перевода UI; третий engine запрещён |
| Provider catalog | `ProviderDescriptor` и collector commercial definitions | Один source/provider identity; sync placeholders только migration aliases |
| Enablement/config/health | `CollectorProviderManager` над существующими JSON stores и verification DB | RM-131 консолидирует существующие stores, не создаёт третий |
| Credentials | `app.security.secrets`/Windows keyring; env только explicit override | Значение никогда не читается для показа, не сохраняется в JSON/SQLite и не экспортируется |
| Saved search profiles | `TenderSearchProfileRepository(search_profiles.json)` | Версионируемая schema migration внутри этого repository; built-in и custom сохраняются |
| Business capability | `CompanyCapabilityProfileRepository` | Не смешивать с search profile; только явно подтверждённые пользователем данные |
| Matching/ranking | `MatchingCatalogRepository` + collector normalizer/ranker | RM-137 выбирает одну chain и учитывает `canonical_term`; объяснимость сохраняется |
| Canonical tender record | `TenderRegistryRepository`/shared `tender_records` | CollectorStateRepository владеет collector state, но не вводит второй identity root |
| Collector schema | `CollectorSchemaMigrator` | Только versioned migration; `CREATE TABLE IF NOT EXISTS` не заменяет migration |
| Decision | `ParticipationDecisionService` + `ParticipationDecisionPolicy` | Critical stop-factor выше score и AI; AI может только добавить проверяемые findings/текст |
| Lifecycle | один application-owned tender controller | Явный idempotent shutdown отменяет workers, останавливает scheduler и ждёт bounded completion |

## Решения source-of-truth D-01–D-10

- **D-01:** канонический shell — modern; RM-127 выделяет отдельную tender page из embedded legacy
  content, сохраняя временные adapters к существующим dialogs/actions.
- **D-02:** target search boundary — async Collector. Sync profile API сохраняется как facade до
  завершения migration RM-128/RM-138 и затем выводится из production composition.
- **D-03:** канонический catalog строится из `ProviderDescriptor` и collector definitions; одинаковые
  источники в sync/async — ports/aliases, а не независимые business adapters.
- **D-04:** `CollectorProviderManager` — façade состояния enablement/config/health. Текущие JSON/DB
  owners мигрируются под него без нового store.
- **D-05:** единый credential boundary — keyring contract `save/load/delete_secret`; UI принимает
  replacement, показывает только configured state, а не secret/masked value.
- **D-06:** search profiles расширяются в `TenderSearchProfileRepository`; capability и matching —
  отдельные доменные понятия, не альтернативные saved-profile repositories.
- **D-07:** целевая normalization/dedup chain — Collector normalizer → deduplicator → verification;
  sync merge временно совместим, после parity retire.
- **D-08:** `tender_records` — canonical record; `collector_runs` — целевая run history после migration;
  `tender_search_runs` сохраняется read-compatible до переноса/retention decision.
- **D-09:** money только finite non-negative `Decimal` + explicit currency; domain datetime только aware,
  timezone нельзя угадывать. Unknown/naive input маркируется/отклоняется на adapter boundary.
- **D-10:** C1–C20 распределены по RM-127–RM-140; отдельная Collector roadmap прекращается.

## Compatibility, deprecation и порядок миграции

1. RM-127 изолирует UI, не меняя search semantics.
2. RM-128 вводит одну панель над существующим profile repository и временным sync/async facade.
3. RM-129/130 версионируют существующие capability/search profile contracts.
4. RM-131/132 сводят source settings и credentials за `CollectorProviderManager`/keyring.
5. RM-133–136 добавляют только audited descriptors/protocol adapters/health checks в тот же catalog.
6. RM-137 утверждает Collector normalization/dedup и мигрирует canonical terms.
7. RM-138 переводит все search entry points на async boundary; sync implementation получает explicit
   deprecation и удаляется только после parity, telemetry и rollback window.
8. RM-139 переиспользует collector health/checkpoint/circuit-breaker/scheduler state.
9. RM-140 закрывает schema/time/lifecycle/error boundary, performance, offline и Windows regressions,
   затем удаляет подтверждённые compatibility paths.

Ни один шаг не допускает big-bang rewrite. Каждый migration сохраняет read compatibility,
детерминированный порядок, identity keys и rollback на предыдущую версию приложения.

## Инварианты

1. AI не меняет score, recommendation, verified facts или приоритет critical stop-factor.
2. Один provider/source имеет один business adapter; sync/async могут быть только ports одного parser.
3. Network не запускается при composition/startup; health/live checks — только explicit user action или
   явно включённое расписание.
4. Отмена Collector сохраняет только честно помеченные partial/cancelled результаты.
5. `Decimal` не преобразуется во float при persistence/JSON decision payload.
6. Domain timestamps aware; scheduler/DB timestamps хранятся в UTC с offset; source timezone остаётся
   в provenance.
7. Secrets не попадают в JSON, SQLite, logs, status bar, reports, support bundle и exception text.
8. Unverified/aggregator-only data не становится verified из-за merge, persistence или UI rendering.
9. Critical blocked requirement всегда возвращает `DO_NOT_PARTICIPATE`, независимо от score/AI.
10. Built-in search profiles нельзя удалить/подменить custom; corrupt catalog quarantine не стирает
    пользовательский файл молча.
11. Один manual и один scheduled Collector run не выполняются одновременно.
12. Shutdown idempotent, bounded и закрывает network runtime даже при cancellation/error.

## Матрица готовности RM-127–RM-140

| RM | Название | Что уже существует | Что переиспользовать | Подтверждённый gap | Что запрещено дублировать | Prerequisite | Acceptance tests |
|---|---|---|---|---|---|---|---|
| RM-127 | Новая структура вкладок | Modern shell, embedded legacy page, tender actions/dialogs | `DashboardLayout`, controller actions, legacy widgets как временные компоненты | tender content не изолирован; global search пишет в catalog query | второй main window/shell и новый tender workflow | D-01, UI journey map | navigation/focus/action parity; no hidden legacy shell owner; close smoke |
| RM-128 | Единая панель поиска | saved profiles UI, topbar global search, Collector dialog | `TenderSearchProfileRepository`, query models, D-02 facade | topbar search — equipment catalog, не tender search; два entry contract | новый query repository/engine | RM-127, D-02 | one query routes to facade; provider/profile selection; offline composition |
| RM-129 | Универсальные бизнес-профили | capability profile, Corteris classifier, matching catalog | `CompanyCapabilityProfile`, versioned catalog, explicit confirmation | Corteris-specific fields/rules не отделены от reusable capability schema | смешивание business capability с saved search | D-06 | schema upgrade/rollback; explicit confirmation; score explainability unchanged |
| RM-130 | Сохранённые поисковые профили | atomic `search_profiles.json`, built-in/custom, dialogs/runner | `TenderSearchProfileRepository` | schema v1 не покрывает universal search modes | второй JSON/SQLite profile repository | RM-128/129 | corrupt quarantine; built-in protection; custom migration; old-file round trip |
| RM-131 | Настройки площадок | enablement, commercial settings, health JSON, provider manager | `CollectorProviderManager` façade | enablement дублируется в двух JSON stores; legacy platforms отдельны | третий source settings store | D-03/D-04 | deterministic merge/migration; no secret persistence; UI state parity |
| RM-132 | Безопасный ввод API и credentials | keyring wrapper, MOS replacement dialog, env overrides | `app.security.secrets`, provider secret names | commercial/legacy UI contract неоднороден; raw error paths | новый secret vault, чтение значения для UI, masked export | RM-131, D-05 | save/reload/delete with fake keyring; no value in files/log/export/errors |
| RM-133 | Ручное добавление площадки | legacy `PlatformConnection` and explicit tester; descriptors | audited descriptor/catalog extension point | legacy arbitrary endpoint не интегрирован в provider catalog | произвольный executable adapter или direct registry mutation | RM-131/132 | allowlist/validation, duplicate identity rejection, disabled default, no startup I/O |
| RM-134 | Выбор протокола | legacy API/RSS/FTP/FTPS tester; async HTTP contract | typed protocol strategy behind provider contract | protocol semantics/TLS/error policy не унифицированы | string switch и второй network stack без audit | RM-133 | protocol-specific TLS/timeouts/limits/cancel/error redaction |
| RM-135 | Безопасный конструктор адаптера | commercial access placeholders and descriptors | catalog + vetted protocol strategies only | нет безопасного declarative schema | user code execution, CAPTCHA/access bypass, guessed API | RM-134 | schema validation; no arbitrary imports/code; contract fixtures; honest NOT_CONFIGURED |
| RM-136 | Тест подключения | provider `check_health`, manager explicit background checks, C19 verification | existing health monitor and vertical verification | generic exception сохраняется как `type: message`; legacy tester separate | второй/третий health mechanism, auto live startup test | RM-131–135 | explicit action; bounded/cancellable; sanitized result; health != C19 verified |
| RM-137 | Отраслево-независимая нормализация | Collector normalizer/dedup/provenance; sync merge; matching catalog | Collector chain and shared identity keys | `canonical_term` не используется; parallel merge semantics | новая третья normalizer/deduplicator chain | D-07 | golden normalization; canonical-term; money/time/provenance; deterministic dedup |
| RM-138 | Параллельный поиск | thread-pool sync engine; async semaphore/cancel/circuit breaker | async Collector boundary, profile facade | sync timeout не останавливает running call; два равноправных engine | третий engine или вечные dual paths | RM-128, RM-137 | parity; cancel/timeout; partial; ordering; bounded shutdown; migration fallback |
| RM-139 | Мониторинг источников | health/checkpoints/circuit breaker/scheduler/notifications/C19 state | existing collector state and manager | единое агрегированное представление отсутствует | отдельный monitor DB/prober | RM-131/136/138 | no startup network; state freshness; scheduled/manual guard; notification dedup |
| RM-140 | Стабилизация поиска | 395 target tests, full Windows gate, migrations/backups | all canonical owners above | lifecycle, naive time, raw errors, dual histories/compat cleanup | feature rewrite или новая schema family | RM-127–139 | migration+backup; aware time; shutdown races; error redaction; perf/offline/Win 3.12/3.13 |

## Security boundaries

- Endpoint — potentially private metadata: хранить только normalized HTTP(S) endpoint без user-info,
  query/fragment; в exports применять redaction.
- Username — private metadata: допустим только в protected local settings после решения RM-132;
  никогда не использовать как credential value.
- Password/token/API key — только keyring или explicit process environment; environment не экспортировать.
- Health/error — публичная модель должна содержать bounded category/message; raw exception, response body,
  URL query и credential backend text не сохранять.
- Manual protocol — disabled by default, allowlisted schemes, TLS verification, size/time limits, no
  automatic retries that can multiply writes, no access/CAPTCHA bypass.

## Test boundaries

Каждый RM выполняет focused contour плюс полный workflow-equivalent gate. Обязательные guards:

- UI contract и lifecycle: Qt offscreen, close during every worker type, scheduler timer stop;
- provider: descriptor uniqueness across all factories, no-network composition, live checks opt-in;
- data: Decimal/currency, aware timezone, source provenance, deterministic identity/dedup;
- security: fake keyring/environment isolation, endpoint/error/log/support-bundle redaction;
- persistence: old/current/future/corrupt schema, atomic write, transaction rollback, backup/restore;
- decision: critical stop-factor priority and AI immutability;
- release: Windows Python 3.12/3.13, Ruff, format, mypy, secret scan, pip-audit and build smoke.

## Запрещённые дубли

- второй shell или второй tender analysis workflow;
- второй saved-search repository либо third source-settings store;
- третий provider factory/catalog или parallel search engine;
- второй credential vault либо показ сохранённого secret;
- второй health/checkpoint/circuit-breaker/scheduler subsystem;
- третий normalization/dedup chain;
- новые canonical tender tables/identity root без versioned migration;
- AI-owned score/recommendation/criticality;
- live network в offline tests, bootstrap или composition smoke.
