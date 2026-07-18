# RM-139 — локальная приёмка мониторинга источников

Дата: 18 июля 2026 года.

Статус пакета: feature acceptance и exact merge-SHA gate пройдены. Feature PR #86 слит в `main`;
этот docs-only closeout переводит RM-139 в `DONE` и активирует RM-140.

## Границы и трассируемость

- Базовый `main`: `d333e2658aacdb16f91c49c7c26ba96843a151d1`.
- Feature branch: `feat/rm-139-source-monitoring`.
- Audit/contract/plan: commit `6ad5741`.
- Expected-red contract: commit `d9b2b97`; семь collection errors отсутствующих RM-139
  production symbols подтвердили, что тесты не проходили случайно через legacy поведение.
- Production commits: `fdcb9c2`, `088e100`, `a29a978`.
- Feature PR: #86; merge commit: `41b547f67020b9645d915694c943b962b46ddc08`.
- Реализация покрывает C19 из `docs/RM-126_REQUIREMENTS.md` и не начинает RM-140.

## Принятая реализация

- Один code-owned `SourceMonitoringService` строит immutable snapshot из существующих provider
  descriptors, configuration, connection evidence, accepted Collector run/provider outcomes,
  checkpoints, schedule и C19 verification evidence.
- Connection readiness, operational run/circuit state, checkpoint freshness, C19 verification и
  schedule показаны раздельно; отсутствие evidence не превращается в успех.
- Freshness policy `source-monitoring-v1` использует aware UTC, проверяет future skew и задаёт
  явные TTL: connection evidence — 24 часа, inactive checkpoint — 24 часа, active checkpoint —
  `2 × schedule + 5 минут` в диапазоне 1–48 часов, C19 verification — 30 дней.
- Existing `ProviderHealthMonitor` восстанавливается из принятых persisted outcomes; второй
  circuit breaker не создан. Cooldown использует monotonic runtime boundary и не доверяет
  отрицательному либо неограниченному wall-clock остатку.
- Read-only history/checkpoint/verification reads не создают schema и не выполняют migration;
  Collector schema остаётся v14, health JSON — v2.
- Existing notification repository/service переиспользованы. Уведомления создаются только для
  переходов, учитывают `notify_failures`, имеют стабильный deduplication ID и не раскрывают raw
  exception, URL, credential или response body.
- Existing provider manager dialog расширен безопасными полями monitoring snapshot; прежние
  enable/disable/check actions сохранены. Проверка подключения отклоняется во время активной
  Collector session. Startup network I/O не добавлен.
- RM-107 score/recommendation/hard-exclusion и critical stop-factor priority не изменены; AI не
  участвует в вычислении monitoring state.

## Проверки

- Baseline owner contour до production changes: `44 passed in 13.85s`.
- RM-139 focused tests после реализации: `14 passed`; circuit/run-session integration:
  `5 passed in 6.72s`; пять повторов circuit/notification contour — все успешны.
- Neighbor regression contour: `53 passed in 14.44s`; UI compatibility rerun:
  `9 passed in 8.58s`.
- Финальный full pytest: `1908 passed, 2 warnings in 120.62s`.
- `ruff check .` — успешно.
- `ruff format . --check` — `620 files already formatted`.
- Repository secret scan — успешно.
- Required mypy contour — `Success: no issues found in 20 source files`; RM-139 owner contour —
  `Success: no issues found in 3 source files`.
- Workflow-derived smokes: offline `2 passed`, migration `5 passed`, composition `1 passed`,
  build/release `6 passed`, public import — успешно.
- Dependency audit: `No known vulnerabilities found` (editable package пропущен самим
  `pip-audit`).
- `git diff --check` после docs update — успешно.

Два предупреждения full pytest принадлежат существующему openpyxl contour и не являются новой
ошибкой RM-139. Более широкий legacy mypy запуск обнаруживает существующие ошибки вне обязательного
и RM-139 owner contours; их исправление не входит в scope этого этапа.

## GitHub acceptance

- PR Quality Gate run `29623757948`: Python 3.12 —
  `1908 passed, 2 warnings in 82.11s`; Python 3.13 —
  `1908 passed, 2 warnings in 109.04s`.
- Exact merge-SHA push run `29624355650` на
  `41b547f67020b9645d915694c943b962b46ddc08`: Python 3.12 —
  `1908 passed, 2 warnings in 120.67s`; Python 3.13 —
  `1908 passed, 2 warnings in 133.34s`.
- В обоих run успешны secret scan, Ruff check/format, required mypy, workflow smokes, full pytest
  и dependency audit. Неблокирующее Node.js 20/24 annotation относится к official actions и не
  изменяет итог gate.

После merge feature PR и успешного exact merge-SHA gate RM-139 соответствует Definition of Done.
Этот отдельный docs-only closeout фиксирует evidence, переводит RM-139 в `DONE` и назначает RM-140
единственным `IN PROGRESS`; RM-141–RM-200 остаются `PLANNED`.
