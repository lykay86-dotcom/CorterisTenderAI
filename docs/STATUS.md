# Текущее состояние CorterisTenderAI

Обновлено: 13 июля 2026 года.

## Подтверждение RM-107

RM-107 повторно проверен по расширенному Definition of Done. Decision Engine
возвращает score, recommendation, confidence, explanation, причины с impact,
стоп-факторы, missing data и action plan. Все поля отображаются в UI и входят
в JSON. Полный регресс после доработки: 633 passed.

## Активный этап
**RM-113 — локальный режим**

Статус: `IN PROGRESS`

Назначение вступает в силу после merge реализации RM-112. До изменения
application-кода RM-113 требуется отдельный аудит локального режима. Код
local/Ollama не входит в RM-112 и в текущей ветке отсутствует.

## Предыдущий этап
**RM-112 — выбор AI-провайдера**

Статус: `DONE`

Подтверждение:
- канонический persisted source — секция `ai` существующего `ConfigManager`;
- поддержаны stable IDs `disabled`, `openai`, `openai_compatible`;
- переиспользованы `DisabledProvider`, `OpenAICompatibleProvider`, единый analyzer и Orchestrator;
- default, unknown, corrupt config и ошибки keyring безопасно переходят в `disabled`;
- legacy display label `OpenAI API` не включает сеть, миграция идемпотентна;
- существующая ChatGPT/ИИ вкладка сохраняет выбор через application service и не показывает secret;
- целевой набор `62 passed`, полный pytest `784 passed` за 52,92 с;
- Ruff, mypy, secret scan, dependency audit и `git diff --check` успешны;
- миграция БД не требуется.

## Ранее завершённый этап
**RM-111 — AI Orchestrator**

Статус: `DONE`

Подтверждение:
- PR #24 слит в `main` коммитом `f246381`;
- создана единая application-service точка входа `TenderAiOrchestrator`;
- полный анализ вызывает только Orchestrator;
- полный локальный регресс `748 passed`, обязательные проверки успешны.

## Текущее действие
Слить PR реализации RM-112, подтвердить merge gate и только затем начать аудит RM-113.
