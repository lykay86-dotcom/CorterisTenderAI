# Текущее состояние CorterisTenderAI

Обновлено: 20 июля 2026 года.

## Активный этап

**RM-150 — современные таблицы**

Статус: `IN PROGRESS`

RM-149 завершён feature PR #106 на head
`d7a6896b9fa2daf94e760b0fcf1ae030089adcb1`, merge commit
`219e7c43527ca230a61de8cdeb3f191288fc3f87` и успешным exact merge-SHA Windows Quality Gate
run `29704404132`. Этот отдельный docs-only closeout переводит RM-149 в `DONE`. RM-150 —
единственный активный этап; RM-151–RM-200 остаются `PLANNED` и не выполняются параллельно.
RM-150 должен начаться отдельным audit-first пакетом и переиспользовать принятые
shell/navigation/theme/lifecycle, tender-detail/card, RM-146 chart, RM-147 analytics и RM-148
financial contracts без создания дублирующих owners.

## Завершённый этап

**RM-149 — новая карточка тендера**

Статус: `DONE`

Подтверждение:

- один Qt-free `app.tenders.detail` owner определяет typed registry/legacy identity, immutable
  detail/card contracts, bounded read-only assembler, reason codes, action catalog, deterministic
  fingerprint и fail-closed HTTPS/stale-action policy;
- native RM-143 detail/card widgets интегрированы с exact registry и persisted-search surfaces;
  RM-147 drill-down переиспользует тот же registry owner, а legacy Dashboard не получает
  выдуманный ORM↔registry bridge; RM-148 остаётся владельцем price/currency projection;
- локально: focused `36 passed`, neighboring `358 passed`, full pytest
  `2245 passed, 2 warnings`; secret scan, Ruff/format (`735 files`), mypy,
  offline/migration/import/composition/build/frozen smokes, benchmark и dependency audit успешны;
- feature PR #106 на head `d7a6896b9fa2daf94e760b0fcf1ae030089adcb1` слит merge commit
  `219e7c43527ca230a61de8cdeb3f191288fc3f87`;
- PR-head Quality Gate `29703943804` и exact merge-SHA push-run `29704404132` успешны на Python
  3.12/3.13; final full suites — `2245 passed, 2 warnings` на обеих версиях;
- первые Python 3.12 попытки обоих runs завершились native Windows heap/access violation без test
  assertion; повтор того же неизменного SHA прошёл полностью;
- DB/schema/migration, dependencies, provider/network/AI paths, generic-table scope и RM-107
  score/recommendation/critical stop-factor priority не изменены.

## Ранее завершённый этап

**RM-148 — финансовая аналитика**

Статус: `DONE`

- Один Qt-free `app.financial` owner предоставляет finite Decimal, explicit currency/unit/state,
  derived metrics, immutable snapshots и exact projections.
- Feature PR #104 слит merge commit `1116216cf00fc74dad2b870617c496242cd659c2`.
- Exact merge-SHA Quality Gate run `29699279963` успешен на Python 3.12/3.13.

## Текущее действие

Слить этот docs-only closeout, после чего начать RM-150 отдельным audit-first пакетом. Не начинать
production-реализацию RM-150 до его аудита и не начинать RM-151+ до выполнения RM-150 Definition
of Done и следующего отдельного канонического closeout.
