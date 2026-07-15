# RM-124 — контракт повторной проверки AI

Baseline: `52c1f5ce72c13f945817225ba2e1e35e9bf400f0`.

Architecture audit: `docs/RM-124_AUDIT.md`.

## Назначение

RM-124 добавляет явную пользовательскую операцию «Повторно проверить AI»: один новый provider
request при том же локальном контексте, exact baseline из append-only history, deterministic
сравнение и объяснение изменений. Операция не является автоматическим retry, critic pass или
второй AI-цепочкой.

Обязательный disclaimer:

> Повторная проверка оценивает воспроизводимость AI-анализа при одинаковом локальном контексте.
> Совпадение результатов не подтверждает фактическую, юридическую или коммерческую правильность
> выводов.

## Immutable domain contract

Новый pure module `app/core/ai/recheck.py` определяет frozen/slots types:

```text
AiRecheckStatus
AiRecheckChangeType
AiRecheckDelta
AiRecheckAssessment
TenderAiRecheckResult
```

`AiRecheckStatus` exact values:

```text
consistent
changed
baseline_missing
current_unavailable
not_comparable
```

`AiRecheckChangeType`: `added`, `removed`, `modified`.

`AiRecheckDelta` содержит `change_type`, `scope`, `category`, `citation_id`,
`previous_statement`, `current_statement`.

`AiRecheckAssessment` содержит `policy_version`, `status`, `registry_key`,
`context_fingerprint`, baseline/current analysis ID и created_at, provider/model,
baseline/current digest, `unchanged_count`, `added_count`, `removed_count`, `modified_count`,
`summary_changed`, `final_conclusion_changed`, `missing_documents_changed`, `deltas`, `warnings`.

`TenderAiRecheckResult` — safe application envelope с registry key, current analysis,
assessment, started/completed timestamps и bounded warnings. Полный baseline payload в envelope
не хранится.

## Pure comparator

```text
AI_RECHECK_POLICY_VERSION = "1"
compare_ai_analyses(
    baseline: AiDocumentAnalysis | None,
    current: AiDocumentAnalysis,
) -> AiRecheckAssessment
```

Comparator не выполняет I/O и не читает provider/repository. Comparability требует:

- baseline/current status `complete` или `partial`;
- valid current и baseline provenance/schema;
- одинаковые registry key и context fingerprint;
- одинаковые prompt/output schema/persisted schema/analyzer/context/citation resolver versions;
- одинаковые provider ID и model.

Отсутствующий baseline даёт `baseline_missing`. Недоступный current provider result даёт
`current_unavailable`. Любое другое нарушение exact invariants даёт `not_comparable` с fixed safe
warning.

Semantic digest и comparison игнорируют `created_at`, `analysis_id`, `provider_response_id` и
repository warnings. Сравниваются canonical summary, final conclusion, missing documents,
root/specialized statuses и только locally verified findings.

Finding exact key: `scope + category + citation_id`. При одинаковом ключе изменённый statement
даёт `modified`; появление/исчезновение — `added`/`removed`; exact unchanged — unchanged count.
Неоднозначность никогда не разрешается heuristic matching. Unverified finding не включается и не
повышается. Ordering deterministic и не зависит от входного порядка.

## Service и orchestrator

`TenderDocumentAiAnalysisService.recheck(registry_key)`:

1. валидирует key;
2. один раз строит existing local context и fingerprint;
3. один раз выполняет `repository.reusable(key, fingerprint)` и захватывает exact baseline;
4. обходит cache return и вызывает existing analyzer ровно один раз;
5. применяет тот же inventory/scoped/documentation/legal/financial/competition postprocess;
6. сохраняет допустимый current analysis existing append-only repository;
7. pure-сравнивает captured baseline и current.

Обычный `analyze(force=False)` сохраняет текущую cache семантику. Recheck — отдельный method, а не
перегрузка `force`.

Repository read failure не блокирует current request: assessment `baseline_missing` и fixed safe
warning. Provider/current failure: `current_unavailable`, baseline не возвращается как fallback,
failed current не сохраняется. Repository write failure не отменяет сравнение, но добавляет safe
warning.

`TenderAiOrchestrator.recheck(registry_key)` делегирует service и изолирует unexpected boundary
failure; repository напрямую не читает. Runtime продолжает использовать один orchestrator.

## UI

Existing `TenderFullAnalysisDialog`:

- signal `ai_recheck_requested(str)`;
- кнопка «Повторно проверить AI»;
- кнопка enabled только для current complete/partial analysis с valid provenance и когда recheck
  не выполняется;
- confirmation exact text:
  `Будет выполнен один новый запрос к выбранному AI-провайдеру. Кеш текущего анализа использоваться не будет.`;
- во время worker run кнопка disabled, повторный click игнорируется, message
  «Повторная проверка AI…»;
- result block отображается в existing AI tab: status, baseline/current metadata, counts, deltas,
  warnings и disclaimer.

Controller использует existing thread pool/QRunnable/signal pattern и отдельный per-registry
in-flight guard. Новая вкладка, full-analysis stage или synchronous provider call в UI запрещены.

## Export и security

Existing `TenderAiAnalysisExporter.export(...)` получает optional recheck assessment. При
отсутствующем assessment существующая JSON/HTML семантика не меняется. При наличии:

