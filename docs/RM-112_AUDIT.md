# RM-112 — аудит выбора AI-провайдера

Дата: 13 июля 2026 года. Исходный HEAD: `ddf0c4c`. Статус RM-112:
`IMPLEMENTED — READY FOR PR`.

## Gate RM-111

- PR #24 с реализацией Orchestrator слит в `main` коммитом `f246381`.
- PR #25 с документальным закрытием слит коммитом `ddf0c4c`.
- Quality Gate обоих merge-коммитов успешен на Python 3.12 и 3.13.
- `ROADMAP.md` и `STATUS.md` указывают RM-111 `DONE`, RM-112 `IN PROGRESS`.
- Более новых незавершённых изменений RM-111 в `main` нет.

RM-112 разрешён к началу.

## Выполненный поиск

Проверены production-код, тесты и Git-история по символам:

- `AIProvider`, `DisabledProvider`, `OpenAICompatibleProvider`;
- `ai_provider`, `ai_base_url`, `ai_model`, `openai_api_key`;
- `ConfigManager`, `UserSettingsStore`, `Settings`, `get_settings`;
- `load_secret`, `save_secret`, `delete_secret`, `keyring`;
- `create_tender_search_runtime`, `TenderAiOrchestrator`,
  `TenderDocumentAiAnalyzer`;
- все прямые вызовы `.analyze()` у provider.

Отдельно прочитаны provider/analyzer/orchestrator, composition roots,
три settings-пути, keyring adapter, legacy и modern UI, controller и существующие
AI/runtime/bootstrap/UI/security тесты.

## Карта компонентов

| Компонент | Текущая роль | Provider/model/base URL | Credentials | Production runtime | Дублирование | Решение RM-112 |
| --- | --- | --- | --- | --- | --- | --- |
| `app.ai.provider.AIProvider` | Абстракция provider | Нет | Нет | Да | Нет | REUSE |
| `DisabledProvider` | Безопасный offline provider | Нет | Нет | Да | Нет | REUSE |
| `OpenAICompatibleProvider` | Единственный HTTP adapter | Да | Получает готовый key | Пока нет | Нет | REUSE |
| `TenderDocumentAiAnalyzer` | Единственный вызов `provider.analyze()` | Нет | Нет | Да | Нет | REUSE |
| `TenderAiOrchestrator` | Единая application-service точка AI | Нет | Нет | Да | Нет | REUSE |
| `create_tender_search_runtime` | Создаёт AI graph с `DisabledProvider` | Только hardcoded disabled | Нет | Да | Нет | ADAPT |
| `app.bootstrap` | Production composition root UI | Нет | Нет | Да | Нет | ADAPT |
| `StartupContext.config` / `ConfigManager` | Атомарный JSON config | Секция `ai` | Нет | Да, но AI не подключён | Канонический кандидат | ADAPT |
| `app.config.settings.Settings` | Environment settings | `ai_provider`, model, URL | Нет | Да для data paths | Пересекается | OUT OF SCOPE; только явный override |
| `UserSettingsStore` | Legacy UI preferences | Display label, model, URL | Нет | Да для legacy UI | Пересекается | MIGRATE / compatibility |
| `app.security.secrets` | Keyring functions | Нет | Читает/пишет keyring | Да для других flows | Нет | ADAPT |
| `app.ui.main_window` | Существующая ChatGPT/ИИ вкладка | Display label, model, URL | Пишет keyring напрямую | Да через modern shell | Содержит settings логику | ADAPT |
| `ModernMainWindow` | Встраивает legacy settings UI | Нет | Нет | Да | Нет | ADAPT для DI |
| `TenderSearchUiController` | UI controller и fallback runtime root | Нет | Нет для AI | Да | Нет | REUSE; получит готовый runtime |

## Текущие settings paths

### `ConfigManager`

`DEFAULT_SETTINGS.ai` уже хранит provider, base URL и model. Provider по умолчанию
равен legacy-значению `none`. `StartupContext` уже передаёт этот manager в
production bootstrap. Это единственный существующий кандидат на канонический persisted
source. Секрета в нём нет.

Во время реализации обнаружено, что невалидный JSON при `ConfigManager.load()`
прерывал bootstrap раньше selection boundary. `ConfigManager` усилен: невалидный
JSON и non-object root сбрасываются к безопасным defaults с `provider=disabled`.
Повреждённая AI-секция дополнительно изолируется selection service.

### `UserSettingsStore`

Legacy `UserPreferences` хранит display label, model и URL в отдельном JSON. Default
`ai_provider="OpenAI API"` не является подтверждённым выбором пользователя и не
может автоматически включать сеть. Остальные поля preferences и файл
сохраняются для compatibility.

### Environment `Settings`

