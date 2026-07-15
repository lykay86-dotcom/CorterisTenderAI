# Текущее состояние CorterisTenderAI

Обновлено: 16 июля 2026 года.

## Активный этап

**RM-127 — новая структура вкладок**

Статус: `IN PROGRESS`

Этап следует принятому в RM-126 решению D-01: modern shell владеет единственной tender page,
а существующие legacy widgets/actions извлекаются поэтапно без второго main window, нового search
runtime, provider catalog, persistence root или analysis workflow. Application-код RM-127 можно
начинать только после merge этого docs-only closeout и успешного финального Windows Quality Gate.

## Предыдущий этап

**RM-126 — аудит раздела Тендеры**

Статус: `DONE`

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

После merge closeout и зелёного финального Quality Gate начать RM-127 только с изоляции tender page
по D-01 и handoff-контракту `docs/RM-126_REQUIREMENTS.md`.
