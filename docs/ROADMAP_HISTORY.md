# История дорожной карты CorterisTenderAI

## 2026-07-17 — RM-130 завершён, RM-131 активирован

- Audit `docs/RM-130_AUDIT.md` и implementation plan зафиксированы docs-only commit `09d60cc` до
  application changes; expected-red characterization — commit `f206c0d`.
- Existing `TenderSearchProfileRepository` повышен до schema v2 в прежнем
  `<data_directory>/search_profiles.json`; immutable typed load fail-closed различает
  missing/current/migrated-v1/corrupt/future и не уничтожает original.
- Первая explicit mutation valid v1 создаёт byte-for-byte backup и atomic replace; corrupt/future
  source не перезаписывается, replace failure сохраняет original и очищает temp.
- Canonical built-in ID membership является единственным источником built-in identity; custom
  profiles, disabled state, IDs и deterministic order сохраняются при load/migration/restore.
- `SAVED_PROFILE` и `KEYWORD_OVERRIDE` фиксируют существующую RM-128 семантику; transient text
  заменяет только keywords текущего запуска и не изменяет model/repository bytes.
- Profile price editor использует exact Decimal-safe boundary без float; explicit currency и
  aware-or-unknown timestamps сохраняются без guessed timezone.
- Один repository/path/dialog/editor/unified panel/Collector worker owner сохранён; legacy sync
  runner, async Collector, scheduler profile-ID behavior и RM-129 business projection не заменены.
- DB/schema/migrations, dependencies, provider settings/credentials, normalization/ranking,
  score/recommendation/critical stop-factor, AI и RM-131+ production scope не изменены.
- Локальная acceptance: focused `82 passed in 9.68s`, neighbor `64 passed in 6.33s`, full pytest
  `1656 passed in 60.73s`; secret scan, Ruff/format (`554 files`), mypy, workflow smokes,
  dependency audit и diff-check успешны.
- Feature PR #66 (`feat(rm-130): add safe saved search profile schema v2`) слит в `main` коммитом
  `3a4d530` (`3a4d53067b7b0f8eaf0b5969c139284c9d5ed987`).
- PR Quality Gate run `29533900495` успешен: Python 3.12 — `1656 passed in 101.17s`, Python 3.13 —
  `1656 passed in 150.85s`.
- Exact merge-SHA run `29534568925` успешен: Python 3.12 — `1656 passed in 141.74s`,
  Python 3.13 — `1656 passed in 66.21s`; все обязательные jobs завершились `success`.
- RM-130 переведён в `DONE`; RM-131 назначен единственным `IN PROGRESS` для audit-first
  консолидации existing provider settings/catalog. RM-132–RM-200 остаются `PLANNED`.

## 2026-07-16 — RM-129 завершён, RM-130 активирован

- Audit `docs/RM-129_AUDIT.md` и implementation plan зафиксированы docs-only commit `ddb8427` до
  application changes; expected-red characterization — commit `3331131`.
- Existing `CompanyCapabilityProfileRepository` повышен до schema v2 в том же JSON path; v1
  мигрируется in memory, typed load fail-closed различает missing/current/migrated/corrupt/future и
  не уничтожает original.
- Content-bound confirmation version 1 связывает все decision facts с deterministic SHA-256;
  explicit currency, decimal strings и aware UTC timestamps сохраняются без guessed capabilities.
- Pure frozen `BusinessCapabilityProjection` является одной confirmed-facts boundary для manual score,
  automatic Collector и stop-factor engine; runtime/controller/dialog разделяют existing repository.
- V1/v2 golden score components/explanations/recommendation, stop и final decision совпадают; matching,
  saved search, DB/migrations, provider/network, AI и `ParticipationDecisionService` не изменены;
  critical block остаётся абсолютным.
- Локальная acceptance: focused `76 passed in 5.25s`, neighbor `38 passed in 6.85s`, adjacent
  summary/full-analysis `51 passed in 3.53s`, full pytest `1623 passed in 70.35s`; secret scan,
  Ruff/format (`549 files`), mypy, workflow smokes, dependency audit и diff-check успешны.
- Feature PR #64 (`feat(rm-129): add universal confirmed business profiles`) слит в `main` коммитом
  `f9b43c3` (`f9b43c37bb5c7e631e4851cde2b39c1178d34239`).
