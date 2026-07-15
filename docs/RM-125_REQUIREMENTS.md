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

## Feature acceptance

Окружение: Python `3.12.7`, project `.venv`, `QT_QPA_PLATFORM=offscreen`, worktree-local
`--basetemp` и pip-audit cache.

- Baseline SHA: `a54ca0b039af95beedd81c1736be6151a3a58616`.
- Audit commit: `82cdcbcb10980671b2ab787efd6f07b6dbb620ad`.
- RED commit: `8382e102a5faf76610ea0921bd25e758118d4dab`.
- Implementation commit: `715a4b2d6654e6419da9c157275e1bc9ec0bbb05`.
- Обязательный 13-file target: `315 passed in 7.15s`.
- Полный suite: `1496 passed in 58.68s`.
- `python -m ruff check .`: passed.
- `python -m ruff format . --check`: passed (`523 files already formatted`).
- `python -m mypy`: passed (`20 source files`).
- `python scripts/check_repository_secrets.py`: passed.
- `python -m pip_audit --skip-editable --cache-dir .tmp/pip-audit-cache`: no known
  vulnerabilities; editable project skipped as expected.
- `git diff --check`: passed.

Первый dependency-audit в sandbox подтвердил только запрет socket и недоступность host cache;
канонический повтор с разрешённой сетью и worktree-local cache прошёл без изменения кода.

Статический acceptance подтвердил:

- один production `provider.analyze(...)` call site в existing analyzer;
- по одному production `TenderAiOrchestrator` и `AiDocumentAnalysisRepository` construction;
- одну enum/stage пару `RUNNING_AI` и одно execution-использование stage;
- отсутствие production `last_warning`, `_USE_LATEST_AI_ANALYSIS` и
  `ai_analysis_repository.latest(...)`;
- отсутствие retry/backoff/sleep в AI orchestrator/service и отсутствие нового provider retry;
- отсутствие diff в `participation_decision_policy.py` и `collector/participation_score.py`;
- отсутствие новой AI tab/stage, SQLite table/column/migration и второго runtime graph.

Execution contract version `1` exact-сопоставляет prompt/provider schema/payload/analyzer/context/
citation versions и sanitized provider/model. Repository возвращает immutable lookup result,
пропускает corrupt/future/different-contract rows и находит newest exact baseline ниже них.
`no_documents` имеет current empty-source provenance, не вызывает provider, сохраняется один раз и
переиспользуется. Результат без exact current provenance не сохраняется.

Per-key orchestrator coordinator сериализует normal/recheck одного registry key, сохраняет
parallelism разных keys, освобождает lock при exception и удаляет пустые entries. Provider failure
codes отображаются на fixed warnings без raw message/URL/path/secret/traceback и без automatic
retry/failover/stale fallback.

`ParticipationDecisionService` принимает только explicit current AI result; standalone вызов с
default `None` deterministic-only. Full analysis продолжает явно передавать orchestration result,
а recheck не пересчитывает decision. RM-107 score/recommendation/actions/evidence/confidence,
commercial estimate и абсолютный приоритет critical stop-factor не изменены.

Фактические версии после implementation: provider schema `4`, response format
`corteris_tender_analysis_v4`, prompt `6`, payload `10`, analyzer `12`, context `6`, citation
resolver `1`, recheck policy `1`, execution contract `1`. Physical SQLite schema не менялась.

Это feature acceptance, а не closeout. Обязательны feature PR merge, post-merge Windows Quality
Gate на Python 3.12/3.13 и отдельный merged docs-only closeout до статуса `DONE`.
