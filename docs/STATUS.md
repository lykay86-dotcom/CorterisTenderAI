# Текущее состояние CorterisTenderAI

Обновлено: 15 июля 2026 года.

## Активный этап

**RM-124 — повторная проверка AI**

Статус: `IN PROGRESS`

Этап назначается только после merge реализации RM-123, успешного post-merge Windows Quality
Gate на merge-коммите и merged docs-only closeout. До изменения application-кода RM-124
требуется отдельный аудит существующего механизма повторной проверки AI, cache/retry semantics и
его deterministic/AI boundaries.

## Предыдущий этап

**RM-123 — полнота документации**

Статус: `DONE`

Подтверждение:

- feature PR #49 слит в `main` коммитом `759f015`;
- post-merge Quality Gate run `29430495132` успешен на Python 3.12 и 3.13;
- полный Windows suite: Python 3.12 — `1442 passed in 85.09s`, Python 3.13 —
  `1442 passed in 81.29s`;
- canonical inventory объединяет existing document store с latest extraction по `document_key`,
  сохраняет download failures/archive members и не раскрывает private source metadata;
- pure local documentation policy задаёт четыре статуса, stable issues/IDs/actions и не использует
  provider output как source of truth;
- persisted payload v10 локально пересчитывается и exact-сверяется, legacy v1–v9 и повреждённые
  данные обрабатываются fail-closed; duplicate JSON keys отклоняются;
- existing UI и JSON/HTML export показывают counts, coverage, inventory, issues/actions, warnings
  и disclaimer с безопасным escaping; provider `missing_documents` маркируется отдельно;
- сохранены единые provider/analyzer/service/Orchestrator/repository/UI/exporter, один production
  provider call и одна `RUNNING_AI` стадия;
- provider schema/format v4, prompt v6, citation resolver v1 и legal/financial/competition policy
  v1 не изменены; payload повышен до v10, analyzer — до v11, context — до v6;
- network/DB/filesystem/regex/money logic, чтение `raw_metadata`, legacy engine и company profile
  в pure policy не добавлялись;
- RM-107 score/recommendation и абсолютный приоритет critical stop-factor не изменены;
- новая AI-stage, repository, таблица, колонка или миграция БД не потребовались;
- локально: target `589 passed`, full `1442 passed`, Ruff, mypy (20 файлов), secret scan,
  dependency audit и diff-check успешны;
- post-merge gate подтвердил Ruff (`519 files`), mypy (20 файлов), secret scan, smoke tests и
  dependency audit на обеих версиях Python.

## Ранее завершённый этап

**RM-122 — анализ конкуренции**

Статус: `DONE`

Подтверждение:

- feature PR #47 слит в `main` коммитом `4ebbf6c`;
- post-merge Quality Gate run `29422296807` успешен на Python 3.12 и 3.13;
- полный Windows suite: `1389 passed` на обеих версиях Python;
- pure local competition registry использует current verified specialized findings и fail-closed
  v9;
- RM-107 score/recommendation и critical stop-factor policy не изменены.

## Текущее действие

Провести отдельный аудит RM-124 до изменения механизма повторной проверки AI или его
cache/retry/deterministic contract.
