# Текущее состояние CorterisTenderAI

Обновлено: 18 июля 2026 года.

## Активный этап

**RM-142 — новая информационная архитектура**

Статус: `IN PROGRESS`

RM-141 завершён audit-only PR #90, merge commit
`a2e8d0528a1b9c6378a543a5c9f2c5b762483c63` и успешным exact merge-SHA Windows Quality Gate
run `29655095879`. RM-142 — единственный активный этап; RM-143–RM-200 остаются `PLANNED` и не
выполняются параллельно. Реализация RM-142 начинается только с его audit-first entry gate и
handoff из `RM-141_REDESIGN_HANDOFF.md`.

## Завершённый этап

**RM-141 — аудит UI**

Статус: `DONE`

Подтверждение:

- шесть обязательных audit-документов и два read-only deterministic scripts зафиксировали
  composition, inventory, journeys, findings, redesign handoff и acceptance без production change;
- инвентаризированы 68 UI modules / 28 910 строк и 97 UI/PySide6 test modules;
- зарегистрированы 17 findings: P0 — 0, P1 — 0, P2 — 16, P3 — 1; каждый actionable finding
  назначен ровно одному RM из RM-142–RM-155;
- локально: secret scan, Ruff/format (`632 files`), mypy, mandatory selection (`14 passed`),
  UI contour (`302 passed, 2 warnings`) и full pytest (`1946 passed, 2 warnings`) успешны;
- audit PR #90 слит в `main` merge commit
  `a2e8d0528a1b9c6378a543a5c9f2c5b762483c63`;
- PR Quality Gate run `29654916158` и exact merge-SHA run `29655095879` успешны на Python
  3.12/3.13; dependency audit и все обязательные jobs завершились `success`;
- `app/`, dependencies, DB schema/migrations, navigation/theme, scoring/recommendation/critical
  stop-factor priority не изменены; RM-142+ в audit PR не реализовывались.

## Ранее завершённый этап

**RM-140 — стабилизация поиска**

Статус: `DONE`

- Feature PR #88 слит в `main` коммитом `8c09ca6`.
- Exact merge-SHA Quality Gate run `29651986321` успешен на Python 3.12/3.13.
- Search lifecycle и deterministic decision boundaries сохранены.

## Текущее действие

Начать RM-142 с отдельного audit-first пакета, канонического entry gate и handoff
`RM-141_REDESIGN_HANDOFF.md`. Не начинать RM-143+ и не изменять business/data ownership или
deterministic decision/scoring/critical stop-factor priority без отдельного аудита.
