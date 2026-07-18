# Текущее состояние CorterisTenderAI

Обновлено: 19 июля 2026 года.

## Активный этап

**RM-144 — новый каркас приложения**

Статус: `IN PROGRESS`

RM-143 завершён feature PR #94, merge commit
`c8d111f3db615dd3c21c231bf265bb00093c65bd` и успешным exact merge-SHA Windows Quality Gate
run `29663124774`. RM-144 — единственный активный этап; RM-145–RM-200 остаются `PLANNED` и не
выполняются параллельно. RM-144 должен начаться отдельным audit-first пакетом и сохранить
дизайн-систему RM-143, route/navigation contract RM-142 и существующие business/data owners.

## Завершённый этап

**RM-143 — новая дизайн-система**

Статус: `DONE`

Подтверждение:

- `app.ui.theme` остаётся единственным owner Corteris Design System v1; immutable tokens,
  одинаковые dark/light roles и deterministic sRGB contrast policy покрыты тестами;
- semantic icon registry использует локальные original SVG assets, bounded cache и безопасный
  fallback; Sidebar/TopBar подключены без изменения route IDs/order/availability/context;
- button/card/status/data/form contracts и offline component gallery покрывают обе темы,
  focus/keyboard/loading/disabled/error и lifecycle stability без вычисления business status;
- exact migration matrix покрывает 45 baseline local-style sites; итоговый guard:
  `matrix=45`, `styles=43`, `violations=0`, literal colours outside theme — 0;
- локально: secret scan, Ruff/format (`662 files`), mypy, RM-143 contract (`76 passed`), соседний UI
  contour (`40 passed`) и full pytest (`2059 passed, 2 warnings`) успешны; dependency audit не
  обнаружил известных уязвимостей;
- feature PR #94 на head `1915be92dc0a9e0b9c1edc0bb5955abf6c94f948` слит merge commit
  `c8d111f3db615dd3c21c231bf265bb00093c65bd`;
- PR-head Quality Gate `29662950338` и exact merge-SHA run `29663124774` успешны на Python
  3.12/3.13; full suite, dependency audit и все обязательные jobs завершились `success`;
- DB/schema/migration, runtime dependencies, RM-107 score/recommendation/critical stop-factor
  priority и RM-144+ application scope не изменены.

## Ранее завершённый этап

**RM-142 — новая информационная архитектура**

Статус: `DONE`

- Один immutable typed route registry и существующий `DashboardLayout` остаются единственными
  navigation metadata/stack owners.
- Feature PR #92 слит merge commit `246734d2f3b700392c6682c7bcfb5d6ab1469ec5`.
- Exact merge-SHA Quality Gate run `29659317641` успешен на Python 3.12/3.13.

## Текущее действие

Начать RM-144 с отдельного audit-first пакета. Не начинать RM-145+, не создавать второй
theme/navigation/business owner и не изменять deterministic decision/scoring/critical stop-factor
priority без отдельного аудита и Definition of Done.
