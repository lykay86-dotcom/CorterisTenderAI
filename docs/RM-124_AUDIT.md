# RM-124 — аудит повторной проверки AI

Дата аудита: 15 июля 2026 года.

Baseline: `52c1f5ce72c13f945817225ba2e1e35e9bf400f0` (`main`).

## Entry gate

- `docs/ROADMAP.md` фиксирует RM-123 как `DONE`, RM-124 как единственный `IN PROGRESS`,
  RM-125–RM-200 как `PLANNED`.
- Feature PR RM-123 #49 слит коммитом `759f015b2d101e56c9dc2a3db2ac57332b9d8ccc`.
- Docs-only closeout PR RM-123 #50 слит baseline-коммитом
  `52c1f5ce72c13f945817225ba2e1e35e9bf400f0`.
- Финальный main Quality Gate run `29432241449` на baseline SHA завершён успешно на Python
  3.12 и 3.13.
- Ветка `feat/rm-124-ai-recheck` создана от указанного baseline.

Entry gate пройден. До фиксации аудита application-код RM-124 не изменялся.

## Проверенный контур

Проверены канонические roadmap/DoD/history документы, ТЗ RM-124, provider analyzer,
`TenderDocumentAiAnalysisService`, `TenderAiOrchestrator`, append-only repository, provenance и
finding schemas, full-analysis composition, runtime dependency injection, existing Qt dialog и
controller workers, JSON/HTML exporter, а также deterministic participation decision/score
контур RM-107.

Статический поиск выполнен по `force`, `reusable`, `latest`, `context_fingerprint`,
`provider.analyze`, `RUNNING_AI`, background workers, export entry point, provenance versions,
verified citations и всем specialized finding collections.

## Единственные владельцы и вызовы

- Единственный production provider call — `provider.analyze(...)` внутри
  `TenderDocumentAiAnalyzer.analyze()`.
- `TenderDocumentAiAnalysisService.analyze()` один раз строит local context и fingerprint,
  использует `repository.reusable(...)` только при обычном non-force запуске, вызывает analyzer,
  применяет existing scoped/documentation/legal/financial/competition assessors и сохраняет
  допустимый результат.
- `TenderAiOrchestrator` — единственная application boundary над service; repository напрямую не
  читает.
- `AiDocumentAnalysisRepository` хранит append-only history в одной существующей таблице и уже
  предоставляет exact lookup `reusable(registry_key, fingerprint)`.
- `create_tender_search_runtime()` создаёт один graph context/analyzer/service/repository/
  orchestrator и передаёт orchestrator UI runtime.
- Full-analysis использует одну enum-стадию `RUNNING_AI`. Dialog содержит одну AI-вкладку, а
  controller — существующий `QRunnable`/signal pattern для фоновой работы.
- `TenderAiAnalysisExporter` — единственный JSON/HTML exporter AI-анализа.

RM-124 расширяет эти владельцы. Второй analyzer, prompt, provider client/call site, repository,
таблица, full-analysis stage, UI tab, controller или exporter не нужны.

## Текущая cache/force семантика

Обычный `analyze(force=False)` строит текущий fingerprint и возвращает exact reusable analysis,
если cache row валиден. `force=True` обходит lookup и выполняет новый analyzer call, однако не
сохраняет baseline и не формирует объяснимое сравнение. Поэтому существующий `force` не является
публичным контрактом recheck и не должен перегружаться новой семантикой.

Для RM-124 service получает отдельный `recheck(registry_key)`: context/fingerprint строятся один
раз, exact baseline захватывается до записи текущего результата, cache не возвращается вместо
нового результата, analyzer вызывается ровно один раз, затем применяется существующий postprocess
и append-only save. Ошибка чтения repository не блокирует новый вызов и даёт `baseline_missing` с
безопасным warning. Ошибка provider даёт `current_unavailable`; baseline не используется как
fallback и failed current result не сохраняется.

## Comparability и deterministic diff

