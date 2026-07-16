# Текущее состояние CorterisTenderAI

Обновлено: 16 июля 2026 года.

## Активный этап

**RM-130 — сохранённые поисковые профили**

Статус: `IN PROGRESS`

RM-129 завершён после audit-first реализации, feature merge и успешного exact-SHA post-merge
Windows Quality Gate. RM-130 назначен единственным активным этапом; RM-131–RM-200 остаются
`PLANNED` и не выполняются параллельно.

## Завершённый этап

**RM-129 — универсальные бизнес-профили**

Статус: `DONE`

Подтверждение:

- audit/plan зафиксированы docs-only commit `ddb8427`, expected-red contract — `3331131`;
- один existing `CompanyCapabilityProfileRepository` сохраняет schema v2 в прежний JSON path,
  безопасно мигрирует v1 in memory и typed различает missing/current/migrated/corrupt/future;
- content-bound confirmation exact-связывает все decision facts с SHA-256; explicit currency,
  decimal strings и aware UTC timestamps сохраняются без guessed facts;
- pure frozen `BusinessCapabilityProjection` является общей confirmed-facts boundary для manual
  score, automatic Collector и `StopFactorEngine`; unconfirmed capabilities fail closed;
- existing runtime/controller/dialog используют один repository owner, domain `confirm()` и честные
  load statuses без auto-save;
- score keys/maxima/explanations/bands, matching catalog, RM-107 decision и абсолютный приоритет
  critical stop-factor не изменены; DB/migrations/network/dependencies/AI/RM-130 scope не затронуты;
- локально: focused `76 passed in 5.25s`, neighbor `38 passed in 6.85s`, full pytest
  `1623 passed in 70.35s`; все workflow-equivalent gates успешны;
- feature PR #64 слит в `main` коммитом `f9b43c3`
  (`f9b43c37bb5c7e631e4851cde2b39c1178d34239`);
- PR Quality Gate run `29522220375` успешен: Python 3.12 — `1623 passed in 164.70s`,
  Python 3.13 — `1623 passed in 63.03s`;
- exact-SHA post-merge run `29522737754` успешен: Python 3.12 —
  `1623 passed in 69.59s`, Python 3.13 — `1623 passed in 103.67s`;
- на обеих версиях прошли secret scan, Ruff check/format (`549 files`), mypy (20 файлов),
  offline/migration/import/composition/build smoke и dependency audit.

## Ранее завершённый этап

**RM-128 — единая панель поиска**

Статус: `DONE`

Подтверждение:

- feature PR #62 слит в `main` коммитом `a67f5df`;
- post-merge Quality Gate run `29499519358` успешен на Python 3.12/3.13;
- единая search panel и existing-controller async Collector path имеют статус `DONE`.

## Текущее действие

Начать RM-130 только с обязательного аудита существующего `TenderSearchProfileRepository`, schema
`search_profiles.json`, built-in/custom protection и current unified/manual/scheduled call sites. Не
создавать второй saved-search repository и не смешивать search profiles с business capability.
