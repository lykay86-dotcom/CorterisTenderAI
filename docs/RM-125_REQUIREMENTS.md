# RM-125 — контракт стабильности AI-платформы

Baseline: `a54ca0b039af95beedd81c1736be6151a3a58616`.

Branch: `fix/rm-125-stabilize-ai-platform`.

Architecture audit: `docs/RM-125_AUDIT.md`.

## Immutable execution contract

Pure module `app/core/ai/execution_contract.py` определяет frozen/slots
`AiExecutionContract` с полями:

```text
contract_version
prompt_version
provider_output_schema_version
persisted_schema_version
analyzer_version
context_version
citation_resolver_version
provider_id
provider_model
```

`AI_EXECUTION_CONTRACT_VERSION = "1"`. Public helpers:

```text
current_execution_contract(provider_metadata) -> AiExecutionContract
execution_contract_from_provenance(provenance) -> AiExecutionContract | None
execution_contract_matches(provenance, expected_contract) -> bool
```

Provider/model берутся только из sanitized `AiProviderMetadata`. Equality exact; contract
строится один раз на invocation и используется cache, provenance/save predicate и recheck.

## Repository contract

Frozen/slots `AiCacheLookupResult` содержит:

```text
analysis: AiDocumentAnalysis | None
warnings: tuple[str, ...]
skipped_rows: int
```

`reusable(registry_key, context_fingerprint, expected_execution_contract)` выполняет newest-first
lookup, fail-closed пропускает invalid stored version, malformed/duplicate JSON, payload/schema,
registry/provenance/fingerprint и execution-contract mismatch, затем возвращает первый exact
match. Fixed warnings не содержат row/exception data. `last_warning` отсутствует. Append-only
history и existing physical SQLite schema сохраняются.

## Service/analyzer contract

Prepared invocation содержит documents, statistics, documentation inventory, fingerprint и
current execution contract, построенные один раз.

Normal run выполняет exact lookup, при hit не вызывает provider, при miss вызывает existing
analyzer не более одного раза. Force обходит cache return, но использует тот же postprocess и
cacheability predicate. Recheck захватывает exact baseline до current save, вызывает analyzer
ровно один раз и использует existing comparator.

Единый pure predicate разрешает save только для current `complete`, `partial`, `no_documents` с
exact key/fingerprint/execution contract/current payload и допустимыми locally verified findings.
Provider/invalid/provenance failure не сохраняется. Repository write failure не уничтожает safe
current result.

`no_documents` не вызывает provider, получает current empty-source provenance, empty response ID,
сохраняется один раз и exact-reuse возвращает его.

## Failure contract

Allowlisted provider codes из ТЗ отображаются только на fixed bounded Russian warnings. Unknown
code получает generic warning. Raw `message`, exception type/text, base URL, credential, private
path и traceback не переносятся в result/UI/export. `retryable` информационный: automatic retry,
backoff, failover и stale fallback отсутствуют. Disabled provider не выполняет сеть.

## Concurrency contract

Existing `TenderAiOrchestrator` сериализует `run(key)` и `recheck(key)` одного key. Второй normal
run после ожидания повторно проверяет cache; recheck после ожидания выполняет новый request по
своей семантике. Разные keys работают параллельно. Lock освобождается при exception, registry
entry удаляется после последнего пользователя. Global lock на execution, polling и sleep
отсутствуют.

## RM-107, UI/export и architecture

`ParticipationDecisionService.evaluate(..., ai_document_analysis=None)` не читает AI repository.
Full analysis явно передаёт current result; standalone evaluation deterministic-only; recheck не
пересчитывает decision. Current locally verified evidence и critical stop-factor semantics не
меняются. Production policy/score files не изменяются.

Переиспользуются existing AI tab/dialog/controller worker/guard и exporter. Не создаются второй
provider call, analyzer/service/orchestrator/repository/runtime graph, новая stage/tab/table/
column/migration, retry/critic/failover.

## Version matrix

```text
provider output schema: 4 -> 4
response format: corteris_tender_analysis_v4 -> corteris_tender_analysis_v4
prompt: 6 -> 6
persisted payload: 10 -> 10
analyzer: 11 -> 12
context: 6 -> 6
citation resolver: 1 -> 1
recheck policy: 1 -> 1
execution contract: absent -> 1
physical SQLite schema: unchanged
```

## Acceptance scenarios

Обязательны все 45 сценариев ТЗ: cache identity 1–5, recheck 6–11, repository safety 12–18,
cacheability/provenance 19–23, concurrency 24–28, failure/security 29–33, RM-107 boundary 34–39
и architecture 40–45.

Target contour:

```text
tests/test_ai_execution_contract.py
tests/test_ai_document_analysis_repository.py
tests/test_ai_document_analysis_service.py
tests/test_ai_document_analyzer.py
tests/test_ai_orchestrator.py
tests/test_ai_recheck.py
tests/test_openai_compatible_provider.py
tests/test_ai_provider_selection.py
tests/test_full_analysis_service.py
tests/test_participation_decision_service.py
tests/test_tender_search_runtime.py
tests/test_tender_full_analysis_dialog.py
tests/test_tender_ai_analysis_export.py
```

## Baseline acceptance

Окружение: Python `3.12.7`, project `.venv`, `QT_QPA_PLATFORM=offscreen`, worktree-local
`--basetemp`.

- Existing 12-file target: `285 passed in 6.82s`.
- Full suite: `1466 passed in 58.25s`.
- Static audit: один production `provider.analyze(...)`, один runtime graph, одна `RUNNING_AI`;
  подтверждены mutable `last_warning` и implicit Decision Service fallback.

Первый запуск с системным TEMP дал fixture-setup errors; канонический повтор с worktree-local
`--basetemp` прошёл без изменения кода.

## RED и feature acceptance

RED contract добавлен отдельным test package для immutable execution identity, provider/model-aware
cache, typed repository lookup, no-document provenance/cacheability, fixed provider failures,
same-key concurrency, lock cleanup, explicit RM-107 boundary и architecture invariants.

До production implementation 13-file target завершился одной collection error с точной причиной:

```text
ModuleNotFoundError: No module named 'app.core.ai.execution_contract'
1 error in 3.93s
```

Новый test file проходит Ruff check и Ruff format check. RED фиксируется commit
`test(rm-125): define AI platform stability contract`. Последующие target/full/Ruff/mypy/secret/
audit/diff результаты записываются сюда после соответствующих прогонов.

До feature merge, post-merge Windows matrix и отдельного docs-only closeout RM-125 остаётся
`IN PROGRESS`.
