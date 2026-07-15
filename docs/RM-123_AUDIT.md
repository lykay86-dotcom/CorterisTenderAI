# RM-123 — аудит полноты документации

Дата аудита: 15 июля 2026 года.

Baseline: `8e5947e993a3d61cc6697abe4f410cb0771d2697` (`main`).

## Entry gate

- `docs/ROADMAP.md` фиксирует RM-122 как `DONE`, RM-123 как единственный `IN PROGRESS`,
  RM-124–RM-200 как `PLANNED`.
- `docs/STATUS.md` назначает RM-123 активным только после feature merge RM-122, успешного
  post-merge Windows Quality Gate и merged docs-only closeout.
- Feature PR RM-122 #47 слит коммитом
  `4ebbf6c4dc4cf004e234310a7bc0fdf959ee17c6`.
- Docs-only closeout PR RM-122 #48 слит коммитом
  `8e5947e993a3d61cc6697abe4f410cb0771d2697`.
- Финальный main Quality Gate run `29423396195` на closeout merge SHA завершён успешно на
  Python 3.12 и Python 3.13. На обеих версиях прошли полный pytest, Ruff check/format, mypy,
  secret scan, offline/migration/composition/build smoke tests и dependency audit.
- Ветка `feat/rm-123-documentation-completeness` создана от указанного baseline.

Entry gate пройден. До фиксации этого аудита application-код RM-123 не изменялся.

## Проверенный контур

Проверены канонические roadmap/DoD/history документы и все production-файлы, перечисленные в
ТЗ: единый classifier, context, schema, analyzer/service, orchestrator, repository, provider
contract, document store, text extraction, full-analysis composition, RM-107 decision/score,
существующий AI exporter и AI tab. Дополнительно проверены ближайшие schema, persistence,
runtime, UI/export и participation regression tests.

Статический поиск выполнен по `completeness`, `missing_documents`, scoped document IDs, всем
context counters, `DocumentKind`, `list_documents`, `list_results`, `RUNNING_AI`,
`provider.analyze` и `AiDocumentAnalysisRepository`.

ТЗ называет отсутствующий baseline-файл `tests/test_tender_document_text_extractor.py`.
Фактический existing contour разделён между:

- `tests/test_tender_document_text_service.py`;
- `tests/test_tender_document_text_extractors.py`;
- `tests/test_document_text_extract_path.py`.

Baseline target использует эти реальные файлы. Новый обязательный RM-123 contract test будет
создан с именем из ТЗ, не заменяя существующие extraction tests.

## Единственные владельцы и AI component graph

- Единственный semantic classifier — `DocumentKind` и `classify_document_kind(...)` в
  `app/core/document_classification.py`.
- Единственный `TenderDocumentContextBuilder` читает latest local extraction results и строит
  `AiDocument` плюс `AiContextStatistics`.
- Единственный production provider call — `provider.analyze(...)` в
  `TenderDocumentAiAnalyzer.analyze()`.
- Единственные analyzer/service/orchestrator/repository — соответственно
  `TenderDocumentAiAnalyzer`, `TenderDocumentAiAnalysisService`, `TenderAiOrchestrator` и
  `AiDocumentAnalysisRepository`.
- `create_tender_search_runtime()` создаёт один граф из existing document store, text service,
  analyzer/service/repository/orchestrator.
- В `TenderFullAnalysisService` определена одна enum-стадия `RUNNING_AI` и одно production-
  использование этой стадии.
- Persisted history использует одну таблицу `tender_ai_document_analyses` и versioned
  `payload_json`.
- Существуют одна AI-вкладка и один JSON/HTML exporter.

RM-123 расширяет этот граф; второй classifier, provider call, prompt, analyzer/service,
orchestrator, repository, table, stage, UI tab или export format не нужны.

## Фактические версии baseline

```text
provider output schema: 4
response format: corteris_tender_analysis_v4
prompt: 6
context: 5
citation resolver: 1
persisted payload: 9
analyzer: 10
legal risk policy: 1
financial risk policy: 1
competition policy: 1
```

RM-123 повышает payload `9 -> 10`, analyzer `10 -> 11` и context `5 -> 6`, добавляет
documentation completeness policy `1`. Provider schema/format, prompt, citation resolver и
существующие specialized policies не меняются.

## Текущие local data sources

`TenderDocumentStore.list_documents(registry_key)` возвращает catalog record с internal
`document_key`, именем, download status, checksum и вычисляемым `available_locally`. Record также
содержит URL, private path и raw error; эти поля запрещены для нового snapshot.

`TenderDocumentTextService.list_results(registry_key)` возвращает все сохранённые extraction
revisions. В record есть status, checksum, character count, warnings и вычисляемый
`available_locally`; также присутствуют private paths и raw error. Context builder уже выбирает
latest revision детерминированно по timestamp/checksum/path, но сейчас не сохраняет canonical
inventory.

Archive members после безопасной распаковки проходят через existing `extract_path(...)` и
получают internal key с префиксом `archive-member:`. Они сохраняются в extraction catalog, но не
обязаны иметь record в document store. Новый join обязан сохранить их как safe local inventory
entry без исходного пути или URL.

