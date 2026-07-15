# RM-125 — аудит стабильности AI-платформы

Дата аудита: 15 июля 2026 года.

Baseline: `a54ca0b039af95beedd81c1736be6151a3a58616` (`main`).

Ветка: `fix/rm-125-stabilize-ai-platform`.

## Entry gate

- `docs/ROADMAP.md` и `docs/STATUS.md` фиксируют RM-124 как `DONE`, RM-125 как единственный
  `IN PROGRESS`, RM-126–RM-200 как `PLANNED`.
- Feature PR RM-124 #51 слит коммитом
  `cfd044e2ff437819aabe16864c4426d9b4ad8fd8`.
- Docs-only closeout PR RM-124 #52 слит baseline-коммитом
  `a54ca0b039af95beedd81c1736be6151a3a58616`.
- Feature post-merge Quality Gate run `29437124384` прошёл на Python 3.12
  (`1466 passed in 108.68s`) и Python 3.13 (`1466 passed in 80.07s`).
- Финальный main Quality Gate run `29440757813` прошёл на Python 3.12
  (`1466 passed in 58.66s`) и Python 3.13 (`1466 passed in 92.25s`).
- Локальный existing target RM-125: `285 passed in 6.82s`.
- Локальный full suite: `1466 passed in 58.25s`.

Первый локальный target без worktree-local `--basetemp` завершился `199 passed, 86 errors`:
ошибки возникли только при setup системных pytest temporary-directory fixtures. Один failing
test с локальным `--basetemp` прошёл, затем весь target и full suite прошли без изменения кода.
Это подтверждённое ограничение среды, а не regression baseline.

Entry gate пройден. До фиксации этого аудита application-код RM-125 не изменялся.

## Проверенный контур и владельцы

Проверены provider metadata/client, единственный analyzer call site, prepared context и service,
append-only repository, provenance/schema deserialization, recheck comparator, orchestrator,
full-analysis composition, production dependency injection, Participation Decision, existing Qt
dialog/controller worker и JSON/HTML exporter.

- Единственный production `provider.analyze(...)` находится в
  `TenderDocumentAiAnalyzer.analyze()`.
- Существуют по одному `TenderDocumentAiAnalyzer`, `TenderDocumentAiAnalysisService`,
  `TenderAiOrchestrator` и `AiDocumentAnalysisRepository` в production runtime.
- `create_tender_search_runtime()` создаёт один общий AI graph и одну SQLite repository.
- Full analysis содержит одну `RUNNING_AI` stage; UI содержит одну existing AI tab и фоновые
  workers; exporter имеет один normal path и optional `ai_recheck`.
- Новая таблица, колонка, migration, provider client/call, analyzer, service, orchestrator,
  repository, stage, tab или exporter для RM-125 не требуются.

## Подтверждённые дефекты

### 1. Cache не учитывает provider/model

`context_fingerprint(...)` включает документы и версии, но не sanitized provider metadata.
`TenderDocumentAiAnalysisService.analyze()` вызывает
`repository.reusable(registry_key, fingerprint)`, а repository возвращает первый valid current
payload независимо от `provenance.provider_id` и `provenance.provider_model`. После смены
provider/model обычный запуск может вернуть cache другого execution contract.

Решение: один immutable `AiExecutionContract`, построенный из current versions и
`AiProviderMetadata`, exact lookup по полному contract. Provider/model не добавляются в context
fingerprint: fingerprint остаётся идентичностью локального контекста, contract — идентичностью
исполнения.

### 2. Recheck может выбрать неправильный baseline

`recheck()` использует тот же contract-unaware `reusable(...)`. Если newest row принадлежит
другому provider/model, comparator возвращает `not_comparable`, не продолжая поиск более старого
exact baseline.

Решение: repository newest-first пропускает incompatible execution contracts и возвращает первый
exact match. Отсутствие exact match означает `baseline_missing`.

### 3. Repository warning является mutable side channel

`AiDocumentAnalysisRepository.last_warning` сбрасывается и изменяется каждым lookup. Service
читает его через `getattr(...)`. Один shared runtime repository используется background workers,
поэтому warning одного lookup может быть перезаписан другим.