- PR Quality Gate run `29522220375` успешен: Python 3.12 — `1623 passed in 164.70s`, Python 3.13 —
  `1623 passed in 63.03s`.
- Exact-SHA post-merge run `29522737754` успешен: Python 3.12 — `1623 passed in 69.59s`,
  Python 3.13 — `1623 passed in 103.67s`; все обязательные jobs завершились `success`.
- Неблокирующее предупреждение official actions о принудительном Node.js 24 не повлияло на gate и
  остаётся отдельной CI maintenance задачей.
- RM-129 переведён в `DONE`; RM-130 назначен единственным `IN PROGRESS` для audit-first upgrade
  existing saved-search profile contract. RM-131–RM-200 остаются `PLANNED`.

## 2026-07-16 — RM-129: feature acceptance подготовлена

- Audit `docs/RM-129_AUDIT.md` и implementation plan зафиксированы docs-only commit `ddb8427` до
  production changes; expected-red characterization — commit `3331131`.
- Существующий `CompanyCapabilityProfileRepository` повышен до schema v2 в том же JSON path;
  v1 мигрируется только in memory, typed load различает missing/current/migrated/corrupt/future,
  invalid/future original не перезаписывается.
- Content-bound confirmation version 1 exact-связывает все decision facts с deterministic SHA-256;
  explicit `base_currency` нормализуется, money остаётся decimal strings, timestamps — aware UTC.
- Pure frozen `BusinessCapabilityProjection` отделяет facts от Corteris completeness/scoring policy и
  fail-closed скрывает неподтверждённые capability facts.
- Manual recalculation и automatic Collector строят одну projection для existing ranker и
  `StopFactorEngine`; v1/v2 golden components/explanations/recommendation/stop/final-decision guards
  совпадают, critical block остаётся абсолютным.
- Existing runtime/controller/dialog используют один repository instance; UI вызывает domain
  confirmation, требует новое подтверждение после edit и показывает migrated/corrupt/future status без
  auto-save.
- Matching catalog/`canonical_term`, saved search profiles, DB/migrations, provider/network,
  dependencies, AI и `ParticipationDecisionService` production code не изменены.
- Локальная acceptance на feature HEAD `a99252b`: focused `76 passed in 5.25s`, neighbor
  `38 passed in 6.85s`, adjacent summary/full-analysis `51 passed in 3.53s`, full pytest
  `1623 passed in 70.35s`; secret scan, Ruff/format (`549 files`), mypy, workflow smokes,
  dependency audit и diff-check успешны.
- Это feature evidence, не closeout: RM-129 остаётся `IN PROGRESS` до feature PR/merge, exact-SHA
  Windows Quality Gate 3.12/3.13 и отдельного docs-only closeout. RM-130 остаётся `PLANNED`.

## 2026-07-16 — RM-128 завершён, RM-129 активирован

- Audit `docs/RM-128_AUDIT.md` и implementation plan зафиксированы docs-only commit `39605d0` до
  application changes; expected-red characterization — commit `19aceba`.
- Одна `TenderUnifiedSearchPanel` встроена над existing tabs одной `TenderWorkspacePage`; topbar
  использует narrow page → panel → existing controller path и не меняет equipment `catalog_query`.
- Pure immutable request boundary использует existing `TenderSearchProfileRepository` snapshots,
  сохраняет profile query/`Decimal`/currency/dates и отклоняет unknown/disabled/stale provider без
  silent fallback или network.
- Unified panel, Collector dialog и scheduler разделяют один existing `TenderSearchUiController`,
  единственный `_CollectorRunWorker`, cancellation/progress/result cleanup и canonical registry.
- Unified path использует existing async `CollectorRunSession`; legacy sync profile dialog/runner
  сохранён до parity/retirement RM-138.
- Новый repository, engine, Collector, provider catalog, DB/migration, profile schema, dependency,
  decision или AI contract не добавлен; critical stop-factor priority неизменен.
- Локальная acceptance: focused `23 passed in 5.20s`, neighbor `66 passed in 8.80s`, full pytest
  `1552 passed in 61.49s`; secret scan, Ruff/format (`545 files`), mypy, workflow smokes,
  dependency audit и diff-check успешны.
