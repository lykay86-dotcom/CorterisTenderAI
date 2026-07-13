# RM-113 — аудит локального AI-режима

Дата аудита: 13 июля 2026 года. Baseline: `7546b65` (merge PR #27).

## Результат поиска

- Реализованного Ollama runtime до RM-113 нет. В старом UI и документации встречалось
  только display-имя `Ollama`; stable provider ID и production resolution отсутствовали.
- Provider создаётся в `AiProviderSelectionService`, а production composition root находится
  в `app/bootstrap.py::_create_ai_runtime`.
- Единственный HTTP adapter — `app.ai.provider.OpenAICompatibleProvider` с вызовом
  OpenAI-compatible `/responses`.
- Единственный production-вызов `provider.analyze()` находится в
  `app/core/ai/analyzer.py::TenderDocumentAiAnalyzer`.
- Runtime содержит по одному `TenderAiOrchestrator`, `TenderDocumentAiAnalyzer` и AI
  repository; отдельный локальный pipeline не требуется.
- Канонические non-secret настройки уже хранятся в `ConfigManager.ai` (`provider`, `model`,
  `base_url`). Cloud credential хранится под существующим именем `openai_api_key`.
- Default disabled flow не читает keyring и не выполняет сеть. Bootstrap только разрешает
  provider и внедряет его в существующий runtime.
- RM-107 сохраняет владение score/recommendation и абсолютный приоритет критического
  stop-factor. RM-111 сохраняет единую точку orchestration.
- Незавершённых изменений RM-112 в `origin/main` нет: PR #26 и completion PR #27 слиты.

## Карта компонентов

| Компонент | Решение RM-113 |
|---|---|
| `app.ai.provider.AIProvider` | REUSE |
| `DisabledProvider` | REUSE |
| `OpenAICompatibleProvider` | REUSE |
| `AiProviderSelectionService` | ADAPT |
| `ConfigManager.ai` | REUSE |
| `TenderDocumentAiAnalyzer` | REUSE без изменений |
| `TenderAiOrchestrator` | REUSE без изменений |
| `create_tender_search_runtime` | REUSE существующего DI |
| `AiProviderSettingsWidget` | ADAPT |
| keyring для Ollama | NOT USED |
| новый repository/analyzer/Orchestrator/HTTP transport | FORBIDDEN |
| новая БД или миграция | NOT REQUIRED |

## Baseline

- Целевой набор RM-112: `34 passed`.
- Полный pytest: `784 passed`.
- Из-за ограничений системного `%TEMP%` тесты запускались с `--basetemp` внутри worktree;
  это не меняет состав или поведение тестов.

## Вывод

Локальный режим следует добавить как ещё один вариант существующего selection service.
Для Ollama достаточно безопасно разрешить loopback `/v1` endpoint и создать текущий
`OpenAICompatibleProvider` с несекретным compatibility placeholder. Сеть остаётся возможной
только при явном запуске анализа через существующий analyzer и Orchestrator.

## Закрытие этапа

Аудит подтверждён реализацией без архитектурного дублирования. Feature PR #28 слит в
`main` коммитом `ef8b296`; post-merge Quality Gate run `29285835443` успешен на Python
3.12 и 3.13. Созданы только изменения selection service, существующего UI и тестов.
Analyzer, Orchestrator, repository, Decision Engine и схема БД не изменялись.
