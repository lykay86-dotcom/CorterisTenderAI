# История дорожной карты CorterisTenderAI

## 2026-07-14 — RM-114 завершён

- PR #30 (`feat(rm-114): harden OpenAI-compatible Responses API`) слит в `main`
  коммитом `e4caca0`.
- Post-merge Quality Gate run `29315630189` завершился статусом `SUCCESS`:
  Python 3.12 — `863 passed in 161.88s`, Python 3.13 — `863 passed in 164.67s`.
- Обязательный audit и Responses API contract зафиксированы до application-кода.
- Укреплён существующий `OpenAICompatibleProvider`; второй provider, analyzer,
  Orchestrator, repository, Decision Engine или AI pipeline не создан.
- Канонический endpoint — один `POST /responses` без streaming, retry, background mode,
  Chat Completions fallback, bootstrap/save health-check или сети до явного анализа.
- Cloud profile отправляет `stream=false` и `store=false`; Ollama переиспользует тот же
  provider и не получает неподтверждённые optional fields.
- Redirects запрещены, TLS verification сохранена, response ограничен 4 MiB, а
  HTTP/JSON/network/TLS/refusal/incomplete ошибки не раскрывают raw body, URL, exception,
  credential, prompt, документы или приватный путь.
- Generic base URL и credential boundaries усилены без изменения stable provider IDs,
  keyring ownership или UI business logic.
- RM-107 score/recommendation и абсолютный приоритет critical stop-factor сохранены.
- Локальная приёмка: target `152 passed`, full `863 passed`, Ruff check/format,
  mypy (10 файлов), secret scan, dependency audit и `git diff --check` успешны.
- Новая БД или миграция БД не добавлялись. Strict JSON Schema, citations/provenance и
  специализированный анализ ТЗ остались за RM-115/RM-116/RM-117.
- RM-114 переведён в `DONE`; RM-115 назначен следующим активным этапом только для
  отдельного будущего аудита и реализации.

## 2026-07-14 — RM-113 завершён

- PR #28 (`feat(rm-113): add safe local Ollama mode`) слит в `main` коммитом `ef8b296`.
- Post-merge Quality Gate run `29285835443` завершился статусом `SUCCESS` на Python 3.12
  и 3.13. Первый Python 3.13 job завершился единичным native Qt access violation в
  существующем `test_matching_catalog_dialog.py`; повторный job прошёл полностью.
- Добавлен stable ID `ollama` с loopback-only endpoint policy и нормализацией к `/v1`.
- Переиспользованы существующие `OpenAICompatibleProvider`, analyzer, Orchestrator,
  repository, ConfigManager и production DI; второй AI pipeline не создан.
- Ollama не использует keyring, а bootstrap/save не выполняют сеть или health-check.
- Невалидная конфигурация и недоступный локальный сервер дают безопасный fallback без
  раскрытия URL, exception, secret или приватного пути.
- Новая БД или миграция БД не требуются.
- Локальная приёмка: целевой набор `58 passed`, полный pytest `808 passed`, Ruff
  check/format, mypy, secret scan, dependency audit и `git diff --check` успешны.
- RM-113 переведён в `DONE`; RM-114 назначен следующим активным этапом.

## 2026-07-13 — RM-112 завершён

- PR #26 (`feat(rm-112): add safe AI provider selection`) слит в `main`
  коммитом `1d559b5`.
- Post-merge Quality Gate run `29280757442` завершился статусом `SUCCESS` на
  Python 3.12 и 3.13.
- Проведён обязательный аудит settings, keyring, runtime, UI и прямых
  provider-вызовов; требования зафиксированы до application-кода.
- Секция `ai` существующего `ConfigManager` назначена каноническим persisted
  source со stable IDs `disabled`, `openai`, `openai_compatible`.
- Переиспользованы существующие provider adapters, analyzer и Orchestrator;
  выбранный provider внедряется в production runtime через bootstrap.
- Default, неизвестная/повреждённая конфигурация и ошибки keyring безопасно
  переходят в `disabled` без утечки secret и без сети при bootstrap/save.