- Feature PR #62 (`feat(rm-128): add unified tender search panel`) слит в `main` коммитом `a67f5df`
  (`a67f5df331f8257799e24a9ef3980c6feea69c7a`).
- PR Quality Gate run `29499175129` успешен: Python 3.12 — `1552 passed in 67.74s`, Python 3.13 —
  `1552 passed in 97.95s`.
- Exact-SHA post-merge run `29499519358` успешен: Python 3.12 —
  `1552 passed in 169.06s`, Python 3.13 — `1552 passed in 73.62s`; initial Python 3.12 native access
  violation не воспроизвёлся при rerun того же SHA. Все обязательные jobs завершились `success`.
- RM-128 переведён в `DONE`; RM-129 назначен единственным `IN PROGRESS` для audited generalization
  existing company capability без смешивания с saved search profiles. RM-130–RM-200 остаются
  `PLANNED`.

## 2026-07-16 — RM-127 завершён, RM-128 активирован

- Audit `docs/RM-127_AUDIT.md` и implementation plan были зафиксированы docs-only commit
  `13dfb83` до production changes; characterization contract — commit `cb21b82`.
- Existing tender content выделен как одна `TenderWorkspacePage(QWidget)` с exact 8 top-level и
  6 nested settings tabs, stable keys/objectNames и narrow compatibility API.
- Production `ModernMainWindow` больше не создаёт hidden legacy `MainWindow`, не вызывает
  `takeCentralWidget()` и не обращается к `table/current_id/catalog_query` напрямую; standalone
  legacy wrapper строит одну reusable page.
- Один существующий `TenderSearchUiController`, те же 7 direct и 2 scheduler QAction, menu/toolbar,
  shortcuts, dialogs, workers и C11 full-analysis workflow сохранены без дублирования.
- Topbar сохраняет прежний price/equipment catalog contract; universal search RM-128, новый engine,
  Collector, repository, DB/migration, provider, decision или AI changes не добавлены.
- Локальная acceptance: focused `54 passed in 31.02s`; полный pytest дважды —
  `1532 passed in 55.91s` и `1532 passed in 77.25s`; secret scan, Ruff, format, mypy,
  workflow smokes, dependency audit и diff-check успешны.
- Feature PR #60 (`feat(rm-127): isolate tender workspace in modern tab structure`) слит в `main`
  коммитом `0b95567` (`0b9556799a20ddbf7338476fe76f602e7ff79d07`).
- PR Quality Gate run `29488228903` успешен: Python 3.12 — `1532 passed in 94.14s`,
  Python 3.13 — `1532 passed in 83.76s`.
- Post-merge Quality Gate run `29489511239` успешен: Python 3.12 —
  `1532 passed in 82.83s`, Python 3.13 — `1532 passed in 145.43s`; на обеих версиях прошли
  Ruff check/format (`540 files`), mypy (20 файлов), secret scan,
  offline/migration/import/composition/build smoke tests и dependency audit.
- RM-127 переведён в `DONE`; RM-128 назначен единственным `IN PROGRESS` для одной search panel над
  существующим saved-profile repository и audited sync/async facade. RM-129–RM-200 остаются `PLANNED`.

## 2026-07-16 — RM-126.1 завершён, RM-127 активирован

- Feature PR #58 (`feat(rm-126.1): harden EIS parser stage 1`) слит в `main` коммитом `b6369c8`
  (`b6369c85791b9c06a97f03a1fbb2504c88a1dea7`).
- Post-merge Quality Gate run `29460395144` завершился статусом `SUCCESS`: Python 3.12 —
  `1524 passed in 95.38s`, Python 3.13 — `1524 passed in 71.31s`.
- На обеих версиях прошли Ruff check/format (`537 files`), mypy (20 файлов), repository secret scan,
  offline/migration/import/composition/build smoke tests и dependency audit.
- Audit `docs/EIS_PARSER_STAGE_1_AUDIT.md` и architecture plan были зафиксированы commit `955ec6a`
  до production changes; implementation commit `ca3e6c2` сохранил единую Collector/DI цепочку.
- `get_tender()` открывает detail-page; 44-ФЗ и 223-ФЗ разделены детерминированным router; mandatory
  fields и HTML drift проверяются fail-closed; добавлены parser versions, diagnostics, separate
  network/parser health, allowed hosts, opt-in sanitized snapshots, fixtures и read-only live canary.
