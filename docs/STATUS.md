# Текущее состояние CorterisTenderAI

Обновлено: 18 июля 2026 года.

## Активный этап

**RM-139 — мониторинг источников**

Статус: `IN PROGRESS`

RM-138 завершён после audit-first реализации, feature merge и успешного exact
merge-SHA Windows Quality Gate. RM-139 — единственный активный этап;
RM-140–RM-200 остаются `PLANNED` и не выполняются параллельно.

## Завершённый этап

**RM-138 — параллельный поиск**

Статус: `DONE`

Подтверждение:

- audit/contract/plan зафиксированы commit `bd3880d` до application-кода,
  expected-red lifecycle contract — `7360125`;
- existing production `AsyncProviderSearchEngine`, Collector session/admission, RM-137 normalizer/
  deduplicator, repository/DB, HTTP retry и DI paths переиспользованы; третий engine, второй retry,
  model/repository/DB не добавлялись;
- bounded parallel lifecycle публикует immutable revisioned snapshots с exact queued/running/
  completed state, aware UTC, monotonic provider/overall deadlines и engine-owned progress;
- cooperative idempotent cancellation ставит terminal boundary до отмены задач, сохраняет принятые
  partial results и отвергает late completions; legacy blocking-thread limit задокументирован;
- canonical partial results используют RM-137 normalization/dedup один раз и детерминированы
  относительно completion schedule; slow progress subscriber не удерживает provider slot;
- provider/pipeline/persistence/UI boundaries используют safe typed category/code/message без raw
  exception/URL/credential; UI остаётся в одном background worker и не вычисляет business progress;
- sync `TenderSearchEngine` API, RM-107 score/recommendation/hard-exclusion и critical stop-factor
  priority сохранены;
- локально: full pytest `1892 passed, 2 warnings`; secret scan, Ruff/format (`611 files`), mypy,
  workflow smokes, five-cycle race gate и dependency audit успешны;
- feature PR #84 слит в `main` merge commit
  `593ed39c7b81efc8a67e36eef47ceadbbbaf46ca`;
- PR Quality Gate run `29619784410` успешен: Python 3.12 —
  `1892 passed, 2 warnings in 94.36s`, Python 3.13 —
  `1892 passed, 2 warnings in 111.15s`;
- exact merge-SHA run `29619998396` успешен: Python 3.12 —
  `1892 passed, 2 warnings in 102.67s`, Python 3.13 —
  `1892 passed, 2 warnings in 82.24s`; все обязательные jobs завершились `success`.

## Ранее завершённый этап

**RM-137 — отраслево-независимая нормализация**

Статус: `DONE`

- Feature PR #81 слит в `main` коммитом `e38c8c1`.
- Exact merge-SHA Quality Gate run `29615080804` успешен на Python 3.12/3.13.
- Canonical normalization/dedup и deterministic decision boundaries сохранены.

## Текущее действие

Начать RM-139 с отдельного audit-first пакета и канонического entry gate.
Не начинать RM-140+ и не изменять deterministic decision/scoring/critical stop-factor priority
до отдельно утверждённого source-monitoring contract.