Решение: immutable `AiCacheLookupResult` с `analysis`, `warnings` и `skipped_rows`; production
`last_warning` удалить. Lookup warnings принадлежат только конкретному вызову.

### 4. `no_documents` сохраняется, но не переиспользуется

Analyzer возвращает `no_documents` до построения provenance. Service сохраняет результат только
по status, а repository позднее отклоняет row без provenance. Каждый запуск создаёт новую запись.

Решение: создать current empty-source provenance без provider call, с current fingerprint и
execution contract, empty provider response ID. Результат сохраняется один раз и exact-reuse
возвращает его при неизменном empty context.

### 5. Результат без provenance может быть сохранён

При исключении в `_build_provenance()` analyzer удаляет verified findings и возвращает safe
warning, но status может остаться `complete`/`partial`. Status-only save predicate сохраняет row,
который следующий lookup отклонит.

Решение: единый pure cacheability predicate проверяет status, key, current payload version,
fingerprint, exact execution contract и existing local verification invariants до любого save.

### 6. Provider failure теряет bounded причину

`OpenAICompatibleProvider` уже возвращает fixed `error_code` и `retryable`, но analyzer сводит
любой `status != ok` к одному `provider_error`. Raw `message` уже не используется и не должен
использоваться далее.

Решение: allowlist кодов из ТЗ отображается на фиксированные ограниченные русские warnings;
unknown code получает generic warning. `retryable=True` не запускает retry, backoff, failover или
stale fallback.

### 7. Application boundary не сериализует same-key execution

`TenderAiOrchestrator.run()` и `recheck()` напрямую делегируют service. UI recheck guard является
только UX-защитой; normal full-analysis worker и recheck worker одного key могут одновременно
вызвать shared service/provider/repository.

Решение: per-registry coordinator внутри existing orchestrator. Один key сериализуется, разные
keys остаются параллельными; lock освобождается при exception, registry entry удаляется после
последнего пользователя. Global lock, polling и sleep запрещены.

### 8. Participation Decision имеет implicit historical fallback

`ParticipationDecisionService.evaluate()` использует sentinel `_USE_LATEST_AI_ANALYSIS` и при
отсутствии explicit argument вызывает `ai_analysis_repository.latest(key)`. Runtime передаёт
repository в Decision Service, хотя full analysis уже явно передаёт current orchestration result.

Решение: default `ai_document_analysis=None`, удалить sentinel, implicit `latest(...)` и
repository dependency. Standalone evaluation становится deterministic-only; full analysis
продолжает явно передавать current result; recheck не пересчитывает решение.

## Versions и persistence

Фактический baseline:

```text
provider output schema: 4
response format: corteris_tender_analysis_v4
prompt: 6
persisted payload: 10
analyzer: 11
context: 6
citation resolver: 1
recheck policy: 1
```

RM-125 добавляет execution contract version `1` и повышает analyzer version до `12`, потому что
меняются cacheability и execution/cache semantics. Provider schema/format, prompt, payload,
context, citation resolver и recheck policy не меняются. Execution identity уже полностью
представима existing provenance, поэтому payload shape и physical SQLite schema не меняются;
migration не требуется.

## Security и RM-107

Contract получает provider/model только из sanitized `AiProviderMetadata`; base URL, credential,
account/project data в него не входят. Repository/provider/orchestrator failures используют fixed
warnings без raw exception, response, URL/path, document text, traceback или secret. Existing
UI/export escaping и optional recheck payload переиспользуются.

`TenderFullAnalysisService` уже явно передаёт current analysis в RM-107. RM-125 удаляет только
historical fallback. `app/tenders/participation_decision_policy.py` и
`app/tenders/collector/participation_score.py` не изменяются. Score, recommendation, actions,
evidence, confidence, commercial estimate и абсолютный приоритет critical stop-factor остаются
детерминированными.

## Решение аудита

Добавить один pure `app/core/ai/execution_contract.py`, расширить existing prepared invocation,
repository/service/analyzer/orchestrator и удалить implicit Decision Service fallback. Existing
runtime graph, recheck comparator, UI/export, append-only table и provider call переиспользуются.
Production diff допустим только для закрытия RED acceptance contract.