`AiContextStatistics` уже содержит source/included/truncated/omitted/empty/duplicate/unavailable
counters и scoped found/included IDs для ТЗ, требований к заявке и проекта договора. Эти данные
сейчас входят в fingerprint через `context_parameters`, но полного inventory в fingerprint нет.

## Существующая completeness-модель

Общего documentation completeness assessor нет. Есть только три scoped status family:

- `AiTechnicalSpecificationStatus`;
- `AiApplicationRequirementsStatus`;
- `AiDraftContractStatus`.

Service применяет scoped context statistics после provider normalization. Отсутствующая область
получает `not_found`; omission/truncation даёт `partial`; provider/context failure даёт
`unavailable`. После этого локально пересчитываются legal, financial и competition assessments.

Download failure без extraction record сейчас увеличивает только store statistics и не попадает
в AI context. Extraction `failed`/`unsupported` и отсутствующий text file считаются unavailable;
partial extraction может войти в context, а warning остаётся только в extraction record. Empty,
duplicate, omitted и truncated records представлены агрегированными counters, но не отдельным
persisted document snapshot. Поэтому существующий payload не может объяснить неполноту по
конкретным document IDs.

Provider `missing_documents` остаётся частью strict provider schema. Это неподтверждённый AI-
список: он не является источником local completeness, issue ID или status. Existing RM-107
compatibility path может показывать его как missing-data hint; RM-123 не включает local
assessment в decision evidence/actions/score и в UI отделяет provider hint от локальных issues.

## Fingerprint и cache

`context_fingerprint(...)` хеширует включённые `AiDocument`, versions и context parameters.
Текущие statistics инвалидируют cache при изменении scoped counts/IDs и truncation, однако
download failure или catalog-only document не гарантированно представлены. RM-123 должен
передавать canonical inventory в fingerprint parameters. Тогда download/extraction status,
checksum, kind, inclusion и truncation каждого snapshot становятся cache-sensitive, а
перестановка входных records не влияет на hash.

Repository запрещает duplicate JSON keys через `object_pairs_hook`. Current payload локально
пересчитывает derived legal/financial/competition sections и exact-сравнивает сохранённое
значение. Тот же fail-closed pattern применим к documentation completeness.

## Persistence и migration

`tender_ai_document_analyses` уже хранит произвольный versioned JSON в `payload_json` и имеет
`payload_version`. Для двух новых root keys не нужны колонка, таблица или physical DB migration.
Legacy v1–v9 не содержит trusted inventory/assessment и должен вернуть empty unavailable
documentation assessment без переписывания строк. Future/corrupt payload остаётся incompatible
или безопасно пропускается.

## Граница RM-107

`_current_verified_ai_findings()` перечисляет только generic root `risks`,
`suspicious_conditions` и `contradictions`. Specialized sections и новый completeness assessment
туда не входят. `participation_decision_policy.py` и `collector/participation_score.py` остаются
без production-изменений. Новый snapshot/status/issues не влияют на score, recommendation,
actions, confidence, decision evidence или stop factors; critical deterministic stop factor
сохраняет абсолютный приоритет при score 100.

## UI/export и security boundary

Existing AI tab и exporter уже выполняют HTML escaping и показывают specialized sections.
RM-123 добавляет перед ними одну секцию «Полнота документации» с local status, counts, coverage,
issues/actions, warnings и обязательным disclaimer. Safe display name или internal ID допустимы;
URL, private path, raw errors/tracebacks, credentials, raw provider response и document text
запрещены.

Provider `missing_documents` отображается отдельно как «Возможные отсутствующие документы по
ответу AI — не подтверждено локальной проверкой» и не смешивается с local issues.

## Baseline acceptance

Окружение: Python `3.12.7`, `QT_QPA_PLATFORM=offscreen`, worktree-local `TEMP/TMP` и pytest
`--basetemp`.

- Target contour с фактическими extraction test files: `536 passed in 15.52s`.
- Full suite: `1389 passed in 58.38s`.
- Ruff check: passed.
- Ruff format check: passed (`517 files already formatted`).
- mypy: passed (`19 source files`).
- repository secret scan: passed.
- dependency audit: no known vulnerabilities; editable project skipped as expected.

Первый sandbox-запуск dependency audit не имел доступа к PyPI и global cache. Root cause —
ограничения среды; повтор с разрешённой сетью и worktree-local cache прошёл без изменения кода.

## Решение аудита

RM-123 реализуется расширением existing context с immutable canonical inventory, одним pure
`app/core/ai/documentation_completeness.py` и новыми immutable schema types. Service прикрепляет
inventory и пересчитывает assessment после scoped context для любого provider outcome.

Inventory входит в fingerprint. Current v10 строго валидируется и локально пересчитывается;
legacy/future/corrupt payload обрабатывается fail-closed. Provider contract, RM-107, physical DB,
UI navigation и число AI-вызовов не меняются.
