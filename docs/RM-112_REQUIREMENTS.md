# RM-112 — требования к выбору AI-провайдера

Дата: 13 июля 2026 года. Исходный HEAD: `ddf0c4c`. Статус:
`IMPLEMENTED — READY FOR PR`.

## Цель

Добавить безопасный выбор уже существующего AI provider без второго
HTTP adapter, analyzer, Orchestrator, repository или Decision Engine. Выбр должен
попадать в production runtime только через bootstrap dependency injection.

## Канонический source

- Persisted source: `app.core.config_manager.ConfigManager`, секция `ai`.
- Поля: `provider`, `model`, `base_url`.
- Секреты в эту секцию не входят.
- `UserSettingsStore.ai_*` остаётся только legacy/migration compatibility.
- `app.config.settings.Settings.ai_*` не переопределяет persisted choice в production.
- Environment override допустим только как явно переданная dependency
  CLI/dev/test и имеет приоритет только в этом явном вызове.
- Четвёрый settings store не создаётся.

## Stable provider IDs

Persistence и application layer используют только:

- `disabled` — существующий `DisabledProvider`;
- `openai` — существующий `OpenAICompatibleProvider` с official base URL;
- `openai_compatible` — тот же `OpenAICompatibleProvider` с явным base URL.

Legacy `none` нормализуется в `disabled`. Display labels живут только в UI.
Ollama/local provider не является допустимым выбором в RM-112.

## Typed contract

`app/core/ai/provider_selection.py` содержит:

- `AiProviderId(StrEnum)`;
- immutable `AiProviderSettings(provider_id, model, base_url)`;
- immutable `AiProviderResolution(requested_provider_id, effective_provider_id,
  provider, available, warnings, requires_restart)`;
- immutable `LegacyAiProviderSettings(provider_label, model, base_url)`;
- `AiSecretStore` protocol с `load`, `save`, `delete`;
- `AiKeyringSecretStore`, переиспользующий `app.security.secrets`;
- `AiProviderSelectionService` с load, validation, migration, save и resolution.

Secret не входит в settings/resolution, `repr`, warnings, exception, config payload
и return value.

## Resolution

### `disabled`

- Возвращает существующий `DisabledProvider`.
- `effective_provider_id=disabled`, `available=true`.
- Не читает keyring.
- Не выполняет сеть.

### `openai`

- Использует official base URL `https://api.openai.com/v1`.
- Требует непустые model и keyring credential `openai_api_key`.
- Переиспользует `OpenAICompatibleProvider`.
- Отсутствующее или невалидное значение даёт disabled fallback.

### `openai_compatible`

- Требует явные non-empty base URL, model и keyring credential.
- Разрешены только `http` и `https` URL с hostname.
- URL с username, password, fragment или unsupported scheme отклоняется.
- Validation синтаксическая и не выполняет HTTP request.
- Переиспользует `OpenAICompatibleProvider`.

### Unknown/corrupt

- Пустой, unknown, legacy `none` или повреждённый provider ID не вызывает exception.
- Effective provider всегда `disabled`.
- `available=false` для requested provider, который не может быть активирован.
- Warning не содержит raw configuration, URL, key или exception text.
- Ошибка keyring даёт тот же safe disabled fallback.
- Повреждённая AI-секция config не прерывает bootstrap.

Fallback не использует старый успешный AI-result вместо ошибки текущего
запуска и не блокирует детерминированный анализ.

## Save contract

- UI передаёт stable `AiProviderId`, model, base URL и optional new secret
  в application service.
- Settings валидируются до persistence.
- Если передан новый secret, keyring save должен завершиться до
  переключения canonical provider.
- Ошибка secret save не меняет persisted provider и возвращает disabled
  resolution с безопасным warning.
- Успешное save имеет `requires_restart=true`; текущий runtime не меняется.
- Сохранение не выполняет connection test или любой HTTP request.

## Legacy migration