- Новый Collector, HTTP client, tender model, persistence root, DB schema/migration, scoring или
  analysis workflow не добавлены; deterministic decision и critical stop-factor priority не изменены.
- Локальная приёмка: EIS/Collector target `69 passed in 6.35s`, full `1524 passed in 54.24s`,
  repository secret scan, Ruff, mypy, smoke tests, dependency audit и diff-check успешны.
- Live canary не запускался автоматически против внешней ЕИС; сетевой запуск остаётся явной
  operator action и не входит в offline CI.
- Общий RM-126, включая поздний подэтап RM-126.1, переведён в `DONE`; RM-127 назначен единственным
  `IN PROGRESS`, RM-128–RM-200 остаются `PLANNED`.

## 2026-07-16 — RM-126 переоткрыт для технического подэтапа RM-126.1

- После завершения audit/closeout RM-126 владелец проекта предоставил и явно подтвердил позднее
  дополнение `RM-126.1 — Аудит и укрепление текущего провайдера ЕИС`.
- История audit PR #55, closeout PR #56 и их успешных Quality Gate сохраняется без изменения: общий
  архитектурный аудит остаётся принятой завершённой частью RM-126.
- Для соблюдения порядка из дополнения общий RM-126 временно возвращён в `IN PROGRESS`, RM-126.1
  назначен единственным активным техническим подэтапом, а RM-127 возвращён в `PLANNED`.
- RM-126.1 обязан переиспользовать `AsyncHttpClient`, `AsyncProviderSearchEngine`,
  `AsyncEisTenderProvider`, `UnifiedTender`, `CollectorStateRepository`, verification/scoring/full
  analysis и существующий DI; второй Collector, HTTP client, model, database или workflow запрещены.
- До production-кода обязателен отдельный EIS parser audit. Условие завершения: feature merge,
  post-merge Windows Quality Gate и docs-only closeout; только затем активируется RM-127.
- Эта запись меняет только canonical ordering/status и не содержит production- или DB-изменений.

## 2026-07-16 — RM-126 завершён

- Audit PR #55 (`docs(rm-126): audit tenders section`) слит в `main` коммитом `f09d07e`
  (`f09d07ebb1a15acb42279d3b8f7e0393c8d84afc`).
- Post-merge Quality Gate run `29453928900` завершился статусом `SUCCESS`: Python 3.12 —
  `1496 passed in 76.46s`, Python 3.13 — `1496 passed in 157.55s`.
- На обеих версиях прошли Ruff check/format (`523 files`), mypy (20 файлов), repository secret
  scan, offline/migration/import/composition/build smoke tests и dependency audit.
- Entry baseline `7d51159a` прошёл target `395 passed in 36.20s` и full
  `1496 passed in 63.74s`; финальная локальная audit branch — target `395 passed in 33.99s`,
  full `1496 passed in 61.27s`, остальные workflow-equivalent checks и diff-check успешны.
- `docs/RM-126_AUDIT.md` фиксирует UI journeys, sync/async search comparison, provider/profile/
  credentials/persistence/lifecycle/downstream boundaries, 12 findings и семь evidence-based Mermaid
  diagrams; `docs/RM-126_REQUIREMENTS.md` задаёт обязательный handoff RM-127–RM-140.
- Приняты D-01–D-10: modern shell владеет единственной tender page; async Collector — целевой search
  boundary с временным sync facade; существующие provider manager, keyring, saved-profile repository,
  Collector normalization/verification и shared `tender_records` переиспользуются.
- C1–C20 распределены по одному основному RM из RM-127–RM-140; третьи search/provider/settings/
  credential/health/normalization/persistence owners запрещены.
- HIGH handoff для будущих этапов: embedded legacy UI, два search orchestration path, отсутствие
  общего tender shutdown и неоднородная timezone policy. Publication blocker не обнаружен.
- Audit и closeout не изменяют production-код, зависимости, DB schema или migrations и не выполняют
  live-запросы к площадкам; deterministic decision и абсолютный приоритет critical stop-factor сохранены.
- RM-126 переведён в `DONE`; RM-127 назначен единственным `IN PROGRESS` для изоляции tender page по
  D-01 после merge closeout и успешного финального Windows Quality Gate.