- Legacy label `OpenAI API` не активирует сеть; migration non-secret drafts
  идемпотентна.
- Переиспользована существующая ChatGPT/ИИ вкладка; local/Ollama не добавлен.
- Новая БД или миграция БД не требуются.
- Локальная приёмка: целевой набор `62 passed`, полный pytest `784 passed` за
  52,92 с, Ruff check/format, mypy (9 файлов), secret scan, dependency audit и
  `git diff --check` успешны.
- RM-112 переведён в `DONE`; RM-113 назначен следующим активным этапом.

## 2026-07-13 — RM-111 завершён

- PR #24 (`feat(rm-111): add unified tender AI orchestrator`) слит в `main`
  коммитом `f246381`.
- Обязательный Quality Gate merge-коммита завершился статусом `SUCCESS`
  на Python 3.12 и 3.13.
- Подтверждены единый Orchestrator, отсутствие второго production AI
  workflow, явная передача текущего результата в RM-107 и безопасная
  деградация без API.
- Миграция БД не требуется.
- RM-111 переведён в `DONE`; RM-112 назначен следующим активным этапом
  только после merge PR #24.

## 2026-07-13 — RM-111 AI Orchestrator подготовлен к приёмке

- Проведён аудит всех provider/task-service/repository/Decision Engine/UI/export
  путей; требования зафиксированы до изменения application-кода.
- Создан единый stateless `TenderAiOrchestrator`, переиспользующий
  `TenderDocumentAiAnalysisService` и возвращающий результат текущего запуска.
- Последняя exception boundary и status-to-warning policy удалены из полного
  анализа и централизованы в Orchestrator без раскрытия exception, traceback,
  credentials или приватных путей.
- `TenderFullAnalysisService` вызывает Orchestrator один раз и явно передаёт
  текущий AI-результат в RM-107; stale cache не подменяет текущую ошибку.
- Production runtime создаёт один Orchestrator и один AI repository; по
  умолчанию сохранён `DisabledProvider`, настройки RM-112/RM-114 не добавлялись.
- Неиспользуемый legacy `TenderAIService` с собственными score/recommendation и
  прямым provider-вызовом удалён; совместимые JSON/citation helpers сохранены.
- UI получил отдельную стадию «AI-анализ документации»; существующее поле
  `ai_document_analysis` и HTML/JSON export не изменены.
- Новая БД, таблица или миграция не требуются.
- Локальная приёмка: целевой набор `93 passed`, полный pytest `748 passed` за
  42,79 с, Ruff check/format, mypy (7 файлов), security scan и dependency audit
  успешны.
- RM-111 остаётся `IN PROGRESS` до merge PR; RM-112 не назначен.

## 2026-07-13 — RM-111 quality-gate prerequisite
- Решением владельца герметизация credential-тестов и воспроизводимый Windows
  quality gate назначены обязательным prerequisite текущего RM-111.
- Основание: baseline чистого `origin/main` (`b4c1cc7`) дал
  `719 passed, 2 failed`; offline-тесты прочитали Windows Credential Manager,
  а один тест выполнил реальный API-запрос.
- При пустом временном keyring оба целевых теста проходят (`2 passed`), что
  подтверждает зависимость результата от пользовательского credential store.
- До закрытия prerequisite бизнес-логика AI Orchestrator не реализуется.
- C17 canonicalization и C19 live verification остаются отдельными будущими
  work packages и не включаются в RM-111.
- В отдельной ветке `fix/rm-111-quality-gate` устранено чтение host keyring в
  offline-тестах, добавлены secret/dependency gates, фиксированный mypy-контур
  и Windows GitHub Actions matrix для Python 3.12/3.13.
- Локальный полный регресс прошёл в обычном и изолированном режимах:
  `725 passed` в каждом; Ruff, mypy, security scan и dependency audit успешны.
- PR #22 слит в `main` коммитом `ebfdf01`; обязательные jobs Python 3.12 и 3.13
  прошли на PR и повторно на merge-коммите в `main`.
