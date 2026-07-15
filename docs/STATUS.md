# Текущее состояние CorterisTenderAI

Обновлено: 15 июля 2026 года.

## Активный этап

**RM-119 — анализ требований к заявке**

Статус: `IN PROGRESS`

Этап назначен только после merge реализации RM-118, успешного post-merge Windows Quality
Gate на merge-коммите и merged docs-only closeout. До изменения application-кода RM-119
требуется отдельный аудит текущего анализа требований к заявке и его deterministic/AI boundaries.

## Предыдущий этап

**RM-118 — анализ проекта договора в тендере**

Статус: `DONE`

Подтверждение:

- feature PR #39 слит в `main` коммитом `40b7da2`;
- post-merge Quality Gate run `29399058186` успешен на Python 3.12 и 3.13;
- полный Windows suite: Python 3.12 — `1080 passed in 79.65s`, Python 3.13 —
  `1080 passed in 57.69s`;
- единый deterministic classifier надёжно назначает `DocumentKind.DRAFT_CONTRACT`, сохраняет
  приоритет ТЗ и используется также AI context builder;
- строгий provider-output schema v3 содержит 16 contract-групп, persisted payload v5 читает
  legacy безопасно и отклоняет future/corrupt cache fail-closed;
- contract findings подтверждаются только единым RM-116 citation resolver и current provenance
  для локально классифицированных проектов договоров;
- existing UI и JSON/HTML export показывают complete/partial/not_found/unavailable, все 16 групп,
  citations и предупреждения без бизнес-логики или private paths;
- сохранены единые provider/analyzer/service/Orchestrator/repository/context builder/exporter,
  один production provider call и одна `RUNNING_AI` стадия;
- RM-107 score/recommendation и абсолютный приоритет critical stop-factor не изменены;
- новая БД или миграция БД не потребовались;
- локально: target `277 passed`, full `1080 passed`, Ruff, mypy (16 файлов), secret scan,
  dependency audit и diff-check успешны;
- post-merge gate подтвердил Ruff (`510 files`), mypy (16 файлов), secret scan, smoke tests и
  dependency audit на обеих версиях Python.

## Ранее завершённый этап

**RM-117 — анализ ТЗ**

Статус: `DONE`

Подтверждение:

- feature PR #37 слит в `main` коммитом `c9d5a31`;
- post-merge Quality Gate run `29376283665` успешен на Python 3.12 и 3.13;
- полный Windows suite: `1043 passed` на обеих версиях Python;
- введены 13 TS-групп, completeness-aware context и fail-closed payload v4;
- RM-107 score/recommendation и critical stop-factor policy не изменены.

## Текущее действие

Провести отдельный аудит RM-119 до изменения анализа требований к заявке или его
AI/deterministic contract.
