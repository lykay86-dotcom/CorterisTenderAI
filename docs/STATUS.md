# Текущее состояние CorterisTenderAI

Обновлено: 15 июля 2026 года.

## Активный этап

**RM-121 — финансовые риски**

Статус: `IN PROGRESS`

Этап назначается только после merge реализации RM-120, успешного post-merge Windows Quality
Gate на merge-коммите и merged docs-only closeout. До изменения application-кода RM-121
требуется отдельный аудит текущего финансового анализа и его deterministic/AI boundaries.

## Предыдущий этап

**RM-120 — юридические риски**

Статус: `DONE`

Подтверждение:

- feature PR #43 слит в `main` коммитом `f2f87ff`;
- post-merge Quality Gate run `29411717306` успешен на Python 3.12 и 3.13;
- полный Windows suite: Python 3.12 — `1198 passed in 74.13s`, Python 3.13 —
  `1198 passed in 73.26s`;
- pure local legal policy строит versioned registry только из current verified specialized
  requirements, ТЗ и draft-contract findings;
- категории, priorities, stable IDs и actions детерминированы; generic risks и deterministic
  stop-factors не копируются;
- persisted payload v7 локально пересчитывается и сверяется, legacy v1–v6 и повреждённые данные
  обрабатываются fail-closed;
- existing UI и JSON/HTML export показывают четыре статуса, priorities, citations, warnings и
  disclaimer с безопасным escaping;
- сохранены единые provider/analyzer/service/Orchestrator/repository/UI/exporter, один production
  provider call и одна `RUNNING_AI` стадия;
- RM-107 score/recommendation и абсолютный приоритет critical stop-factor не изменены;
- новая БД или миграция БД не потребовались;
- локально: target `342 passed`, full `1198 passed`, Ruff, mypy (17 файлов), secret scan,
  dependency audit и diff-check успешны;
- post-merge gate подтвердил Ruff (`513 files`), mypy (17 файлов), secret scan, smoke tests и
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

Провести отдельный аудит RM-121 до изменения анализа финансовых рисков или его
AI/deterministic contract.