- Для `main` включена защита: обязательный PR, актуальная ветка, оба стабильных
  quality-gate check context, запрет force-push и удаления; правила действуют
  для администратора.
- Prerequisite переведён в `DONE`; RM-111 остаётся `IN PROGRESS`. AI
  Orchestrator, C17 и C19 в этом пакете не реализовывались.
- В post-job логах GitHub есть неблокирующие предупреждения о переходе official
  actions с Node.js 20 на Node.js 24 и cleanup Git-кэша; итог обоих jobs —
  `SUCCESS`, обновление action pins остаётся обслуживающей задачей CI.

## 2026-07-13 — Roadmap v2
- RM-107 переведён в `DONE`.
- RM-108 назначен активным.
- Сохранена нумерация RM-001–RM-200.
- Добавлены универсальный поиск, полный редизайн, оценка контрагентов, договорный AI, подписки и защита приложения.
- Включена многоуровневая защита: Nuitka, нативные модули, серверные entitlements, подписанные лицензии, Authenticode и защищённые обновления.
- Collector C1–C20 остаётся интеграционным слоем и не заменяет RM.

## 2026-07-13 — RM-108 завершён
- Добавлено детерминированное резюме тендера с безопасным AI-улучшением текста.
- Резюме отображается в полном анализе и сохраняется в реестре закупок.
- Схема реестра обновлена до версии 13.
- RM-109 назначен следующим активным этапом.

## 2026-07-13 — RM-108 acceptance finalization
- Добавлены confidence и provenance для каждого факта резюме.
- Резюме собирает существующие решение RM-107, стоп-факторы, коммерческий расчёт, проверку данных и профиль компании.
- Добавлены история резюме, отдельная вкладка AI summary и тест воспроизводимости offline-результата.
- Полный регресс: 620 passed (без отдельного теста crash-reporting).

## 2026-07-13 — RM-107 закрыт
- Владелец проекта подтвердил статус `DONE` для RM-107.
- Дальнейшие улучшения единого решения об участии ведутся отдельными RM и не
  переоткрывают RM-107.

## 2026-07-13 — RM-109 завершён
- Реализован evidence-first AI-анализ полного комплекта извлечённых документов.
- Вывод без точной цитаты маркируется `unverified` и не влияет на RM-107.
- Добавлены хранение, повторное использование, вкладка UI и экспорт HTML/JSON.
- Полный регресс: 631 passed (без отдельного теста crash-reporting).
- RM-110 назначен следующим активным этапом.

## 2026-07-13 — RM-107 приведён к расширенному Definition of Done
- Добавлены причины решения с числовым impact и верхнеуровневый score.
- Confidence учитывает качество доказательств и количество отсутствующих данных.
- Добавлены отдельные stop_factors, missing data и детерминированный action plan.
- JSON и UI показывают все поля итогового решения.
- Стоп-фактор сохраняет абсолютный приоритет над высоким score.
- Полный регресс: 633 passed (без отдельного теста crash-reporting).

## 2026-07-13 — RM-110 завершён
- PR: #19 (`feat(rm-110): stabilize tender intelligence`).
- Проведён аудит существующей цепочки Tender Intelligence без создания
  дублирующих механизмов.
- Добавлены защитная нормализация AI-ответа, безопасные статусы, контролируемый
  контекст, версионированный fingerprint и восстановление истории SQLite.
- Ошибки AI, сети, контекста и persistence больше не блокируют RM-107,
  детерминированное резюме, UI и экспорт.
- Неподтверждённые и устаревшие AI-выводы не влияют на текущее решение.
- По разрешению владельца устранён существующий Ruff baseline: 768 ошибок;
  legacy-код приведён к единому формату без изменения подтверждённого поведения.
- Полный регресс после очистки, включая crash-reporting: 701 passed.
- `ruff check .` и `ruff format . --check` проходят.
- RM-111 назначен следующим активным этапом только после merge PR #19.

## Правило
Каждое изменение содержит дату, RM, причину, ссылку на PR и влияние на следующие этапы.
