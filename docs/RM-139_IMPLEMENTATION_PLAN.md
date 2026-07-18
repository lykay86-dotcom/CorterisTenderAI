# RM-139 — implementation plan мониторинга источников

Baseline: `d333e2658aacdb16f91c49c7c26ba96843a151d1`  
Branch: `feat/rm-139-source-monitoring`

## Phase A — audit gate

- Зафиксировать audit, contract и этот plan отдельным docs-only commit.
- Не менять application-код до commit.

## Phase B — characterization/expected-red

- Добавить focused tests immutable ordering/dimensions/revision и strict time boundaries.
- Зафиксировать current fresh-runtime circuit loss и expected target hydration.
- Добавить contracts read-only persistence, transitions/dedup, passive no-network и Qt rendering.
- Expected-red должен падать только из-за отсутствующих RM-139 symbols/behavior.

## Phase C — pure projection

- Создать `app/tenders/collector/source_monitoring.py` с frozen models, closed enums,
  `SourceMonitoringPolicy` и service-owned revision.
- Реализовать safe aware UTC parsing, freshness, attention order и deterministic aggregation.
- Не импортировать Qt и не выполнять I/O внутри pure policy functions.

## Phase D — existing persistence/circuit

- Добавить `ProviderRunOutcomeRecord`, read-only ordered provider outcome query и
  `list_checkpoints()` в `CollectorStateRepository` без initialize/write/schema bump.
- Сделать latest C19 read path no-create/read-only.
- Добавить explicit restore API к existing `ProviderHealthMonitor` и hydrate fresh per-run runtime
  из compatible safe run history before provider dispatch.
- Сохранить one-run runtime close и RM-138 terminal semantics.

## Phase E — transitions/operations

- Расширить existing notification service deterministic source transitions; публиковать через
  existing repository/controller.
- Initial/passive repeated refresh не создаёт alerts.
- Отклонять explicit health check во время active Collector; второй worker/guard не создавать.

## Phase F — UI

- Передавать snapshot из `TenderSearchUiController` в existing provider dialog.
- Показать dimensions отдельными колонками/details со stable objectNames.
- Refresh остаётся local/read-only; existing enable/config/credential/check actions сохраняются.

## Phase G — acceptance

- Focused RM-139, neighbor RM-136/138/checkpoint/scheduler/notification/UI contours.
- Five-cycle deterministic circuit/time/transition tests.
- Workflow-equivalent secret scan, Ruff/format, mypy, offline/migration/import/composition/build,
  full pytest, dependency audit и diff-check.
- Записать точные результаты в `docs/RM-139_ACCEPTANCE.md` и roadmap docs, не переводя RM-139 в
  `DONE` до feature merge, exact merge-SHA Windows gate и отдельного closeout PR.

## Stop conditions

Остановиться при необходимости нового monitor store/prober/scheduler, DB migration без нового
persisted field, ослабления RM-138 cancellation, startup network, raw secret/error persistence,
изменения deterministic decision authority или scope RM-140.
