# RM-113 — требования к безопасному локальному режиму

Дата: 13 июля 2026 года. Исходный HEAD: `7546b65`. Статус: `ACCEPTED`
(PR #28, merge `ef8b296`).

## Цель и границы

Добавить stable provider ID `ollama` и UI-label «Ollama — локально», переиспользовав
существующие ConfigManager, `OpenAICompatibleProvider`, analyzer, Orchestrator, repository и
production DI. Новый transport, AI pipeline, БД или миграция не создаются.

## Канонический контракт

- `AiProviderId.OLLAMA = "ollama"`.
- Default endpoint: `http://localhost:11434/v1`.
- Compatibility credential: несекретная константа `ollama`, которая не сохраняется.
- Model обязателен и проходит существующую ограниченную синтаксическую проверку.
- Сохраняются только `ai.provider`, `ai.model`, `ai.base_url`; save возвращает
  `requires_restart=True`.
- Legacy display-label `Ollama` не активирует provider. Активация возможна только после
  явного сохранения stable ID пользователем.

## Endpoint policy

Разрешены только `http`/`https` URL без username, password, query и fragment. Host должен
быть ровно `localhost`, адресом из `127.0.0.0/8` или `::1`. Разрешён произвольный локальный
порт. Remote domain, LAN IP, `localhost.example.com` и другие схемы запрещены. После
валидации путь канонизируется к `/v1`, потому что существующий adapter добавляет
`/responses`.

Невалидный URL или model дают `DisabledProvider`. Warning является константным и не
содержит исходный URL, exception, secret или приватный путь.

## Credential и сеть

- Ollama никогда не читает, не записывает и не удаляет cloud credential в keyring.
- Переключение на Ollama не затрагивает сохранённый cloud credential.
- Resolve, bootstrap, load UI и save UI не выполняют HTTP request или health-check.
- HTTP request выполняется только из `OpenAICompatibleProvider.analyze()`, вызванного
  единым `TenderDocumentAiAnalyzer` при явном AI-анализе.
- Приложение не устанавливает Ollama, не запускает его и не выполняет `ollama pull`.

## UI

- Combo содержит stable IDs `disabled`, `openai`, `openai_compatible`, `ollama`.
- Для Ollama доступны model и Base URL, а API key отключён и не показывает состояние
  «Сохранён».
- При первом выборе подставляется default local URL; сохранённый custom loopback URL не
  перезаписывается.
- UI показывает нейтральную подсказку о заранее запущенном Ollama и установленной модели.
- Validation и credential policy остаются в `AiProviderSelectionService`.

## Инварианты RM-107/RM-111

AI не изменяет score/recommendation, stale или unverified AI-result не влияет на решение,
а критический stop-factor имеет абсолютный приоритет. Ошибка или недоступность Ollama даёт
текущий безопасный `provider_error`, не подменяется старым успехом и не останавливает
детерминированный анализ.

## Acceptance

Unit/runtime/UI/security тесты должны покрывать stable ID, loopback policy, нормализацию,
отсутствие keyring и сети при resolve/save/bootstrap, транспорт `/v1/responses`, безопасный
fallback и сохранение архитектурных инвариантов. Обязательны целевой и полный pytest, Ruff,
mypy, repository secret scan, dependency audit и `git diff --check`.

## Результат приёмки

- Все требования реализованы без расширения scope на RM-114–RM-116.
- Целевой набор: `58 passed`; полный локальный pytest: `808 passed`.
- Ruff check/format, mypy, repository secret scan, dependency audit и
  `git diff --check` успешны.
- Post-merge Quality Gate run `29285835443` успешен на Python 3.12 и 3.13.
- Миграция БД не требуется.
