# Текущее состояние CorterisTenderAI

Обновлено: 16 июля 2026 года.

## Активный этап

**RM-128 — единая панель поиска**

Статус: `IN PROGRESS`

RM-127 завершён после feature merge и успешного post-merge Windows Quality Gate. RM-128 назначен
единственным активным этапом; RM-129–RM-200 остаются `PLANNED` и не выполняются параллельно.

## Завершённый этап

**RM-127 — новая структура вкладок**

Статус: `DONE`

Подтверждение:

- audit и implementation plan зафиксированы commit `13dfb83` до application changes;
- `TenderWorkspacePage(QWidget)` владеет единственным набором из 8 top-level и 6 settings tabs со
  stable keys/objectNames; legacy `MainWindow` оставлен тонким standalone wrapper;
- production `ModernMainWindow` больше не создаёт hidden legacy shell, не вызывает
  `takeCentralWidget()` и не обращается к legacy fields;
- Dashboard/topbar используют narrow page API; price/equipment compatibility semantics сохранены,
  universal search RM-128 преждевременно не реализован;
- один существующий `TenderSearchUiController` и те же 7 direct/2 scheduler QAction, dialogs,
  workers, search/Collector runtime и C11 full-analysis workflow переиспользованы;
- DB/schema/migrations/dependencies/providers/decision/AI не изменены;
- локальный focused contour: `54 passed in 31.02s`; полный pytest дважды успешен:
  `1532 passed in 55.91s` и `1532 passed in 77.25s`;
- feature PR #60 слит в `main` коммитом `0b95567`
  (`0b9556799a20ddbf7338476fe76f602e7ff79d07`);
- post-merge Quality Gate run `29489511239` успешен: Python 3.12 —
  `1532 passed in 82.83s`, Python 3.13 — `1532 passed in 145.43s`;
- на обеих версиях прошли repository secret scan, Ruff check/format (`540 files`), mypy (20 файлов),
  offline/migration/import/composition/build smoke tests и dependency audit.

## Ранее завершённый этап

**RM-126 — аудит раздела Тендеры и укрепление провайдера ЕИС**

Статус: `DONE`

Подтверждение:

- feature PR #58 слит в `main` коммитом `b6369c8`;
- post-merge Quality Gate run `29460395144` успешен на Python 3.12/3.13;
- общий RM-126 и технический подэтап RM-126.1 имеют статус `DONE`.

## Текущее действие

Начать RM-128 с обязательного аудита существующих topbar search, saved-profile search и Collector
entry contracts. Переиспользовать `TenderWorkspacePage`, `TenderSearchProfileRepository` и один
существующий sync/async compatibility facade; не создавать новый query repository или третий engine.