## 2026-07-15 — RM-125 завершён

- PR #53 (`Fix/rm 125 stabilize ai platform`) слит в `main` коммитом `bdceb70`
  (`bdceb70f0df1632baf83db4131a7ac4ed6215349`).
- Post-merge Quality Gate run `29450245855` завершился статусом `SUCCESS`: Python 3.12 —
  `1496 passed in 95.46s`, Python 3.13 — `1496 passed in 61.69s`.
- На обеих версиях прошли Ruff check/format (`523 files`), mypy (20 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Единый immutable execution contract v1 exact-связывает provider/model и все versioned
  boundaries анализа; analyzer повышен до v12, остальные утверждённые contracts сохранены.
- Typed cache lookup пропускает corrupt/future/mismatched rows, находит более старую exact
  current-compatible запись и не использует mutable production warning state.
- Empty-source analysis создаёт valid provenance без provider call; pure cacheability predicate
  исключает persistence без exact key/fingerprint/current contract/payload/provenance.
- Allowlisted provider failures получают fixed bounded warnings без raw exception text, retry
  или stale fallback.
- Per-key coordinator сериализует одинаковые run/recheck, сохраняет параллельность разных ключей
  и очищает lock state после исключения.
- Participation decision больше не использует implicit latest AI analysis; текущий AI-результат
  передаётся только явно через existing full-analysis path.
- Сохранены один provider call site, analyzer/service/Orchestrator/repository, одна
  `RUNNING_AI` stage и existing runtime graph; новая AI-stage, provider call, repository, БД,
  таблица или migration не добавлены.
- RM-107 score/recommendation/actions/evidence/confidence/commercial estimate и абсолютный
  приоритет critical stop-factor не изменены.
- Локальная приёмка: target `315 passed in 7.15s`, full `1496 passed in 58.68s`, Ruff
  (`523 files`), mypy (20 файлов), secret scan, dependency audit и diff-check успешны.
- RM-125 переведён в `DONE`; RM-126 назначен следующим активным этапом только для отдельного
  будущего аудита раздела Тендеры.

## 2026-07-15 — RM-124 завершён

- PR #51 (`feat(rm-124): add explainable AI recheck`) слит в `main` коммитом `cfd044e`
  (`cfd044e2ff437819aabe16864c4426d9b4ad8fd8`).
- Post-merge Quality Gate run `29437124384` завершился статусом `SUCCESS`: Python 3.12 —
  `1466 passed in 108.68s`, Python 3.13 — `1466 passed in 80.07s`.
- На обеих версиях прошли Ruff check/format (`521 files`), mypy (20 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Pure recheck policy v1 exact-сравнивает analyses одного registry/fingerprint/provider/model/
  version contract, игнорирует меняющиеся technical provenance fields и использует только
  locally verified findings.
- Finding identity основан на `scope + category + citation_id`; added/removed/modified delta и
  ordering deterministic, heuristic matching и promotion unverified findings отсутствуют.
- Existing service/orchestrator строит context/fingerprint один раз, захватывает exact baseline до
  append-only current save и вызывает analyzer ровно один раз. Automatic retry, critic pipeline и
  stale baseline fallback не добавлены.
- Repository read failure не блокирует current request; current provider failure получает
  `current_unavailable`, не заменяется baseline и не сохраняется.
- Existing AI dialog использует confirmation/background worker/per-registry guard, а existing
  JSON/HTML exporter — optional safe `ai_recheck`; новая UI tab или `RUNNING_AI` stage не создана.
- Provider schema/format v4, prompt v6, payload v10, analyzer v11, context v6, citation resolver v1
  и physical SQLite schema не изменены. Сохранены один provider call site, analyzer/service/
  Orchestrator/repository и runtime graph.
- RM-107 score/recommendation/actions/evidence/confidence/commercial estimate и абсолютный
  приоритет critical stop-factor не изменены.
- Локальная приёмка: target `150 passed in 5.70s`, full `1466 passed in 56.89s`, Ruff
  (`521 files`), mypy (20 файлов), secret scan, dependency audit и diff-check успешны.
- RM-124 переведён в `DONE`; RM-125 назначен следующим активным этапом только для отдельного
  будущего аудита и стабилизации AI-платформы.

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
