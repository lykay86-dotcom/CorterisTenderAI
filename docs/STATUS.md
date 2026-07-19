# Текущее состояние CorterisTenderAI

Обновлено: 19 июля 2026 года.

## Активный этап

**RM-147 — аналитика тендеров**

Статус: `IN PROGRESS`

RM-146 завершён feature PR #100, merge commit
`e09af67931c3a63874e259bed08efc5ce3a14284` и успешным exact merge-SHA Windows Quality Gate
run `29686798140`. RM-147 — единственный активный этап; RM-148–RM-200 остаются `PLANNED` и не
выполняются параллельно. RM-147 должен начаться отдельным audit-first пакетом, определить truthful
tender metrics/intervals/timezone/aggregation/drill-down и переиспользовать chart contracts RM-146,
KPI/evidence contracts RM-145 и deterministic decision/business/data owners.

## Завершённый этап

**RM-146 — интерактивные графики**

Статус: `DONE`

Подтверждение:

- один dependency-free QPainter owner `app.ui.charts` предоставляет immutable contracts,
  deterministic render plan, bar/line rendering, typed selection и semantic export path;
- восемь honest states, aware-time/Decimal/missing rules, mouse/keyboard interaction,
  complete-data accessible table и PNG/SVG/JSON/CSV exports покрыты тестами;
- six-series/1,000-render/10,000-data limits, resize/DPI behavior и isolated hidden frozen smoke
  измерены; native accessibility/DPI observations переданы RM-152;
- локально: RM-146 focused `27 passed`, соседний contour `203 passed`, full pytest
  `2123 passed, 2 warnings`; secret scan, Ruff/format (`682 files`), required/strict mypy,
  frozen/build smoke, design guard и dependency audit успешны;
- feature PR #100 на head `72118c31a31f16b524c79ee83bc82a9daf7071fb` слит merge commit
  `e09af67931c3a63874e259bed08efc5ce3a14284`;
- PR-head Quality Gate `29685966343` и exact merge-SHA run `29686798140` успешны на Python
  3.12/3.13; первый PR-head Python 3.12 job завершился native access violation без assertion,
  rerun того же SHA прошёл без изменений;
- DB/schema/migration, runtime dependencies, KPI/tender/financial semantics и RM-107
  score/recommendation/critical stop-factor priority не изменены.

## Ранее завершённый этап

**RM-145 — современный dashboard**

Статус: `DONE`

- Один immutable six-entry KPI registry сохраняет truthful source/evidence/state/action semantics,
  `Decimal` для денег и `None` для отсутствующих значений.
- Feature PR #98 слит merge commit `ac8d2662911e8a0e450fcb20677f99082187793a`.
- Exact merge-SHA Quality Gate run `29680204767` успешен на Python 3.12/3.13.

## Текущее действие

Начать RM-147 с отдельного audit-first пакета. Не начинать RM-148+, не создавать второй
chart/KPI/theme/navigation/shell/business owner и не изменять deterministic
decision/scoring/critical stop-factor priority без отдельного аудита и Definition of Done.
