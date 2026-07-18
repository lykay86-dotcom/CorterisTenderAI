# RM-140 — приёмка стабилизации поиска

Дата локальной приёмки: 18 июля 2026 года.

Статус пакета: feature implementation и локальные gates пройдены. RM-140 остаётся `IN PROGRESS`
до merge feature PR, успешного Windows Quality Gate на точном merge SHA и отдельного docs-only
closeout по `docs/DEFINITION_OF_DONE.md`.

## Границы и трассируемость

- Базовый `main`: `f14ba84d754a4c84f1173812731e36ec274200f4`.
- Feature branch: `feat/rm-140-search-stabilization`.
- Audit/contract/plan: `30b2f4a`.
- Characterization: `23d28ce`; `7 passed`, соседний контур `28 passed`.
- Expected-red: `ed150ae`; `8 passed, 12 failed in 11.10s`, все failures соответствовали
  заранее описанным lifecycle/time/error/shutdown/compatibility gaps.
- Локально принятый implementation SHA: `f9db188`.
- Пакет закрывает C20 из `docs/RM-126_REQUIREMENTS.md` и не начинает RM-141+.

## Принятая реализация

- Все production UI entry points, включая saved profiles и scheduler, проходят через один
  `TenderSearchUiController` admission generation и один Collector worker. Late progress/result,
  повторный terminal и конкурирующий запуск отклоняются.
- Controller владеет pool, worker/token/provider-check и typed lifecycle вплоть до `CLOSED`.
  Scheduler timer и application shutdown идемпотентны и bounded; main window закрывает tender owner
  до dashboard owner.
- Production composition root больше не создаёт legacy `TenderSearchEngine`, search service и
  profile runner. Их публичные импорты сохранены только как rollback-compatible API.
- Активные времена — aware UTC; durations используют injected monotonic clock. Naive active writes
  отклоняются, старые naive timestamps читаются как `timezone_status=unknown` без догадки и rewrite.
- Exception class/text, nested cause, URL, body и secret-shaped provider metadata не выходят за
  typed allowlist. Sentinel отсутствует в outcome/snapshot/warnings, health, SQLite, UI,
  notification JSON, log и support bundle.
- Новые production runs пишутся только в Collector schema v14; saved-profile origin хранится в
  bounded `TenderSearchQuery.extra`. Registry schema остаётся v1, legacy rows/links/hashes не
  меняются, backup/data-copy migration не создаётся, future Collector schema fail-closed.
- `TenderRegistryRepository` и `CollectorStateRepository` закрывают каждое SQLite connection после
  commit/rollback/read. WAL/schema initialization выполняется один раз на экземпляр, не создавая
  повторного владельца или новой schema family.
- Offline import/composition/dialog load/shutdown не используют DNS, socket, HTTP или keyring read;
  network разрешён только после принятого run/check action.
- RM-107 score/recommendation, critical stop-factor priority, money/Decimal и AI decision boundary
  не изменялись.

## Локальные проверки

Implementation SHA `f9db188`, Windows 10 `10.0.19045`, Python 3.12.7, AMD64 Family 23 Model 1,
8 logical CPUs:

- full pytest: `1946 passed, 2 warnings in 155.86s`;
- repository/no-migration focused: `20 passed in 11.84s`;
- final RM-140 security/offline/lifecycle contour: `27 passed in 12.79s`;
- deterministic volume/concurrency/progress: `6 passed in 24.02s`;
- repository secret scan: passed;
- `ruff check .`: passed;
- `ruff format . --check`: `630 files already formatted`;
- required mypy: `Success: no issues found in 20 source files`;
- workflow smokes: offline `2 passed in 14.95s`, migration `5 passed in 8.91s`, public import
  `DashboardController`, composition `1 passed in 0.56s`, build/release `6 passed in 10.26s`.

Два warnings принадлежат прежнему openpyxl contour: unsupported extension и conditional formatting
в `test_rm132_legacy_credentials_handoff.py`. Новых warnings RM-140 нет.

