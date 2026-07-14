# Текущее состояние CorterisTenderAI

Обновлено: 14 июля 2026 года.

## Активный этап

**RM-116 — ссылки, цитаты и provenance**

Статус: `IN PROGRESS`

Этап назначен только после merge реализации RM-115 и успешного Windows Quality Gate на
merge-коммите. До изменения application-кода RM-116 требуется отдельный аудит текущих
ссылок, цитат, локальной проверки evidence и provenance boundaries.

Подготовка feature acceptance выполнена в выделенной ветке RM-116:

- добавлены точные локальные citations, immutable provenance/source registry и payload v3;
- provider page/section остаются только hints, а checksum, offsets, locator, citation ID и
  eligibility подтверждаются локально;
- cache, UI, JSON/HTML export и RM-107 принимают только current verified citations;
- сохранены единые provider/analyzer/Orchestrator/repository/context builder/exporter и один
  production provider call; вторая схема или AI workflow не созданы;
- RM-107 score/recommendation и абсолютный приоритет critical stop-factor не изменены;
- новая БД или миграция БД не требуются;
- локальная приёмка на Python 3.12.7: RM-116 target `268 passed`, strict/provider/UI
  regressions `97 passed`, full `1024 passed`; Ruff, mypy (16 файлов), secret scan,
  dependency audit и diff-check успешны.

RM-116 остаётся `IN PROGRESS`: до `DONE` обязательны merge feature PR, успешный post-merge
Windows Quality Gate на Python 3.12/3.13 и merged docs-only closeout. RM-117 не активирован.

## Предыдущий этап

**RM-115 — строгая JSON-схема**

Статус: `DONE`

Подтверждение:

- feature PR #33 слит в `main` коммитом `f2573c4`;
- post-merge Quality Gate run `29352442656` успешен на Python 3.12 и 3.13;
- полный Windows suite: Python 3.12 — `901 passed in 74.68s`, Python 3.13 —
  `901 passed in 77.29s`;
- первый Python 3.12 job завершился нативным Windows access violation внутри pytest;
  повторный запуск того же merge SHA прошёл полностью;
- введена единая строгая provider-output схема и fail-closed локальная валидация;
- OpenAI-compatible запросы используют Responses `text.format`, Ollama сохраняет
  подтверждённый compatibility subset без второго запроса или downgrade;
- структурно невалидный ответ не создаёт AI findings; evidence проверяется только локально;
- RM-107 score/recommendation и critical stop-factor policy не изменены;
- локально: target `229 passed`, full `901 passed`, Ruff, mypy, secret scan,
  dependency audit и `git diff --check` успешны;
- миграция БД не требуется.

## Ранее завершённый этап

**RM-112 — выбор AI-провайдера**

Статус: `DONE`

Подтверждение:

- PR #26 слит в `main` коммитом `1d559b5`;
- post-merge Quality Gate успешен на Python 3.12 и 3.13;
- канонический persisted source — секция `ai` существующего `ConfigManager`;
- поддержаны stable IDs `disabled`, `openai`, `openai_compatible`;
- миграция БД не требуется.

## Текущее действие

Открыть feature PR RM-116, дождаться обязательных Windows checks и после merge выполнить
post-merge Quality Gate; затем подготовить отдельный docs-only closeout без смешивания с RM-117.
