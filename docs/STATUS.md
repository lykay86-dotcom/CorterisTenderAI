# Текущее состояние CorterisTenderAI

Обновлено: 14 июля 2026 года.

## Активный этап

**RM-116 — ссылки, цитаты и provenance**

Статус: `IN PROGRESS`

Этап назначен только после merge реализации RM-115 и успешного Windows Quality Gate на
merge-коммите. До изменения application-кода RM-116 требуется отдельный аудит текущих
ссылок, цитат, локальной проверки evidence и provenance boundaries.

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

Провести отдельный аудит RM-116 до изменения ссылок, цитат или provenance contract.
