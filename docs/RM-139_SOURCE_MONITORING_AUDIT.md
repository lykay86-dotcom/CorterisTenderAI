# RM-139 — аудит мониторинга источников

Дата аудита: 18 июля 2026 года  
Baseline: `d333e2658aacdb16f91c49c7c26ba96843a151d1`  
Ветка: `feat/rm-139-source-monitoring`  
Статус: audit завершён до изменения application-кода.

## 1. Entry gate и baseline

Канонические `STATUS.md`, `ROADMAP.md`, `DEFINITION_OF_DONE.md` и
`ROADMAP_HISTORY.md` назначают RM-139 единственным `IN PROGRESS`; RM-138 имеет `DONE`,
RM-140–RM-200 остаются `PLANNED`. Baseline совпадает с RM-138 docs-closeout merge.

Прочитаны handoff и владельцы RM-126, RM-136 и RM-138. До production changes выполнен
owner-contour с repository-local basetemp:

```text
44 passed in 13.85s
```

Первый запуск через системный Python не имел `pytest`; запуск через `.venv` без отдельного
basetemp встретил только `PermissionError` стандартного Windows temp до выполнения 25 тестов.
Повтор с тем же кодом и `--basetemp .tmp/rm139-baseline-20260718` прошёл полностью.

## 2. Ownership map

| Измерение | Канонический владелец | Persisted source | Решение RM-139 |
| --- | --- | --- | --- |
| Enablement/readiness | `CollectorProviderManager` + `ProviderEnablementRepository` | `collector_provider_settings.json`, schema v6 | Только читать frozen display/settings state. |
| Explicit connection health | `ProviderCheckRepository` | `collector_provider_health.json`, schema v2 | Сохранить manual evidence и built-in check records без изменения schema. |
| In-run circuit | `ProviderHealthMonitor` | Сейчас только память одного runtime | Восстанавливать тот же monitor из existing safe run history. |
| Run/provider outcomes | `CollectorStateRepository` | `collector_runs`, `collector_run_providers`, Collector schema v14 | Добавить узкий read-only query, не новые таблицы. |
| Checkpoints | `CollectorStateRepository` | `collector_checkpoints` | Добавить ordered read-only list method. |
| Schedule | `CollectorScheduler` + `CollectorScheduleRepository` | `collector_schedule.json`, schema v1 | Читать active providers/next due; сохранять один busy guard. |
| Notifications | `CollectorNotificationRepository` + `CollectorNotificationService` | `collector_notifications.json`, schema v1 | Добавить deterministic transition events через существующий capped store. |
| C19 verification | `VerticalSourceVerificationRepository` | `collector_vertical_source_verifications` в existing SQLite | Читать latest evidence; `WORKING` только через `qualifies_as_working`. |
| UI | `TenderProviderManagerDialog` + `TenderSearchUiController` | нет | Показывать готовый immutable snapshot, без TTL/priority/network logic. |
| Decision authority | RM-107 deterministic services | existing decision stores | Не изменять score/recommendation/hard exclusion/critical stop-factor. |

Новый persisted owner, monitor DB, health JSON, prober, scheduler, notification store,
normalizer/deduplicator или retry layer не требуются.

## 3. Фактические data flows

1. Explicit check: `_ProviderCheckWorker` → `CollectorProviderManager.check_providers()` →
   provider `check_health()`/manual health service → `ProviderCheckRepository` → manager state → Qt.
2. Collector: `CollectorRunSession` snapshots settings → создаёт fresh network runtime →
   `AsyncProviderSearchEngine` → safe terminal outcomes → `CollectorService` →
   `CollectorStateRepository.complete_run()`.
3. Circuit: engine вызывает existing `ProviderHealthMonitor`; monitor принадлежит runtime,
   созданному на один run, и исчезает после `runtime.aclose()`.
4. Checkpoints: EIS/MOS adapters → `CollectorStateRepository.save_checkpoint()` →
   `collector_checkpoints`.
