# История дорожной карты CorterisTenderAI

## 2026-07-15 — RM-123 завершён

- PR #49 (`feat(rm-123): add deterministic documentation completeness`) слит в `main` коммитом
  `759f015` (`759f015b2d101e56c9dc2a3db2ac57332b9d8ccc`).
- Post-merge Quality Gate run `29430495132` завершился статусом `SUCCESS`: Python 3.12 —
  `1442 passed in 85.09s`, Python 3.13 — `1442 passed in 81.29s`.
- На обеих версиях прошли Ruff check/format (`519 files`), mypy (20 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Первый Python 3.12 attempt завершился transient native Windows heap crash `0xc0000374` без
  failing assertion или Python exception; rerun того же merge SHA полностью прошёл без изменения
  кода, что подтвердило runner-level transient failure.
- Canonical inventory объединяет existing document catalog и latest text extraction по
  `document_key`, сохраняет download failures/archive members и включает safe identity, kind,
  statuses, checksum и context inclusion/truncation без private source metadata.
- Pure local policy задаёт deterministic statuses, counts, stable issue IDs, titles и actions без
  второго provider call, statement/keyword matching, I/O, network, DB или money calculations.
  Provider `missing_documents` не является source of truth и отображается отдельно.
- Inventory входит в context fingerprint; current payload v10 строго валидируется, assessment
  локально пересчитывается и exact-сверяется. Legacy v1–v9 остаётся unavailable, а
  future/corrupt/tampered cache и duplicate JSON keys обрабатываются fail-closed без изменения
  SQLite schema.
- Provider schema/response format v4, prompt v6, citation resolver v1 и
  legal/financial/competition policy v1 не изменены; payload повышен до v10, analyzer — до v11,
  context — до v6, documentation completeness policy имеет версию 1.
- Сохранены один classifier, analyzer/service/Orchestrator/repository/provider call, одна
  `RUNNING_AI` stage и existing AI tab/JSON/HTML exporter. UI/export показывают status,
  disclaimer, counts, coverage, safe inventory, issues/actions и warnings с HTML escaping.
- RM-107 score/recommendation/action plan/evidence/confidence и абсолютный приоритет critical
  stop-factor не изменены; documentation assessment не входит в decision evidence.
- Локальная приёмка: target `589 passed in 15.07s`, full `1442 passed in 52.38s`, Ruff
  (`519 files`), mypy (20 файлов), secret scan, dependency audit и diff-check успешны.
- RM-123 переведён в `DONE`; RM-124 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации повторной проверки AI.

## 2026-07-15 — RM-122 завершён

- PR #47 (`feat(rm-122): add explainable competition assessment`) слит в `main` коммитом
  `4ebbf6c` (`4ebbf6c4dc4cf004e234310a7bc0fdf959ee17c6`).
- Post-merge Quality Gate run `29422296807` завершился статусом `SUCCESS`: Python 3.12 —
  `1389 passed in 100.83s`, Python 3.13 — `1389 passed in 70.65s`.
- На обеих версиях прошли Ruff check/format (`517 files`), mypy (19 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Pure local competition policy строит versioned registry только из current verified specialized
  requirements, technical specification и draft-contract findings без второго provider call,
  statement keyword/regex matching, market prediction или внешних данных о компаниях.
- Category и review priority заданы фиксированными mappings; stable condition IDs и ordering
  основаны на canonical citation IDs. Generic root findings и deterministic stop-factors не
  копируются.
- Persisted payload v9 локально пересчитывается при чтении; legacy v1–v8 остаётся unavailable,
  а future/corrupt/tampered cache и duplicate JSON keys обрабатываются fail-closed без изменения
  SQLite schema.
- Provider schema/response format v4, prompt v6, context v5, citation resolver v1, legal policy
  v1 и financial policy v1 не изменены; сохранены один analyzer/service/Orchestrator/repository/
  provider call и одна `RUNNING_AI` stage.
- Legacy `COMP_RULES`/`competition_risk`, `raw_metadata`, неподтверждённые результаты торгов,
  company profile, деньги и `float` не используются; прогноз числа конкурентов, вероятности
  победы, снижения цены или законности условий не создаётся.
- Existing AI tab и JSON/HTML exporter показывают status, policy version, priority counts,
  escaped titles/actions, current internal citations, warnings и informational disclaimer.
- RM-107 score/recommendation/action plan/evidence/confidence и абсолютный приоритет critical
  stop-factor не изменены; competition registry не входит в decision evidence.
- Локальная приёмка: target `468 passed in 14.72s`, full `1389 passed in 67.60s`, Ruff
  (`517 files`), mypy (19 файлов), secret scan, dependency audit и diff-check успешны.
- RM-122 переведён в `DONE`; RM-123 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации полноты документации.

## 2026-07-15 — RM-121 завершён

- PR #45 (`feat(rm-121): add explainable financial risk assessment`) слит в `main` коммитом
  `ac1cec2` (`ac1cec2e11ce4cb08ec7aab3b4ab74ad255da746`).
- Post-merge Quality Gate run `29416563733` завершился статусом `SUCCESS`: Python 3.12 —
  `1289 passed in 66.64s`, Python 3.13 — `1289 passed in 88.80s`.
- На обеих версиях прошли Ruff check/format (`515 files`), mypy (18 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Pure local financial policy строит versioned registry только из current verified specialized
  requirements, technical specification и draft-contract findings без второго provider call,
  text heuristics, money parsing или финансового прогноза.
- Category и review priority заданы фиксированными mappings; stable risk IDs и ordering основаны
  на canonical citation IDs. Generic root findings и deterministic stop-factors не копируются.
- Persisted payload v8 локально пересчитывается при чтении; legacy v1–v7 остаётся unavailable,
  а future/corrupt/tampered cache обрабатывается fail-closed без изменения SQLite schema.
- Provider schema/response format v4, prompt v6, context v5, citation resolver v1 и legal policy
  v1 не изменены; сохранены один analyzer/service/Orchestrator/repository/provider call и одна
  `RUNNING_AI` stage.
- Existing AI tab и JSON/HTML exporter показывают status, policy version, priority counts,
  escaped titles/actions, current internal citations, warnings и финансовый disclaimer.
- RM-107 score/recommendation/action plan и абсолютный приоритет critical stop-factor не изменены;
  financial registry не входит в decision evidence.
- CommercialEstimator сохраняет каноническую Decimal-границу; incomplete estimate остаётся
  `DATA_INSUFFICIENT` без вымышленных total cost, profit или margin.
- Локальная приёмка: target `337 passed in 13.12s`, full `1289 passed in 55.25s`, Ruff
  (`515 files`), mypy (18 файлов), secret scan, dependency audit и diff-check успешны.
- RM-121 переведён в `DONE`; RM-122 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации анализа конкуренции.

## 2026-07-15 — RM-120 завершён

- PR #43 (`feat(rm-120): add explainable legal risk assessment`) слит в `main` коммитом
  `f2f87ff` (`f2f87ff640082470bf822acee937ddd184ebcb23`).
- Post-merge Quality Gate run `29411717306` завершился статусом `SUCCESS`: Python 3.12 —
  `1198 passed in 74.13s`, Python 3.13 — `1198 passed in 73.26s`.
- На обеих версиях прошли Ruff check/format (`513 files`), mypy (17 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Pure local legal policy строит versioned registry только из current verified specialized
  requirements, technical specification и draft-contract findings без второго provider call,
  regex-классификации или network legal verification.
- Category и review priority заданы фиксированными mappings; stable risk IDs и ordering основаны
  на canonical citation IDs. Generic root risks и deterministic stop-factors не копируются.
- Persisted payload v7 локально пересчитывается при чтении; legacy v1–v6 остаётся unavailable,
  а future/corrupt/tampered cache обрабатывается fail-closed без изменения SQLite schema.
- Provider schema/response format v4, prompt v6, context v5 и citation resolver v1 не изменены;
  сохранены один analyzer/service/Orchestrator/repository/provider call и одна `RUNNING_AI` stage.
- Existing AI tab и JSON/HTML exporter показывают status, policy version, priority counts,
  escaped titles/actions, current internal citations, warnings и юридический disclaimer.
- RM-107 score/recommendation/action plan и абсолютный приоритет critical stop-factor не изменены;
  legal registry не входит в decision evidence.
- Локальная приёмка: target `342 passed in 11.92s`, full `1198 passed in 51.00s`, Ruff
  (`513 files`), mypy (17 файлов), secret scan, dependency audit и diff-check успешны.
- Неблокирующее предупреждение GitHub Actions о переводе pinned official actions с Node.js 20
  на Node.js 24 сохранено как отдельная обслуживающая задача и не влияет на успешный gate.
- RM-120 переведён в `DONE`; RM-121 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации финансовых рисков.

## 2026-07-15 — RM-119 завершён

- PR #41 (`feat(rm-119): add explainable application requirements analysis`) слит в `main`
  коммитом `dedc361` (`dedc361c1ed88b16e0aa00e7e9f07f9ac131422a`).
- Post-merge Quality Gate run `29406013475` завершился статусом `SUCCESS`: Python 3.12 —
  `1114 passed in 88.59s`, Python 3.13 — `1114 passed in 77.06s`.
- На обеих версиях прошли Ruff check/format (`511 files`), mypy (16 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Один public pure classifier и каноническая область источников выделяют application
  requirements/form/instructions/procurement notice, сохраняя приоритет ТЗ и проекта договора;
  AI context переиспользует их и включает application completeness metadata в fingerprint.
- Строгая provider-output schema v4 содержит обязательный раздел из 21 группы, но не отдаёт
  provider контроль над status/category/verified/legal-risk/financial-risk/score/recommendation.
- Persisted payload v6 безопасно читает legacy v1–v5 как unverified/unavailable, отклоняет
  future/corrupt cache и проверяет current provenance без изменения SQLite schema.
- Application evidence проходит единый RM-116 citation resolver только для current locally
  classified application documents; damaged, altered или non-application evidence остаётся
  unverified.
- Existing UI и JSON/HTML export показывают status, completeness, 21 группу,
  citations/provenance и предупреждения без бизнес-логики или private paths.
- RM-107 score/recommendation/action plan и абсолютный приоритет critical stop-factor не изменены;
  application findings не входят в decision evidence.
- Переиспользованы существующие provider/analyzer/service/Orchestrator/repository/context
  builder/exporter; второй AI workflow, provider call, application repository/table и миграция БД
  не добавлены.
- Локальная приёмка: target `311 passed in 12.91s`, full `1114 passed in 55.17s`, Ruff
  (`511 files`), mypy (16 файлов), secret scan, dependency audit и diff-check успешны.
- RM-119 переведён в `DONE`; RM-120 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации.

## 2026-07-15 — RM-118 завершён

- PR #39 (`feat(rm-118): add explainable draft contract analysis`) слит в `main` коммитом
  `40b7da2` (`40b7da25ec3ce43585650ddcec7afef994299f94`).
- Post-merge Quality Gate run `29399058186` завершился статусом `SUCCESS`: Python 3.12 —
  `1080 passed in 79.65s`, Python 3.13 — `1080 passed in 57.69s`.
- На обеих версиях прошли Ruff check/format (`510 files`), mypy (16 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Один public pure classifier назначает `DocumentKind.DRAFT_CONTRACT`, сохраняет приоритет ТЗ;
  AI context переиспользует его и включает contract completeness metadata в fingerprint.
- Строгая provider-output schema v3 содержит обязательный раздел из 16 групп, но не отдаёт
  provider контроль над status/category/verified/legal-risk/financial-risk/score/recommendation.
- Persisted payload v5 безопасно читает legacy, отклоняет future/corrupt cache и проверяет
  current provenance без изменения SQLite schema.
- Contract evidence проходит единый RM-116 citation resolver только для current locally
  classified contract documents; damaged, altered или non-contract evidence остаётся unverified.
- Existing UI и JSON/HTML export показывают status, completeness, 16 групп, citations/provenance
  и предупреждения без бизнес-логики или private paths.
- RM-107 score/recommendation/action plan и абсолютный приоритет critical stop-factor не изменены;
  contract findings не входят в decision evidence.
- Переиспользованы существующие provider/analyzer/service/Orchestrator/repository/context
  builder/exporter; второй AI workflow, provider call, contract repository/table и миграция БД
  не добавлены.
- Локальная приёмка: target `277 passed in 11.82s`, full `1080 passed in 51.12s`, Ruff
  (`510 files`), mypy (16 файлов), secret scan, dependency audit и diff-check успешны.
- Неблокирующее предупреждение GitHub Actions о переводе pinned official actions с Node.js 20
  на Node.js 24 сохранено как отдельная обслуживающая задача и не влияет на успешный gate.
- RM-118 переведён в `DONE`; RM-119 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации.

## 2026-07-15 — RM-117 завершён

- PR #37 (`feat(rm-117): add explainable technical specification analysis`) слит в `main`
  коммитом `c9d5a31` (`c9d5a31e671ca61a6c6f54428aa8b8f9b26a561a`).
- Post-merge Quality Gate run `29376283665` завершился статусом `SUCCESS`: Python 3.12 —
  `1043 passed in 100.66s`, Python 3.13 — `1043 passed in 150.13s`.
- На обеих версиях прошли Ruff check/format (`509 files`), mypy (16 файлов), repository
  secret scan, offline/migration/composition/build smoke tests и dependency audit.
- Один public pure classifier назначает `DocumentKind.TECHNICAL_SPECIFICATION`; AI context
  переиспользует его, приоритизирует ТЗ и включает completeness metadata в fingerprint.
- Строгая provider-output schema v2 содержит обязательный раздел из 13 групп, но не отдаёт
  provider контроль над status/category/verified/score/recommendation.
- Persisted payload v4 безопасно читает legacy, отклоняет future/corrupt cache и включает
  semantic document kind в current provenance без изменения SQLite schema.
- TS evidence проходит единый RM-116 citation resolver; non-TS, unknown, altered и incomplete
  evidence остаётся unverified, а single-source contradiction не повышается до multi-source.
- Existing UI и JSON/HTML export показывают status, found/included counts, 13 групп,
  citations/provenance и truncation warnings без бизнес-логики или private paths.
- RM-107 score/recommendation и абсолютный приоритет critical stop-factor не изменены.
- Переиспользованы существующие provider/analyzer/service/Orchestrator/repository/context
  builder/exporter; второй AI workflow, provider call, TS repository/table и миграция БД не
  добавлены.
- Локальная приёмка: target `214 passed`, full `1043 passed`, Ruff, mypy (16 файлов), secret
  scan, dependency audit и diff-check успешны.
- Неблокирующее предупреждение GitHub Actions о переводе pinned official actions с Node.js 20
  на Node.js 24 сохранено как отдельная обслуживающая задача и не влияет на успешный gate.
- RM-117 переведён в `DONE`; RM-118 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации.

## 2026-07-15 — RM-116 завершён

- PR #35 (`feat/rm-116-citations-provenance`) слит в `main` коммитом `b8ff9b1`
  (`b8ff9b13b7f67366f16b24c1eedccf9a63cb4d46`).
- Post-merge Quality Gate run `29372896780` завершился статусом `SUCCESS`: Python 3.12 —
  `1030 passed in 123.59s`, Python 3.13 — `1030 passed in 60.47s`.
- На обеих версиях прошли Ruff check/format (`507 files`), mypy (16 файлов), repository
  secret scan, offline/migration/composition/build smoke tests и dependency audit.
- Реализованы exact local citations, immutable provenance/source registry, payload v3,
  provenance-aware cache, безопасная UI-навигация и JSON/HTML export.
- Provider сообщает только кандидаты и безопасную public metadata; checksum, offsets,
  locator, citation ID и eligibility вычисляются и проверяются локально.
- Legacy/future/corrupt cache и небезопасная provider/source metadata обрабатываются
  fail-closed без сохранения `VERIFIED` и без утечки чувствительных данных.
- RM-107 принимает только current verified citations; score/recommendation и абсолютный
  приоритет critical stop-factor не изменены.
- Переиспользованы существующие provider/analyzer/Orchestrator/repository/context
  builder/exporter; второй schema/parser/workflow и миграция БД не добавлены.
- Локальная приёмка: target `273 passed`, strict/provider/UI `97 passed`, full `1029 passed`,
  Ruff, mypy (16 файлов), secret scan, dependency audit и diff-check успешны.
- RM-116 переведён в `DONE`; RM-117 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации.

## 2026-07-14 — RM-116: подготовлена feature acceptance

- После обязательного аудита реализованы exact local citations, immutable provenance/source
  registry, payload v3, provenance-aware cache, безопасная UI-навигация и JSON/HTML export.
- Provider сообщает только кандидаты и безопасную public metadata; checksum, offsets, locator,
  citation ID и eligibility вычисляются и проверяются локально.
- RM-107 принимает только current verified citations; score/recommendation и абсолютный
  приоритет critical stop-factor не изменены.
- Переиспользованы существующие provider/analyzer/Orchestrator/repository/context
  builder/exporter; второй schema/parser/workflow и миграция БД не добавлены.
- Локально на Python 3.12.7: target `273 passed in 7.40s`, strict/provider/UI `97 passed in
  4.93s`, full `1029 passed in 54.90s`; Ruff, mypy (16 файлов), secret scan, dependency audit и
  diff-check успешны.
- Запись является подготовкой feature PR, а не closeout: RM-116 остаётся `IN PROGRESS`, RM-117
  остаётся `PLANNED`; обязательны feature merge, post-merge Windows gate 3.12/3.13 и отдельный
  merged docs-only closeout.
- Финальный adversarial review устранил duplicate extraction revisions и fail-open cached
  provider/source metadata; naive source timestamp теперь сохраняется как explicit `unknown`.

## 2026-07-14 — RM-115 завершён

- PR #33 (`feat(rm-115): enforce strict Tender Intelligence JSON schema`) слит в `main`
  коммитом `f2573c4` (`f2573c49cd6ac0dbbe703786414422034ffa53b2`).
- Post-merge Quality Gate run `29352442656` после повторного запуска завершился статусом
  `SUCCESS`: Python 3.12 — `901 passed in 74.68s`, Python 3.13 —
  `901 passed in 77.29s`.
- Первый Python 3.12 job завершился нативным Windows access violation внутри pytest примерно
  на 48% suite; повторный job на том же merge SHA прошёл полностью. Python 3.13 прошёл без
  этого сбоя.
- Введена одна каноническая строгая Pydantic v2 provider-output схема, детерминированная
  генерация JSON Schema и fail-closed decoder без частичного принятия payload.
- OpenAI и generic `openai_compatible` отправляют Responses API `text.format`; Ollama
  переиспользует тот же provider с подтверждённым compatibility subset без downgrade,
  capability probe или второго запроса.
- Структурно невалидный ответ возвращает `invalid_response` без AI findings; после успешной
  структуры evidence подтверждается только точным локальным совпадением цитаты.
- Переиспользованы существующие provider, analyzer, Orchestrator, repository и DI; второй AI
  workflow не создан.
- RM-107 score/recommendation и абсолютный приоритет critical stop-factor сохранены.
- Локальная приёмка: target `229 passed`, full `901 passed`, Ruff check/format,
  mypy (13 файлов), secret scan, dependency audit и `git diff --check` успешны.
- Persisted schema остаётся версии 2; новая БД или миграция БД не добавлялись.
- RM-115 переведён в `DONE`; RM-116 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации.

## 2026-07-14 — prerequisite RM-115: восстановление Git/Codex integration

- В отдельной ветке `codex/git-integration-recovery` удалён случайный gitlink
  `CorterisTenderAI` (`mode 160000`, commit `38b96ab`), добавленный коммитом `35321dc`
  без обязательного `.gitmodules`.
- Причина: повреждённая submodule-запись ломала обнаружение структуры репозитория и
  `git submodule status`, усложняя Git-операции из Codex; вложенный checkout и пользовательские
  данные в рабочем дереве отсутствовали.
- Application-код, детерминированная логика, score/recommendation, critical stop-factor policy,
  схема БД и активный статус RM-115 не изменены.
- Локальная приёмка: `863 passed in 52.41s`, Ruff check, Ruff format (`502 files`),
  mypy (`10 source files`), secret scan, dependency audit, `git diff --check`, строгий `git fsck`
  и `git submodule status --recursive` успешны.
- PR #32; переход к application-коду RM-115 по-прежнему требует отдельного аудита,
  указанного в `STATUS.md`.

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
