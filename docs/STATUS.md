# Текущее состояние CorterisTenderAI

Обновлено: 15 июля 2026 года.

## Активный этап

**RM-118 — анализ проекта договора в тендере**

Статус: `IN PROGRESS`

Этап назначен только после merge реализации RM-117, успешного post-merge Windows Quality
Gate на merge-коммите и merged docs-only closeout. До изменения application-кода RM-118
требуется отдельный аудит текущего анализа проекта договора и его deterministic/AI boundaries.

## Предыдущий этап

**RM-117 — анализ ТЗ**

Статус: `DONE`

Подтверждение:

- feature PR #37 слит в `main` коммитом `c9d5a31`;
- post-merge Quality Gate run `29376283665` успешен на Python 3.12 и 3.13;
- полный Windows suite: Python 3.12 — `1043 passed in 100.66s`, Python 3.13 —
  `1043 passed in 150.13s`;
- единый deterministic classifier назначает `DocumentKind.TECHNICAL_SPECIFICATION`, а TS-first
  ordering и completeness metadata входят в context fingerprint;
- строгий provider-output schema v2 содержит 13 TS-групп, persisted payload v4 читает legacy
  безопасно и отклоняет future/corrupt cache fail-closed;
- TS findings подтверждаются только финальным RM-116 verifier и current provenance с локальным
  semantic document kind; non-TS/unknown/altered evidence остаётся unverified;
- существующие UI и JSON/HTML export показывают complete/partial/not_found/unavailable без
  бизнес-логики и private paths;
- сохранены единые provider/analyzer/service/Orchestrator/repository/context builder/exporter,
  один production provider call и одна `RUNNING_AI` стадия;
- RM-107 score/recommendation и абсолютный приоритет critical stop-factor не изменены;
- новая БД или миграция БД не потребовались;
- локально: target `214 passed`, full `1043 passed`, Ruff, mypy (16 файлов), secret scan,
  dependency audit и diff-check успешны;
- post-merge gate подтвердил Ruff (`509 files`), mypy (16 файлов), secret scan, smoke tests и
  dependency audit на обеих версиях Python.

## Ранее завершённый этап

**RM-116 — ссылки, цитаты и provenance**

Статус: `DONE`

Подтверждение:

- feature PR #35 слит в `main` коммитом `b8ff9b1`;
- post-merge Quality Gate run `29372896780` успешен на Python 3.12 и 3.13;
- полный Windows suite: `1030 passed` на обеих версиях Python;
- введены exact citations, immutable provenance/source registry и fail-closed payload v3;
- RM-107 score/recommendation и critical stop-factor policy не изменены.

## Текущее действие

Провести отдельный аудит RM-118 до изменения анализа проекта договора или его
AI/deterministic contract.