5. Scheduler: `TenderCollectorSchedulerUiController` → `CollectorScheduler.poll()` →
   existing `try_start_collector()` → единственный `_collector_worker`.
6. Notifications: scheduler controller → existing service → existing capped repository.
7. C19: live smoke service → `VerticalSourceVerificationRepository`; обычный health не создаёт
   qualifying C19 evidence.

## 4. Подтверждённые gaps

- Circuit continuity действительно теряется: `create_collector_network_runtime()` создаёт новый
  `ProviderHealthMonitor`, а `CollectorRunSession` создаёт runtime для каждого run.
- Единого immutable read model нет; UI смешивает enablement, explicit health и C19 в один
  `ProviderUiState/status_text`.
- Нет ordered read API для provider outcomes и checkpoints.
- Built-in connection record не имеет отдельного freshness projection; manual evidence имеет
  собственный `valid_until` и не должно подчиняться общей TTL.
- Scheduler timestamps являются aware local time; run/checkpoint/C19 strings могут содержать
  malformed/naive/future values. Projection обязана fail closed и выдавать aware UTC.
- `ProviderCheckRecord.last_error`, scheduler `last_error`, C19 `error_message` и некоторые
  controller exception render paths исторически способны содержать raw text. Monitoring не будет
  копировать их: только closed reason code и фиксированное bounded сообщение.
- Explicit health check и Collector имеют разные workers. Для RM-139 принимается fail-fast guard:
  explicit check отклоняется во время активного Collector; passive refresh не занимает slot.

## 5. Persistence и migration decision

`collector_run_providers` уже хранит terminal provider status, safe error code/message, run ID и
через join с `collector_runs` aware completion time. Этого достаточно, чтобы детерминированно
вычислить consecutive remote failures, last success и cooldown boundary. Cancelled, unsupported,
skipped и circuit-open observations не увеличивают remote failure count.

Поэтому:

- `collector_provider_health.json` остаётся schema v2;
- Collector SQLite остаётся schema v14;
- DB migration, JSON schema bump и backup не требуются;
- новые read methods открывают existing DB read-only (`mode=ro/query_only`) и не создают schema;
- future/corrupt/missing evidence даёт `unknown/invalid`, а не автоматическую перезапись.

## 6. Time/freshness policy decision

Contract `source-monitoring-v1` использует aware UTC и допускает future skew не более 5 минут.
Naive/malformed timestamps остаются invalid. Policy constants:

- built-in explicit connection health: 24 часа;
- manual health: исключительно persisted `valid_until`;
- checkpoint при active schedule: два schedule interval + 5 минут, bounded 1–48 часами;
- checkpoint вне active schedule: 24 часа;
- C19 evidence: 30 дней, поскольку это полный live vertical smoke, а не дешёвый health probe.

Cooldown runtime arithmetic остаётся monotonic. Persisted completion UTC используется только для
расчёта remaining duration при hydration; отрицательное значение означает probe-eligible degraded,
значение выше policy cap fail closed/clamp до code-owned maximum. Python monotonic values не
сохраняются.

## 7. Lifecycle, startup и race decision

- Composition, bootstrap, dialog open и passive refresh не вызывают provider/network methods.
- Existing `run_on_startup=False` сохраняется; явный persisted opt-in остаётся scheduled run.
- Manual и scheduled run продолжают использовать один `_collector_worker`/busy callback.
- Explicit connection check во время Collector отклоняется фиксированным safe сообщением.
- Monitoring snapshot имеет один service-owned monotonic revision на lifetime controller.
- Initial snapshot не создаёт notifications. Только переход между двумя наблюдёнными snapshots с
  новой evidence identity может создать alert; deterministic ID обеспечивает repository dedup.

## 8. Audit conclusion

**ACCEPTED FOR DOCS-ONLY AUDIT COMMIT.** RM-139 реализуем точечным расширением existing owners.
Ключевое предположение плана подтверждено, но schema v3 не нужна: existing Collector run history
покрывает operational continuity. Application changes разрешены только после этого audit,
contract и implementation plan в отдельном commit, затем отдельного expected-red test commit.
