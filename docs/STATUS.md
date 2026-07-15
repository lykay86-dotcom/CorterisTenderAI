# Текущее состояние CorterisTenderAI

Обновлено: 16 июля 2026 года.

## Активный этап

**RM-126.1 — аудит и укрепление текущего провайдера ЕИС**

Статус: `IN PROGRESS`

Технический подэтап переоткрыт по явному подтверждению владельца проекта после получения позднего
дополнения к RM-126. Он укрепляет существующий `AsyncEisTenderProvider` и общую Collector-цепочку,
не создавая второй Collector, HTTP client, tender model, persistence root, scoring или analysis
workflow. RM-127 временно возвращён в `PLANNED` и не выполняется параллельно.

## Завершённая часть активного этапа

**RM-126 — общий аудит раздела Тендеры**

Статус: `AUDIT DONE`; общий RM-126 переоткрыт до завершения RM-126.1

Подтверждение:

- audit PR #55 (`docs(rm-126): audit tenders section`) слит в `main` коммитом `f09d07e`
  (`f09d07ebb1a15acb42279d3b8f7e0393c8d84afc`);
- post-merge Quality Gate run `29453928900` успешен: Python 3.12 —
  `1496 passed in 76.46s`, Python 3.13 — `1496 passed in 157.55s`;
- на обеих версиях прошли Ruff check/format (`523 files`), mypy (20 файлов), repository secret
  scan, offline/migration/import/composition/build smoke tests и dependency audit;
- созданы проверяемые `RM-126_AUDIT.md`, `RM-126_REQUIREMENTS.md` и execution plan; production-код,
  зависимости, схема БД и migrations не изменены;
- приняты D-01–D-10: modern tender page, async Collector как целевой search boundary с временным
  sync facade, единый provider/settings/keyring/profile/normalization/persistence contract и strict
  Decimal/aware-time policy;
- C1–C20 распределены по RM-127–RM-140 без параллельной Collector roadmap;
- HIGH handoff: embedded legacy UI, два search orchestration path, отсутствие общего tender
  shutdown и неоднородная timezone policy;
- локальная приёмка audit branch: target `395 passed in 33.99s`, full
  `1496 passed in 61.27s`; Ruff, mypy, secret scan, smoke tests, dependency audit и diff-check успешны.

## Ранее завершённый этап

**RM-125 — стабилизация AI-платформы**

Статус: `DONE`

Подтверждение:

- feature PR #53 слит в `main` коммитом `bdceb70`;
- post-merge Quality Gate run `29450245855` успешен на Python 3.12 и 3.13;
- полный Windows suite: Python 3.12 — `1496 passed in 95.46s`, Python 3.13 —
  `1496 passed in 61.69s`;
- immutable AI execution contract, deterministic decision и critical stop-factor priority сохранены.

## Текущее действие

До изменения application-кода выполнить отдельный аудит текущего EIS parser/provider и создать
`docs/EIS_PARSER_STAGE_1_AUDIT.md`. После этого реализовать RM-126.1 в существующей Collector-цепочке,
пройти полный Windows Quality Gate и только затем вернуть RM-126 в `DONE` и активировать RM-127.
