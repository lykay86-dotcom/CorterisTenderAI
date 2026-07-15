# Текущее состояние CorterisTenderAI

Обновлено: 15 июля 2026 года.

## Активный этап

**RM-122 — анализ конкуренции**

Статус: `IN PROGRESS`

Этап назначается только после merge реализации RM-121, успешного post-merge Windows Quality
Gate на merge-коммите и merged docs-only closeout. До изменения application-кода RM-122
требуется отдельный аудит текущего анализа конкуренции и его deterministic/AI boundaries.

## Предыдущий этап

**RM-121 — финансовые риски**

Статус: `DONE`

Подтверждение:

- feature PR #45 слит в `main` коммитом `ac1cec2`;
- post-merge Quality Gate run `29416563733` успешен на Python 3.12 и 3.13;
- полный Windows suite: Python 3.12 — `1289 passed in 66.64s`, Python 3.13 —
  `1289 passed in 88.80s`;
- pure local financial policy строит versioned registry только из current verified specialized
  requirements, ТЗ и draft-contract findings;
- категории, priorities, stable IDs и actions детерминированы; generic risks и deterministic
  stop-factors не копируются;
- persisted payload v8 локально пересчитывается и сверяется, legacy v1–v7 и повреждённые данные
  обрабатываются fail-closed;
- existing UI и JSON/HTML export показывают четыре статуса, priorities, citations, warnings и
  disclaimer с безопасным escaping;
- сохранены единые provider/analyzer/service/Orchestrator/repository/UI/exporter, один production
  provider call и одна `RUNNING_AI` стадия;
- RM-107 score/recommendation и абсолютный приоритет critical stop-factor не изменены;
- CommercialEstimator сохраняет Decimal-границу, а incomplete estimate — `DATA_INSUFFICIENT` без
  вымышленных total cost, profit или margin;
- новая AI-stage, calculator, БД или миграция БД не потребовались;
- локально: target `337 passed`, full `1289 passed`, Ruff, mypy (18 файлов), secret scan,
  dependency audit и diff-check успешны;
- post-merge gate подтвердил Ruff (`515 files`), mypy (18 файлов), secret scan, smoke tests и
  dependency audit на обеих версиях Python.

## Ранее завершённый этап

**RM-120 — юридические риски**

Статус: `DONE`

Подтверждение:

- feature PR #43 слит в `main` коммитом `f2f87ff`;
- post-merge Quality Gate run `29411717306` успешен на Python 3.12 и 3.13;
- полный Windows suite: `1198 passed` на обеих версиях Python;
- pure local legal registry использует current verified specialized findings и fail-closed v7;
- RM-107 score/recommendation и critical stop-factor policy не изменены.

## Текущее действие

Провести отдельный аудит RM-122 до изменения анализа конкуренции или его
AI/deterministic contract.
