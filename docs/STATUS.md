# Текущее состояние CorterisTenderAI

Обновлено: 14 июля 2026 года.

## Активный этап

**RM-115 — строгая JSON-схема**

Статус: `IN PROGRESS`

Этап назначен только после merge реализации RM-114 и успешного Windows Quality Gate на
merge-коммите. До изменения application-кода RM-115 требуется отдельный аудит текущей
схемы Tender Intelligence, prompt/output contract и compatibility boundaries.

## Предыдущий этап

**RM-114 — OpenAI-совместимый API**

Статус: `DONE`

Подтверждение:

- feature PR #30 слит в `main` коммитом `e4caca0`;
- post-merge Quality Gate run `29315630189` успешен на Python 3.12 и 3.13;
- полный Windows suite: `863 passed` на каждой версии Python;
- укреплён единый `OpenAICompatibleProvider`; второй HTTP/AI pipeline не создан;
- закреплены `/responses`, cloud `store=false`, Ollama profile, no-redirect и 4 MiB limit;
- HTTP/JSON/network/TLS/refusal/incomplete ошибки безопасно классифицируются без утечек;
- RM-107 score/recommendation и critical stop-factor policy не изменены;
- локально: target `152 passed`, full `863 passed`, Ruff, mypy, secret scan,
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

Провести отдельный аудит RM-115 до изменения prompt, output contract или строгой JSON-схемы.