Пять последовательных race invocations на одном SHA:

| Цикл | Результат | Время |
| ---: | ---: | ---: |
| 1 | 11 passed | 8.73s |
| 2 | 11 passed | 9.40s |
| 3 | 11 passed | 8.27s |
| 4 | 11 passed | 9.66s |
| 5 | 11 passed | 7.49s |

Каждый цикл проверял one admission/terminal, late-result rejection, repeated shutdown, Windows
connection close, provider concurrency 4, cancellation и progress-worker cleanup.

Локальный `pip-audit` заблокирован политикой tenant, что зафиксировано без обхода. На неизменённых
dependency manifests exact baseline/closeout SHA `f14ba84...` прошёл dependency audit в GitHub run
`29624885521`. Обязательное подтверждение для feature и exact merge SHA остаётся за Windows Quality
Gate до closeout.

## Performance acceptance

Воспроизводимая команда:

```text
python -m scripts.benchmark_rm140_search_stabilization
```

Fixture `rm140-baseline-v1`, два warmup, те же repeats, отдельный `tracemalloc` pass. Финальный запуск
на `f9db188`:

| Raw/merged | Repeats | p50 ms | p95 ms | Threshold p95 | Peak MiB | Threshold peak |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0/0 | 12 | 0.004 | 0.007 | 0.052 | 0.001 | 0.002 |
| 100/50 | 12 | 128.840 | 155.938 | 153.868 | 0.909 | 1.102 |
| 1,000/500 | 8 | 1,318.507 | 1,486.644 | 1,438.330 | 8.570 | 10.345 |
| 10,000/5,000 | 5 | 14,247.675 | 14,747.242 | 15,933.804 | 85.075 | 102.704 |

Thread delta во всех размерах равен 0. p50 regression относительно baseline: 100 `+6.75%`, 1,000
`+5.49%`, 10,000 `+2.98%`; 10,000 p95 и все memory budgets проходят. На 100 и 1,000 один
committed run превысил p95 threshold на 1.34% и 3.36% соответственно. Это превышение не скрыто:
normalize/dedup production code в RM-140 не менялся, предыдущий полный запуск дал 135.301 и
1,455.427 ms, а отдельный повтор 1,000 с тем же warmup/repeats дал 1,414.430 ms. Совокупность p50,
большого 10,000 contour и повторов указывает на Windows host scheduling/GC variance, а не на
объёмную регрессию алгоритма; thresholds не увеличивались.

History write/read после explicit connection close:

| Raw/merged | Write ms | Read ms | Baseline write/read ms |
| ---: | ---: | ---: | ---: |
| 0/0 | 22.505 | 5.802 | 20.632 / 12.574 |
| 100/50 | 64.648 | 5.745 | 94.601 / 27.250 |
| 1,000/500 | 342.203 | 6.084 | 752.515 / 30.368 |

Нулевая write smoke отличается от baseline на 1.873 ms абсолютных; объёмные 100/1,000 и все reads
быстрее baseline. Cancellation, десять providers/concurrency 4: tasks `1 → 14 → 1`, p50 `17.078ms`,
p95 `17.719ms`, max `17.945ms`, что ниже local target 100ms и test bound 1,000ms.

## Rollback и оставшиеся gates

- Схема и данные не преобразовывались; rollback — revert feature commits на baseline code.
- Legacy rows/API, provider settings, credentials, schedules, notifications и RM-139 monitoring
  сохраняются.
- До feature merge RM-140 не переводится в `DONE`; `STATUS.md`, `ROADMAP.md` и
  `ROADMAP_HISTORY.md` обновляются только отдельным closeout после exact merge-SHA gate.
- Требуются feature PR review, Windows Quality Gate Python 3.12/3.13, dependency audit, merge,
  отдельный successful run на точном merge SHA и docs-only closeout.
