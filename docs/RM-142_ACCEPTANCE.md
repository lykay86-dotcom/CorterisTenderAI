# RM-142 — приёмка новой информационной архитектуры

Дата локальной приёмки: 18 июля 2026 года.

Статус пакета: feature implementation, локальные gates, feature PR и первый Windows Quality Gate
пройдены; финальный PR-head gate, merge, exact merge-SHA gate и отдельный docs-only closeout ещё
не выполнены. До этих шагов RM-142 остаётся единственным `IN PROGRESS`, а RM-143+ — `PLANNED`.

## Вход и трассируемость

- Канонический baseline `origin/main`: `999354c892326765792308b2c40a0c8b7236f717`.
- RM-141 audit PR #90: merge `a2e8d0528a1b9c6378a543a5c9f2c5b762483c63`, exact run
  `29655095879`, `success` на Python 3.12/3.13.
- RM-141 closeout PR #91: merge `999354c892326765792308b2c40a0c8b7236f717`, exact run
  `29655615482`, `success` на Python 3.12/3.13.
- Feature branch/worktree: `feat/rm-142-information-architecture`, `.worktrees/rm142`.
- Audit/contract/plan: `985601d`.
- Characterization: `153ab5f`; `3 passed in 34.04s`.
- Expected-red: `535db20`; семь ожидаемых collection failures только из-за отсутствующих
  RM-142 contracts, без fixture/environment failures.
- Typed route registry: `27d98f6`.
- Canonical navigation owner: `4995a2f`.
- Workflow navigation state: `c8893ea`.
- Production shell integration: `15e7bb7`.
- Offline journey/security coverage: `6f0331e`.
- Feature acceptance documentation: `4b4e6bc`.
- Feature PR: #92.
- PR Quality Gate run `29658950250` на head `4b4e6bc60c793838c56e2c9448bed742c674150c`:
  `success`, Python 3.12 за 5:36 и Python 3.13 за 5:22.

Entry gate подтвердил RM-141 `DONE`, RM-142 как единственный `IN PROGRESS`, RM-143–RM-200
`PLANNED`, наличие handoff и отсутствие параллельной реализации следующего этапа. Baseline full
pytest от `origin/main`: `1946 passed, 2 warnings in 161.36s`.

## Принятая архитектура

- `app/ui/navigation/` содержит один immutable typed contract: `RouteId`, `RouteKind`,
  `RouteAvailability`, `RouteSpec`, `RouteContext`, `RouteRequest`, `RouteResult` и
  `NavigationSnapshot`.
- `DEFAULT_ROUTE_REGISTRY` — единственный источник stable IDs, hierarchy, title, order,
  availability, context allowlist, journey IDs и legacy aliases.
- `DashboardLayout` — единственный production navigation owner и владелец одного существующего
  `QStackedWidget`; второй shell/router/stack не создавался.
- Primary Sidebar содержит только Dashboard, Tenders и единый Business Workflow. Пять прежних
  ложных peer placeholders удалены из production composition.
- Proposal, estimate и project оформлены как typed child intents одной workflow-области. Две
  физические страницы временно сохранены без переноса lifecycle ownership, что соответствует
  границе RM-144.
- Legacy keys `dashboard`, `tenders`, `ai`, `quotes`, `estimates`, `documents`, `clients`,
  `analytics`, `settings` имеют однозначную disposition. `clients`/`analytics` возвращают typed
  `UNAVAILABLE`, а не изображают готовый экран.
- AI и settings открывают существующие embedded tabs `TenderWorkspacePage`. Documents,
  scheduler и notifications используют существующие controller/QAction owners; topbar и shortcuts
  не создают вторых действий.
- Dashboard quick actions, global search и tender deep link проходят через `RouteRequest`.
  Missing tender ID возвращает safe failure и не меняет текущий route.

## Контекст, возврат и безопасность

- `RouteContext` принимает только bounded allowlisted presentation scalars; QWidget, repository,
  controller, domain record, credential и произвольный mapping запрещены.
- Tender identity переносится как точная строка без преобразования или угадывания.
- `NavigationHistory` ограничена 32 immutable snapshots, хранится только в памяти, coalesces
  consecutive duplicates и не удерживает runtime objects.
- Перед уходом workflow page предоставляет owner-controlled snapshot search/kind/status/archive и
  stable record ID. Back/return восстанавливает exact filter state; отсутствующая или вышедшая из
  scope запись даёт explicit no selection, а не соседнюю строку.
- Focus origin хранится как bounded object-name token без strong QWidget reference. Отсутствующий
  origin безопасно приводит к page-level fallback.
- Unknown, invalid, planned и unavailable routes возвращают fixed safe result без raw input,
  exception, path, URL, traceback или secret-shaped material.
- Route resolution, composition и acceptance journeys работают offline; navigation не читает
  keyring, не открывает socket, не пишет DB и не запускает business/AI calculation.

UI-141-001 закрыт устранением false primary peers и registry-driven availability. UI-141-002
закрыт единой workflow hierarchy, typed intents и stable state round trip. RM-107 score,
recommendation и critical stop-factor priority не изменялись.

## Локальные проверки

Финальный локальный SHA реализации и journey tests: `6f0331e`.

- RM-142 focused/characterization: `37 passed in 15.60s`.
- Соседний RM-127/128/140, Dashboard, workflow, AI, scheduler/notifications contour:
  `68 passed in 13.43s`.
- Full pytest: `1983 passed, 2 warnings in 165.65s`.
- Repository secret scan: passed.
- `ruff check .`: passed.
- `ruff format . --check`: `644 files already formatted`.
- Required mypy contour: `Success: no issues found in 20 source files`.
- `git diff --check`: passed.

Два warnings принадлежат прежнему openpyxl contour
`test_rm132_legacy_credentials_handoff.py`: unsupported extension и conditional formatting. Новых
warnings RM-142 нет.

Локальный `pip-audit --skip-editable` не получил доступ к PyPI из sandbox. Повтор с внешним
доступом был отклонён политикой среды из-за передачи dependency metadata; обход не выполнялся.
Dependency audit успешно выполнен в PR run `29658950250` на Python 3.12 и 3.13. Его повтор на
финальном PR head и exact merge SHA остаётся обязательным до closeout.

## Database, границы и rollback

- DB/schema/migration: не требуются и не изменялись.
- Новые repository, service, controller, search engine, AI pipeline, background worker или timer не
  создавались.
- RM-143 design system, RM-144 lifecycle extraction и прочие RM-143+ не реализовывались.
- Rollback: revert feature commits/feature merge к baseline `999354c`; данные, DB, settings,
  credentials, schedules и notification state не преобразовывались и не требуют downgrade.
  Legacy aliases сохранены для возврата прежнего shell wiring.

## Оставшиеся обязательные gates

RM-142 нельзя признать `DONE`, пока не выполнены оставшиеся пункты:

1. Финальный PR-head Quality Gate после этого evidence-коммита.
2. Merge feature PR в `main` и фиксация точного merge SHA.
3. Exact merge-SHA Quality Gate `success` на Python 3.12 и 3.13.
4. Отдельный docs-only closeout PR: RM-142 → `DONE`, RM-143 → единственный `IN PROGRESS`,
   обновление `ROADMAP.md`, `STATUS.md`, `ROADMAP_HISTORY.md` и этого acceptance-файла.

Текущий DoD verdict: локальная feature-приёмка и первый PR gate пройдены;
final-head/merge/exact-SHA/closeout gates ожидаются, поэтому этап остаётся `IN PROGRESS`.
