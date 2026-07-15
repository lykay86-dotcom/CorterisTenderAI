# Текущее состояние CorterisTenderAI

Обновлено: 15 июля 2026 года.

## Активный этап

**RM-120 — юридические риски**

Статус: `IN PROGRESS`

Этап назначается только после merge реализации RM-119, успешного post-merge Windows Quality
Gate на merge-коммите и merged docs-only closeout. До изменения application-кода RM-120
требуется отдельный аудит текущего анализа юридических рисков и его deterministic/AI boundaries.

## Предыдущий этап

**RM-119 — анализ требований к заявке**

Статус: `DONE`

Подтверждение:

- feature PR #41 слит в `main` коммитом `dedc361`;
- post-merge Quality Gate run `29406013475` успешен на Python 3.12 и 3.13;
- полный Windows suite: Python 3.12 — `1114 passed in 88.59s`, Python 3.13 —
  `1114 passed in 77.06s`;
- единый deterministic classifier надёжно назначает application requirements/form/instructions,
  сохраняет приоритет ТЗ и проекта договора и используется также AI context builder;
- строгий provider-output schema v4 содержит 21 application-группу, persisted payload v6 читает
  legacy безопасно и отклоняет future/corrupt cache fail-closed;
- application findings подтверждаются только единым RM-116 citation resolver и current provenance
  для локально классифицированных документов заявки;
- existing UI и JSON/HTML export показывают complete/partial/not_found/unavailable, все 21 группу,
  citations и предупреждения без бизнес-логики или private paths;
- сохранены единые provider/analyzer/service/Orchestrator/repository/context builder/exporter,
  один production provider call и одна `RUNNING_AI` стадия;
- RM-107 score/recommendation и абсолютный приоритет critical stop-factor не изменены;
- новая БД или миграция БД не потребовались;
- локально: target `311 passed`, full `1114 passed`, Ruff, mypy (16 файлов), secret scan,
  dependency audit и diff-check успешны;
- post-merge gate подтвердил Ruff (`511 files`), mypy (16 файлов), secret scan, smoke tests и
  dependency audit на обеих версиях Python.

## Ранее завершённый этап

**RM-118 — анализ проекта договора в тендере**

Статус: `DONE`

Подтверждение:

- feature PR #39 слит в `main` коммитом `40b7da2`;
- post-merge Quality Gate run `29399058186` успешен на Python 3.12 и 3.13;
- полный Windows suite: `1080 passed` на обеих версиях Python;
- введены 16 contract-групп, completeness-aware context и fail-closed payload v5;
- RM-107 score/recommendation и critical stop-factor policy не изменены.

## Текущее действие

Провести отдельный аудит RM-120 до изменения анализа юридических рисков или его
AI/deterministic contract.
