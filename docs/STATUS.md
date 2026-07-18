# Текущее состояние CorterisTenderAI

Обновлено: 18 июля 2026 года.

## Активный этап

**RM-143 — новая дизайн-система**

Статус: `IN PROGRESS`

RM-142 завершён feature PR #92, merge commit
`246734d2f3b700392c6682c7bcfb5d6ab1469ec5` и успешным exact merge-SHA Windows Quality Gate
run `29659317641`. RM-143 — единственный активный этап; RM-144–RM-200 остаются `PLANNED` и не
выполняются параллельно. RM-143 начинается отдельным audit-first пакетом без расширения scope в
RM-144+.

## Завершённый этап

**RM-142 — новая информационная архитектура**

Статус: `DONE`

Подтверждение:

- создан один immutable typed route registry и один navigation owner на существующем
  `DashboardLayout`, без второго shell/router/page stack;
- primary navigation сведена к Dashboard, Tenders и одному Business Workflow; false peer
  placeholders устранены, mature embedded/modal workflows и legacy aliases сохранены;
- allowlisted context, bounded in-memory history, back/return, exact tender ID, workflow
  filters/stable selection и focus-origin restoration покрыты offline tests;
- локально: secret scan, Ruff/format (`644 files`), mypy, focused (`37 passed`), соседний UI contour
  (`68 passed`) и full pytest (`1983 passed, 2 warnings`) успешны;
- feature PR #92 слит в `main` merge commit
  `246734d2f3b700392c6682c7bcfb5d6ab1469ec5`;
- финальный PR Quality Gate run `29659175137` и exact merge-SHA run `29659317641` успешны на
  Python 3.12/3.13; dependency audit и все обязательные jobs завершились `success`;
- DB/schema/migration, RM-107 scoring/recommendation/critical stop-factor priority и RM-143+
  application scope не изменены.

## Ранее завершённый этап

**RM-141 — аудит UI**

Статус: `DONE`

- Audit PR #90 слит в `main` коммитом `a2e8d052`.
- Exact merge-SHA Quality Gate run `29655095879` успешен на Python 3.12/3.13.
- UI inventory, findings и handoff RM-142–RM-155 сохранены.

## Текущее действие

Начать RM-143 с отдельного audit-first пакета, сохраняя route/navigation contract RM-142 и handoff
`RM-141_REDESIGN_HANDOFF.md`. Не начинать RM-144+ и не изменять business/data ownership или
deterministic decision/scoring/critical stop-factor priority без отдельного аудита.
