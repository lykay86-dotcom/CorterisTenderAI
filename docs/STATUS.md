# Текущее состояние CorterisTenderAI

Обновлено: 20 июля 2026 года.

## Активный этап

**RM-151 — уведомления и фоновые операции**

Статус: `IN PROGRESS`

RM-150 завершён feature PR #108 на head
`4f432cbe650c76994ba6c44f62685a20fb5ed555`, merge commit
`8d6640691ca3e0fc6a22d7e6dd2d732955e0eedd` и успешным exact merge-SHA Windows Quality Gate
run `29708473745`. Этот отдельный docs-only closeout переводит RM-150 в `DONE`. RM-151 —
единственный активный этап; RM-152–RM-200 остаются `PLANNED` и не выполняются параллельно.
RM-151 должен начаться отдельным audit-first пакетом и переиспользовать принятые
shell/navigation/theme/lifecycle, table identity/action/state, tender-detail/card и существующие
worker/controller/DI paths без создания дублирующих operation/notification owners.

## Завершённый этап

**RM-150 — современные таблицы**

Статус: `DONE`

Подтверждение:

- 35 pre-production product table sites полностью классифицированы: `migrate=11`, `keep=12`,
  `defer=12`; девять audit/contract/plan документов созданы до production-кода;
- один Qt-free immutable contract определяет stable row/column/revision identity, typed Decimal
  sort/filter, exact selection/action validation, explicit states и visible-snapshot export parity;
- один reusable Qt adapter owner и 11 representative migrations устраняют adjacent-row action
  drift; RM-107/RM-148/RM-149 owners и decision/financial/tender semantics сохранены;
- локально: focused `31 passed`, deterministic hash-seed contours `22 + 22 passed`, full pytest
  `2276 passed, 2 warnings`; secret scan, Ruff/format (`744 files`), mypy,
  offline/migration/import/composition/build/frozen smokes, benchmark и dependency audit успешны;
- 10,000-row typed Decimal sort p95 улучшен с `2295.315 ms` до `90.907 ms`; missing-text filter
  p95 `137.449 ms` остаётся ниже RM-141 historical `148.005 ms` без arbitrary timing gate;
- feature PR #108 на head `4f432cbe650c76994ba6c44f62685a20fb5ed555` слит merge commit
  `8d6640691ca3e0fc6a22d7e6dd2d732955e0eedd`;
- PR-head Quality Gate `29708327405` и exact merge-SHA push-run `29708473745` успешны на Python
  3.12/3.13; final full suites — `2276 passed, 2 warnings` на обеих версиях;
- DB/schema/migration, dependencies, provider/network/AI paths и RM-107
  score/recommendation/critical stop-factor priority не изменены.

## Ранее завершённый этап

**RM-149 — новая карточка тендера**

Статус: `DONE`

- Один Qt-free `app.tenders.detail` owner предоставляет typed registry/legacy identity, immutable
  snapshots/cards и exact action validation.
- Feature PR #106 слит merge commit `219e7c43527ca230a61de8cdeb3f191288fc3f87`.
- Exact merge-SHA Quality Gate run `29704404132` успешен на Python 3.12/3.13.

## Текущее действие

Начать RM-151 отдельным audit-first пакетом и подтвердить operation/notification owner boundaries
до production-реализации. Не начинать RM-152+ до выполнения RM-151 Definition of Done и следующего
отдельного канонического closeout.
