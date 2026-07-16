# Текущее состояние CorterisTenderAI

Обновлено: 16 июля 2026 года.

## Активный этап

**RM-129 — универсальные бизнес-профили**

Статус: `IN PROGRESS`

RM-128 завершён после audit-first реализации, feature merge и успешного exact-SHA post-merge
Windows Quality Gate. RM-129 назначен единственным активным этапом; RM-130–RM-200 остаются
`PLANNED` и не выполняются параллельно.

## Завершённый этап

**RM-128 — единая панель поиска**

Статус: `DONE`

Подтверждение:

- audit и implementation plan зафиксированы docs-only commit `39605d0` до application changes;
- одна `TenderUnifiedSearchPanel` встроена над existing tabs одной `TenderWorkspacePage`; topbar
  использует narrow page → panel → existing controller path и больше не меняет `catalog_query`;
- pure immutable request boundary сохраняет query profile, `Decimal`, currency и dates, меняет только
  ephemeral keywords и отклоняет missing/disabled/stale profile/provider без fallback/network;
- unified panel, existing Collector dialog и scheduler разделяют один `TenderSearchUiController`,
  один `_CollectorRunWorker`, cancellation token, progress/result cleanup и canonical registry;
- unified path использует existing async `CollectorRunSession`; legacy profile dialog/sync runner
  сохранён как rollback path до RM-138;
- новый repository/engine/Collector/provider catalog/DB/migration/profile schema/dependency не создан;
  decision/AI/critical stop-factor priority не изменены;
- локально: focused `23 passed in 5.20s`, neighbor `66 passed in 8.80s`, full pytest
  `1552 passed in 61.49s`; все workflow-equivalent gates успешны;
- feature PR #62 слит в `main` коммитом `a67f5df`
  (`a67f5df331f8257799e24a9ef3980c6feea69c7a`);
- PR Quality Gate run `29499175129` успешен: Python 3.12 — `1552 passed in 67.74s`,
  Python 3.13 — `1552 passed in 97.95s`;
- exact-SHA post-merge run `29499519358` успешен: Python 3.12 —
  `1552 passed in 169.06s`, Python 3.13 — `1552 passed in 73.62s`; первоначальный transient native
  access violation Python 3.12 не воспроизвёлся при rerun того же SHA;
- на обеих версиях прошли secret scan, Ruff check/format (`545 files`), mypy (20 файлов),
  offline/migration/import/composition/build smoke и dependency audit.

## Ранее завершённый этап

**RM-127 — новая структура вкладок**

Статус: `DONE`

Подтверждение:

- feature PR #60 слит в `main` коммитом `0b95567`;
- post-merge Quality Gate run `29489511239` успешен на Python 3.12/3.13;
- reusable tender workspace и direct modern composition имеют статус `DONE`.

## Текущее действие

Начать RM-129 только с обязательного аудита существующих company capability, search profile,
matching/ranking и deterministic decision contracts. Не смешивать business capability с saved search
profiles и не менять score/recommendation/critical stop-factor priority.