- Canonical `ConfigManager.ai.provider` имеет приоритет.
- Если canonical provider отсутствует, пуст или равен `none`, legacy model/base
  URL могут быть скопированы как черновые non-secret значения.
- Provider при migration записывается как `disabled`.
- Legacy default `OpenAI API` не считается consent на сеть.
- Display label преобразуется в stable ID только при явном save нового UI.
- Остальные `UserPreferences` не меняются.
- Key из keyring не копируется.
- Migration идемпотентна и не меняет `CONFIG_SCHEMA_VERSION`.

## Runtime и bootstrap

`create_tender_search_runtime(..., ai_provider: AIProvider | None = None)`:

- не получил provider — использует `DisabledProvider`;
- не читает ConfigManager и keyring;
- не выполняет сеть;
- передаёт готовый provider в единственный `TenderDocumentAiAnalyzer`;
- создаёт ровно по одному analyzer, task-service, Orchestrator и AI repository.

Production bootstrap:

1. получает existing `StartupContext.config`;
2. выполняет idempotent legacy migration;
3. разрешает provider через selection service;
4. создаёт `TenderSearchRuntime` с готовым provider;
5. передаёт готовый runtime в `TenderSearchUiController`;
6. передаёт selection service в существующий settings UI.

Bootstrap не вызывает `provider.analyze()` и не делает live connection check.

## UI

- Переиспользуется только существующая вкладка ChatGPT/ИИ.
- Combo берёт localized labels из presentation catalog, stable ID — из `itemData`.
- Поддержаны только disabled, OpenAI и OpenAI-compatible.
- Unknown value показывается как disabled.
- Disabled скрывает/блокирует model, URL и key field.
- Official OpenAI не требует редактируемого URL; OpenAI-compatible показывает URL.
- Сохранённый key никогда не загружается в `QLineEdit`; placeholder `Сохранён`
  допустим только как boolean indicator.
- После save key field немедленно очищается.
- Кнопка называется «Сохранить».
- После save UI сообщает: «Новый AI-провайдер будет применён после
  перезапуска приложения».
- UI не читает ConfigManager/keyring напряму, не создаёт provider и не делает HTTP request.

## Инварианты RM-107/RM-111

- Orchestrator остаётся единой application-service точкой.
- `TenderDocumentAiAnalyzer` остаётся единственным местом `provider.analyze()`.
- Второй repository, analyzer, Orchestrator и Decision Engine не создаются.
- AI не рассчитывает score и recommendation.
- Unverified и stale AI не влияют на RM-107.
- Критический stop-factor имеет абсолютный приоритет.

## Вне scope

RM-112 не реализует local/Ollama runtime, новый OpenAI transport или SDK,
protocol upgrades, retries, streaming, failover, live connection checks, новую JSON Schema,
citations/provenance, специализированные analyzers, новую БД или миграцию БД.

## Acceptance

- Unit-тесты покрывают stable IDs, validation, migration, secret failures и safe fallback.
- Runtime-тесты доказывают default disabled, provider injection, один Orchestrator и
  отсутствие network/keyring в default flow.
- Bootstrap-тесты доказывают DI resolved provider/runtime и отсутствие AI network call.
- UI-тесты покрывают `itemData`, visibility, save, key clearing и restart notice.
- Security-тесты доказывают отсутствие secret в config, repr, warning и log.
- Проходят целевой pytest, полный pytest, Ruff check/format, mypy, secret scan,
  dependency audit и `git diff --check`.
- После merge PR в `main` RM-112 переводится в `DONE`, RM-113 назначается
  следующим активным этапом.

## Результат приёмки

- Все требования реализованы без расширения scope на local/Ollama и RM-114.
- Целевой набор из семи обязательных модулей: `62 passed`.
- Полный локальный pytest: `784 passed` за 52,92 с.
- Ruff check/format, mypy для 9 файлов, repository secret scan, dependency audit
  и `git diff --check` успешны.
- Миграция БД не требуется.
