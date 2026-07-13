# Текущее состояние CorterisTenderAI

Обновлено: 14 июля 2026 года.

## Активный этап

**RM-114 — OpenAI-совместимый API**

Статус: `IN PROGRESS`

Этап назначен только после merge реализации RM-113 и успешного Windows Quality Gate на
merge-коммите. До изменения application-кода RM-114 требуется отдельный аудит текущего
OpenAI-compatible transport и границ протокола.

## Предыдущий этап

**RM-113 — локальный режим**

Статус: `DONE`

Подтверждение:

- feature PR #28 слит в `main` коммитом `ef8b296`;
- post-merge Quality Gate run `29285835443` успешен на Python 3.12 и 3.13;
- добавлен stable provider ID `ollama` и loopback-only endpoint policy;
- переиспользованы `OpenAICompatibleProvider`, единый analyzer, Orchestrator и repository;
- Ollama не читает, не записывает и не удаляет cloud credential в keyring;
- bootstrap и сохранение настроек не выполняют HTTP request или health-check;
- недоступный Ollama даёт безопасный `provider_error`, не останавливая детерминированный
  анализ;
- локальный целевой набор `58 passed`, полный pytest `808 passed`;
- Ruff, mypy, secret scan, dependency audit и `git diff --check` успешны;
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

Провести отдельный аудит RM-114 до изменения OpenAI-compatible transport или протокола.