`AiAnalysisProvenance` уже содержит registry context fingerprint, timestamps/analysis ID,
provider/model и все версии. Сравнение допустимо только для current/baseline со статусом
`complete` или `partial`, валидной provenance, одинаковыми registry key, fingerprint, versions,
provider и model.

Технически изменяемые `created_at`, `analysis_id`, `provider_response_id` и repository warnings
не являются semantic differences. Сравниваются summary, final conclusion, missing documents,
root findings и specialized findings/statuses. Finding включается только при locally verified
exact citation. Его exact identity — `scope + category + citation_id`; statement при том же ключе
даёт `modified`, отсутствие/появление — `removed`/`added`. Неоднозначные совпадения не
угадываются и не повышаются до verified.

Pure comparator не читает provider, repository, DB, filesystem, UI, company profile,
participation score или raw document text.

## Persistence и версии

Фактический baseline:

```text
provider output schema: 4
response format: corteris_tender_analysis_v4
prompt: 6
persisted payload: 10
analyzer: 11
context: 6
citation resolver: 1
```

RM-124 добавляет только recheck policy version `1`. Provider schema/format, prompt, payload,
analyzer, context, citation resolver и existing specialized policies не меняются. Recheck —
runtime assessment двух существующих append-only analyses; новый payload key, SQLite column,
table или migration не нужны.

## UI/export и security boundary

Existing `TenderFullAnalysisDialog` получает кнопку «Повторно проверить AI», confirmation и
signal `ai_recheck_requested(str)`. Кнопка доступна только для complete/partial result с valid
provenance и блокируется на время единственного background worker. Result отображается блоком на
существующей AI-вкладке; новая вкладка или full-analysis stage не создаются.

Exporter принимает optional recheck assessment. Без него JSON/HTML формируются прежним путём;
при наличии добавляется `ai_recheck`. Разрешены статусы, counts, safe provider/model metadata,
times, digest, deltas и locally verified citation IDs. Запрещены full baseline/current payload,
raw provider response, URL/path, raw error/traceback, credentials и document text. Все external
strings в HTML экранируются.

Обязательный disclaimer:

> Повторная проверка оценивает воспроизводимость AI-анализа при одинаковом локальном контексте.
> Совпадение результатов не подтверждает фактическую, юридическую или коммерческую правильность
> выводов.

## Граница RM-107

Recheck assessment является только диагностикой воспроизводимости. Он не передаётся в
`ParticipationDecisionService`, policy или collector score и не меняет score, recommendation,
actions, evidence, confidence, stop factors и commercial estimate. Production-файлы
`app/tenders/participation_decision_policy.py` и
`app/tenders/collector/participation_score.py` не изменяются. Critical deterministic stop factor
сохраняет абсолютный приоритет.

## Baseline acceptance

Окружение: Python `3.12.7`, project `.venv`, `QT_QPA_PLATFORM=offscreen`, worktree-local pytest
basetemp.

- Target existing contour: `126 passed in 19.74s`.
- Full suite: `1442 passed in 74.73s`.
- Ruff check: passed.
- Ruff format check: passed (`519 files already formatted`).
- mypy: passed (`20 source files`).
- repository secret scan: passed.
- dependency audit: no known vulnerabilities; editable project skipped as expected.

Глобальный Python не содержал dev dependency `mypy`; canonical проверки повторены через project
`.venv`. Первый sandbox-запуск dependency audit не имел сетевого доступа к PyPI; повтор с
разрешённой сетью и worktree-local cache прошёл без изменения кода.

## Решение аудита

RM-124 реализуется одним pure модулем `app/core/ai/recheck.py`, отдельным service/orchestrator
методом `recheck`, existing repository exact lookup, existing analyzer/postprocess/save path,
одним UI background worker и optional расширением existing exporter. Никаких новых provider
семантик, автоматического retry, critic pipeline, stale fallback, БД/migration, AI stage или
влияния на RM-107 не добавляется.