- JSON содержит root `ai_recheck`;
- HTML содержит escaped recheck section;
- export содержит status/policy, safe metadata/digests/counts/flags/deltas/warnings/disclaimer;
- не содержит full baseline/current payload, raw response, source URL/path, raw error/traceback,
  credentials или document text.

Locally verified citation ID разрешён; statement и все metadata bounded/escaped.

## Versions и persistence

```text
provider output schema: 4 (без изменения)
response format: corteris_tender_analysis_v4 (без изменения)
prompt: 6 (без изменения)
persisted payload: 10 (без изменения)
analyzer: 11 (без изменения)
context: 6 (без изменения)
citation resolver: 1 (без изменения)
recheck policy: 1
```

Recheck assessment отдельно не сохраняется. Physical SQLite schema, migrations, provider JSON
schema и `AiDocumentAnalysis` payload не меняются.

## RM-107 и acceptance

Recheck не входит в participation score/recommendation/actions/evidence/confidence, critical stop
factors или commercial estimate. `participation_decision_policy.py` и
`collector/participation_score.py` не изменяются.

RED tests обязаны доказать отсутствие нового module/types/comparator/service/orchestrator/UI/export
контракта. Feature acceptance включает:

- `tests/test_ai_recheck.py`;
- `tests/test_ai_document_analysis_service.py`;
- `tests/test_ai_orchestrator.py`;
- `tests/test_ai_document_analysis_repository.py`;
- `tests/test_tender_full_analysis_dialog.py`;
- `tests/test_tender_ai_analysis_export.py`;
- `tests/test_tender_search_runtime.py`;
- `tests/test_participation_decision_service.py`;
- полный pytest, Ruff check/format, mypy, secret scan, pip-audit и `git diff --check`.

Статический acceptance подтверждает один production `provider.analyze(...)`, один analyzer/
service/orchestrator/repository, одну `RUNNING_AI` stage, unchanged versions/SQLite/provider schema
и отсутствие изменений в двух production-файлах RM-107.

## Feature acceptance

Окружение: Python `3.12.7`, project `.venv`, `QT_QPA_PLATFORM=offscreen`, worktree-local
`TEMP/TMP` и pytest `--basetemp`.

- Baseline SHA: `52c1f5ce72c13f945817225ba2e1e35e9bf400f0`.
- Feature SHA: `788d1e43c79545c1540623f2685012c1039f0fc5`.
- Обязательный eight-file target contour: `150 passed in 5.70s`.
- Расширенный target с UI-controller regression: `154 passed in 5.70s`.
- Полный suite: `1466 passed in 56.89s`.
- `python -m ruff check .`: passed.
- `python -m ruff format . --check`: passed (`521 files already formatted`).
- `python -m mypy`: passed (`20 source files`).
- `python scripts/check_repository_secrets.py`: passed.
- `python -m pip_audit --skip-editable`: no known vulnerabilities; editable project skipped as
  expected.
- `git diff --check`: passed.

RED target до production implementation завершился шестью collection errors с единственной
причиной `ModuleNotFoundError: app.core.ai.recheck`. После добавления pure module, отдельного
service/orchestrator API, UI worker и optional exporter тот же target прошёл полностью.

Статический acceptance подтвердил один production `provider.analyze(...)`, один
`TenderAiOrchestrator`, один `AiDocumentAnalysisRepository`, одну enum/stage пару `RUNNING_AI` и
одно production-использование stage. Pure comparator импортирует только standard-library
dataclass/enum/hash/JSON и immutable AI schema; I/O, network, repository, provider, UI,
participation score, company profile и document text не используются.

Фактические версии не изменены: provider output schema `4`, response format
`corteris_tender_analysis_v4`, prompt `6`, persisted payload `10`, analyzer `11`, context `6`,
citation resolver `1`; recheck policy имеет версию `1`. Provider schema, `AiDocumentAnalysis`
payload, physical SQLite schema и migrations не менялись.

Recheck захватывает exact reusable baseline до append-only current save, строит context/fingerprint
один раз и вызывает existing analyzer ровно один раз. Repository read failure не блокирует current
request; current provider failure даёт `current_unavailable`, не заменяется baseline и не
сохраняется. Normal `analyze(force=False)` cache semantics подтверждена полным regression suite.

Existing AI tab получил одну кнопку/confirmation/background worker и result block без новой
вкладки или `RUNNING_AI` stage. JSON/HTML без recheck сохраняет прежний payload path; optional
`ai_recheck` содержит только safe assessment metadata/deltas/warnings/disclaimer с HTML escaping,
без full baseline/current payload, raw provider response, URL/path, credentials или document text.

Production-файлы `app/tenders/participation_decision_policy.py` и
`app/tenders/collector/participation_score.py` не изменены. Tests подтвердили отсутствие recheck в
deterministic score/stop policy; score, recommendation, actions, evidence, confidence, commercial
estimate и абсолютный приоритет critical stop factor не меняются.

Глобальный Python не содержал dev dependency `mypy`, поэтому canonical команды выполнены через
project `.venv`. Первый sandbox-запуск dependency audit ожидаемо не имел сетевого доступа к PyPI;
повтор с разрешённой сетью и worktree-local cache прошёл без изменения кода.
