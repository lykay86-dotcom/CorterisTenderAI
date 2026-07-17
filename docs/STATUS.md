# Текущее состояние CorterisTenderAI

Обновлено: 17 июля 2026 года.

## Активный этап

**RM-137 — отраслево-независимая нормализация**

Статус: `IN PROGRESS`

RM-136 завершён после audit-first реализации, feature merge и успешного exact
merge-SHA Windows Quality Gate. RM-137 — единственный активный этап;
RM-138–RM-200 остаются `PLANNED` и не выполняются параллельно.

## Завершённый этап

**RM-136 — тест подключения**

Статус: `DONE`

Подтверждение:

- audit/plan зафиксированы commit `f4bb93a`, expected-red contract — `31da549`;
- existing health evidence повышен до schema v2, provider settings — до schema v6;
  migration, byte-exact backup, atomic replace и revision-aware binding сохранены;
- explicit manual-provider health check использует bounded HTTP/RSS/FTP/FTPS transport,
  all-answer DNS classification, pinned TLS, redirect/unsafe-target rejection и runtime-only
  credential resolution;
- current `PASSED/HEALTHY` evidence с TTL 15 минут требуется и для explicit enablement,
  и для каждого admission; health success не включает provider автоматически;
- локально: focused `36 passed`, full pytest `1859 passed, 2 warnings`; secret scan,
  Ruff/format, mypy, workflow smokes, dependency audit и diff-check успешны;
- feature PR #78 слит в `main` merge commit
  `d84288ab74553e500ad9eaf9f51a091404490551`;
- PR Quality Gate run `29606049619` успешен: Python 3.12 —
  `1859 passed, 2 warnings in 142.75s`, Python 3.13 —
  `1859 passed, 2 warnings in 87.96s`;
- exact merge-SHA run `29606492310` успешен: Python 3.12 —
  `1859 passed, 2 warnings in 93.95s`, Python 3.13 —
  `1859 passed, 2 warnings in 103.55s`; все обязательные jobs завершились `success`;
- deterministic decision/scoring/critical stop-factor, built-in provider flow, legacy bytes
  и credential boundary сохранены; RM-137 получает только normalization scope.

## Ранее завершённый этап

**RM-135 — безопасный конструктор адаптера**

Статус: `DONE`

- Feature PR #76 слит в `main` коммитом `306b209`.
- Exact merge-SHA Quality Gate run `29586643112` успешен на Python 3.12/3.13.
- Manual adapter contract, non-runnable lifecycle и deterministic boundaries сохранены.

## Текущее действие

Начать RM-137 с отдельного audit-first пакета и канонического entry gate.
Не начинать RM-138+ и не изменять deterministic decision/scoring/critical stop-factor priority
до отдельно утверждённого normalization contract.
