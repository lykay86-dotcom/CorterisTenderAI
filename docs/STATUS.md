# Текущее состояние CorterisTenderAI

Обновлено: 19 июля 2026 года.

## Активный этап

**RM-149 — новая карточка тендера**

Статус: `IN PROGRESS`

RM-148 завершён feature PR #104, merge commit
`1116216cf00fc74dad2b870617c496242cd659c2` и успешным exact merge-SHA Windows Quality Gate
run `29699279963`. RM-149 — единственный активный этап; RM-150–RM-200 остаются `PLANNED` и не
выполняются параллельно. RM-149 должен начаться отдельным audit-first пакетом и переиспользовать
принятые shell/navigation/theme/lifecycle, tender source-of-truth, RM-146 chart, RM-147 analytics и
RM-148 financial contracts без создания дублирующих owners.

Feature-пакет RM-149 локально реализован и готов к feature PR: введены typed registry/legacy
identity, immutable `tender-detail-v1`/`tender-card-v1`, один read-only assembler, native reusable
detail/card widgets, versioned action policy и exact registry/search/analytics integrations.
Локально: focused `36 passed`, neighboring `358 passed`, full pytest `2245 passed, 2 warnings`;
Ruff/format, mypy, secret scan, offline/migration/composition/build/frozen smokes, dependency audit и
benchmark 0/1/100/1,000/10,000 успешны. RM-149 остаётся `IN PROGRESS` до feature merge, exact
merge-SHA Windows gate и отдельного docs-only closeout.

## Завершённый этап

**RM-148 — финансовая аналитика**

Статус: `DONE`

Подтверждение:

- один Qt-free `app.financial` owner определяет finite Decimal, explicit RUB/currency, units,
  value states, HALF_UP rounding, derived revenue margin, immutable metrics/snapshots и exact
  JSON/CSV projections;
- existing workflow repository эволюционирован до explicit schema v3 fixed-point strings;
  controlled v2→v3 migration имеет dry-run, exact safety bytes/hash, validation, fsync, atomic
  replace, all-record readback и rollback без silent ordinary-read rewrite;
- workflow table/detail/editor/audit, Dashboard, RM-147 analytics, RM-146 chart/accessibility,
  JSON/CSV/XLSX, import, backup/restore и health используют общий exact contract;
- локально: focused `38 passed`, XLSX contour `16 passed`, full pytest
  `2209 passed, 2 warnings`; secret scan, Ruff/format (`722 files`), mypy, workflow smokes,
  frozen/build и dependency audit успешны;
- feature PR #104 на head `7af94361f47660a44256751126a5871b34851202` слит merge commit
  `1116216cf00fc74dad2b870617c496242cd659c2`;
- PR-head Quality Gate `29698349596` и exact merge-SHA run `29699279963` успешны на Python
  3.12/3.13; exact full suites — `2209 passed, 2 warnings` на обеих версиях;
- dependency, FX/network/provider/AI paths, second repository/chart/route, RM-149 card scope и
  RM-107 score/recommendation/critical stop-factor priority не изменены.

## Ранее завершённый этап

**RM-147 — аналитика тендеров**

Статус: `DONE`

- Один Qt-free owner `app.tenders.analytics` предоставляет immutable aware query/snapshot,
  deterministic aggregation, provenance/partial states и exact export contracts.
- Feature PR #102 слит merge commit `d85cf8c99f8ee72279bbb8054942a0f4d5675ac2`.
- Exact merge-SHA Quality Gate run `29693165086` успешен на Python 3.12/3.13.

## Текущее действие

Опубликовать feature PR RM-149, получить Windows Python 3.12/3.13 PR-head gate, затем после merge
проверить exact merge-SHA gate. Не начинать RM-150+ и не переводить RM-149 в `DONE` до отдельного
docs-only closeout.