Pydantic settings дублируют provider/model/base URL. Production bootstrap не должен
незаметно давать им приоритет над `ConfigManager`. Environment override допустим
только как явно переданная dependency для CLI/dev/tests.

## Credentials

`app.security.secrets` уже изолирует Windows Credential Manager через keyring.
Существующая AI-вкладка вызывает `save_secret("openai_api_key", ...)` напрямую,
но не читает key для production provider. В RM-112 нужен тонкий
`AiKeyringSecretStore`, переиспользующий эти функции. Key не копируется в config,
legacy JSON, БД, dataclass, warning, exception или log.

Для `disabled` resolution запрещено даже чтение keyring. Ошибка keyring должна
давать безопасный disabled fallback без раскрытия исходного exception.

## Production runtime и network boundary

Текущая цепочка:

1. `bootstrap()` создаёт `StartupContext` и `ModernMainWindow`;
2. `TenderSearchUiController` без готового runtime сам вызывает
   `create_tender_search_runtime()`;
3. runtime создаёт один repository, analyzer, task-service и Orchestrator, но
   всегда передаёт `DisabledProvider()`;
4. Orchestrator вызывает task-service;
5. `TenderDocumentAiAnalyzer` — единственное production-место
   `provider.analyze()`.

Прямых AI provider-вызовов в bootstrap, full analysis, Orchestrator и UI нет. Второй
HTTP adapter не нужен. `OpenAICompatibleProvider` не выполняет сеть в
конструкторе, поэтому его можно безопасно создать при bootstrap. Сеть разрешена
только когда пользователь явно запускает AI-анализ.

## UI

Production `ModernMainWindow` встраивает central widget `LegacyMainWindow`, поэтому
существующая вкладка «ChatGPT / ИИ» является production UI и должна быть
переиспользована. Сейчас она:

- хранит display label через `currentText()`;
- показывает Ollama как активный выбор;
- пишет legacy `UserSettingsStore` и keyring напрямую;
- называет кнопку «Сохранить и проверить», хотя connection test нет;
- не подключает выбранный provider к runtime.

RM-112 должен оставить в UI только presentation mapping и вызов application
service. Stable ID хранится в `QComboBox.itemData`, а API key не попадает в
widget properties и очищается сразу после save.

## Legacy migration

Каноническая `ConfigManager.ai.provider` имеет приорит. Legacy model/base URL могут
быть перенесены как черновые значения только если canonical provider отсутствует,
пуст или равен `none`. Effective provider при этом остаётся `disabled`.

Display labels, включая default `OpenAI API`, не мигрируются в активный provider.
Преобразование display label в stable ID допустимо только при явном сохранении
в новом flow. Остальные `UserPreferences` не меняются; key не копируется.
Миграция должна быть идемпотентной и не требует смены `CONFIG_SCHEMA_VERSION`.

## Целевая граница RM-112

Typed boundary размещается в `app/core/ai/provider_selection.py`, потому что это
application/infrastructure orchestration между `ConfigManager`, secret adapter и уже
существующими provider adapters. Модуль не дублирует analyzer, Orchestrator,
repository или HTTP transport.

В RM-112 входят:

- stable IDs `disabled`, `openai`, `openai_compatible`;
- immutable settings/resolution models без secret;
- ConfigManager-backed load/save и идемпотентная legacy migration;
- keyring adapter и safe disabled fallback;
- синтаксическая validation model/base URL без сети;
- injection готового provider в существующий runtime;
- переиспользование существующей ChatGPT/ИИ вкладки;
- unit/runtime/UI/security тесты.

В RM-112 не входят local/Ollama runtime, новый HTTP adapter, OpenAI protocol
изменения, retries, streaming, failover, live connection test, новые schemas/citations,
специализированные analyzers, AI score/recommendation, изменения RM-107 и БД.

## Изменения БД

Миграция БД не требуется. AI settings хранятся в существующем JSON
`ConfigManager`, secret — только в keyring. Таблицы и payload AI-анализа не меняются.

## Итог реализации

- Точный контракт зафиксирован до application-кода в
  `docs/RM-112_REQUIREMENTS.md` и реализован без функций RM-113/RM-114.
- Канонический persisted source — `ConfigManager.ai`; stable IDs — `disabled`,
  `openai`, `openai_compatible`.
- Выбранный provider внедряется в существующий runtime; единственным местом
  `provider.analyze()` остаётся `TenderDocumentAiAnalyzer`.
- Default disabled flow не читает keyring и не выполняет сеть; bootstrap и save
  также не выполняют network call.
- Целевой набор: `62 passed`; полный pytest: `784 passed` за 52,92 с. Ruff,
  mypy, secret scan, dependency audit и `git diff --check` успешны.
- Миграция БД не требуется. Следующий шаг — публикация PR и merge gate.
