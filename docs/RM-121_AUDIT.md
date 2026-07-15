# RM-121 — аудит существующих контуров финансового риска

Дата аудита: 15 июля 2026 года.

Baseline: `32510874291da502d6a588e32e633c01e736c274` (`origin/main`).

## Entry gate

- `docs/ROADMAP.md` и `docs/STATUS.md` фиксируют RM-120 как `DONE`, а RM-121 как
  единственный `IN PROGRESS`.
- Feature PR RM-120 #43 слит merge-коммитом
  `f2f87ff640082470bf822acee937ddd184ebcb23`.
- Post-merge Windows Quality Gate RM-120 run `29411717306` завершён успешно на Python 3.12 и
  Python 3.13.
- Docs-only closeout PR RM-120 #44 слит merge-коммитом
  `32510874291da502d6a588e32e633c01e736c274`.
- Финальный main Quality Gate после closeout, run `29412402372`, также завершён успешно на
  Python 3.12 и Python 3.13.
- Ветка реализации создана как `feat/rm-121-financial-risk-analysis` от указанного baseline.

Entry gate пройден. До этого аудита application-код RM-121 не изменялся.

## Проверенные файлы

- `app/tenders/commercial_estimator.py`;
- `app/tenders/collector/company_capability.py`;
- `app/tenders/collector/participation_score.py`;
- `app/tenders/requirement_analysis.py`;
- `app/tenders/participation_decision_service.py`;
- `app/tenders/full_analysis.py`;
- `app/core/ai/schemas.py`;
- `app/core/ai/output_schema.py`;
- `app/core/ai/analyzer.py`;
- `app/core/ai/repository.py`;
- `app/core/ai/legal_risk.py`;
- `app/reporting/tender_ai_analysis.py`;
- `app/ui/tender_full_analysis_dialog.py`;
- `app/tender_analysis/engine.py`.

Дополнительно проверен `app/estimates/calculator.py`, поскольку он содержит отдельный старый
UI-калькулятор и не должен быть ошибочно принят за текущий Tender Intelligence contract.

## Текущий AI-граф

Статический поиск подтвердил:

- единственный production-вызов `provider.analyze(...)` находится в
  `app/core/ai/analyzer.py`;
- определён один `TenderAiOrchestrator` в `app/core/ai/orchestrator.py`;
- определён один `AiDocumentAnalysisRepository` в `app/core/ai/repository.py`;
- в полном анализе существует одна стадия `RUNNING_AI` и одно её production-использование;
- bootstrap создаёт один analyzer/service/repository/Orchestrator graph;
- persisted AI history хранится в одной таблице `tender_ai_document_analyses` как versioned JSON.

RM-121 не требует второго provider call, analyzer, service, Orchestrator, repository, workflow,
stage, classifier или cache.

## Канонический коммерческий расчёт

`app/tenders/commercial_estimator.py` является каноническим числовым коммерческим расчётом
текущего Tender Intelligence:

- `CommercialCostLine`, `CommercialEstimateDraft` и `CommercialEstimateResult` используют
  `Decimal` для денежных значений и процентов;
- priced line требует `CommercialEvidence`;
- предложенная выручка и условия оплаты требуют evidence;
- неподтверждённая нулевая категория не принимается;
- отсутствие цены, категории, выручки, аванса или срока оплаты сохраняется в `missing_data`;
- неполный draft возвращает `DATA_INSUFFICIENT`, `total_cost`, `profit` и `margin_percent` не
  выдумываются;
- только при достаточных данных рассчитываются total cost, profit, margin, advance и financing
  exposure;
- `calculated_at` содержит timezone;
- repository сохраняет draft/result в существующем collector schema.

`app/estimates/calculator.py` — отдельный старый калькулятор главного окна с `float`; он не входит
в `TenderFullAnalysisService`, `ParticipationDecisionService` или evidence-backed commercial
repository. RM-121 его не импортирует и не расширяет. Это audited protocol/scope difference, а не
основание создавать третий калькулятор.

## Профиль финансовых возможностей

`CompanyCapabilityProfile` является каноническим источником явно подтверждённых лимитов
компании: `max_project_amount`, `working_capital`, `max_bid_security`,
`max_contract_security`, `bank_guarantee_limit`, `minimum_margin_percent`, допустимые сроки
оплаты и отсрочки. Денежные поля нормализуются в `Decimal`, timestamps требуют timezone, а
repository сохраняет только явно подтверждённый профиль.

RM-121 не должен читать профиль или сравнивать findings с лимитами. Рекомендуемое действие может
направить пользователя к ручной сверке, но policy остаётся чистой функцией только от
`AiDocumentAnalysis`.

## Существующие deterministic и legacy-контуры

`app/tenders/collector/participation_score.py` уже содержит deterministic scoring component
`financial` и текстовые признаки оплаты/аванса, а также использует подтверждённую проекцию
capability profile. `app/tenders/requirement_analysis.py` содержит отдельные rule-based
requirements и stop-factor findings. Эти правила остаются владельцами существующего score и не
копируются в новую AI policy.

`app/tender_analysis/engine.py` вычисляет legacy `financial_risk` из `float` margin thresholds и
смешивает его с устаревшими score/recommendation. Текущий full-analysis может запускать legacy
bridge как отдельный дополнительный этап, но новый AI-код не импортирует этот engine. RM-121 не
использует и не расширяет legacy `financial_risk`.

## Доступные специализированные источники

Текущая strict provider schema v4 уже нейтрально извлекает необходимые условия в существующие
requirements, technical specification и draft-contract buckets. Для RM-121 достаточно
фиксированной source policy над этими полями:

- requirements: price/estimate, security/guarantee, warranty, national regime, ambiguities,
  clarifications и contradictions;
- technical specification: scope/deliverables/volumes, materials/equipment,
  execution/schedule, acceptance, customer dependencies, ambiguities, clarifications и
  contradictions;
- draft contract: scope, schedule/location, price change, payment, acceptance, security,
  warranty, customer dependencies, subcontracting, liability, change/termination,
  ambiguities, clarifications и contradictions.

Generic root `risks`, `suspicious_conditions`, `contradictions`, legacy `RequirementFinding`,
commercial results и company profile не являются источниками нового registry. Category,
priority, title и action нельзя выводить из provider statement или regex.

## Evidence и provenance

`AiDocumentAnalysis.is_current_verified()` уже проверяет current provenance, checksum, context
fingerprint, canonical source ref и citation ID. RM-120 дополнительно показал безопасный шаблон
source-kind validation и локального пересчёта persisted derived section. RM-121 может переиспользовать
этот audited protocol, но со своей закрытой financial source policy.

Разрешённые source kinds:

- requirements — только текущие application source kinds;
- technical specification — только `TECHNICAL_SPECIFICATION`;
- draft contract — только `DRAFT_CONTRACT`.

Stale, altered, unverified, foreign-kind, duplicated-source и locator-conflicting evidence должно
обрабатываться fail-closed.

## Persistence и версии

Фактические версии baseline:

```text
provider output schema: 4
response format: corteris_tender_analysis_v4
prompt: 6
context: 5
citation resolver: 1
persisted payload: 7
analyzer: 8
legal risk policy: 1
```

Для RM-121 требуется повысить только persisted payload `7 -> 8` и analyzer `8 -> 9`, добавить
financial policy version `1`. Provider schema/format, prompt, context, citation resolver и legal
policy остаются без изменений.

Таблица `tender_ai_document_analyses` уже содержит `payload_json` и `payload_version`. Новая
колонка, таблица, migration или отдельный financial repository не требуются.

## Граница RM-107

`_current_verified_ai_findings()` в `app/tenders/participation_decision_service.py` перечисляет
только generic root `risks`, `suspicious_conditions` и `contradictions`. Specialized legal
assessment туда не входит, и financial assessment также не должен входить.

`ParticipationDecisionService` отдельно сохраняет `DATA_INSUFFICIENT` при отсутствующем или
неполном `CommercialEstimateResult`. Новый registry не должен менять score, thresholds,
recommendation, actions, decision evidence, stop factors или эту completeness-проверку.
Критический deterministic stop factor остаётся абсолютным даже при score 100.

## UI и экспорт

Существующая вкладка `AI-анализ` и существующий JSON/HTML exporter уже отображают specialized
sections и canonical internal citations. RM-121 должен добавить только секцию «Финансовые риски»
в эти поверхности. Новая вкладка, export format, source registry или citation resolver не нужны.
Внешний title/action/statement/warning обязан экранироваться; raw provider response, prompt,
полный документ, credentials, traceback и private paths не выводятся.

## Baseline acceptance

Окружение: Python `3.12.7`, `QT_QPA_PLATFORM=offscreen`, worktree-local `TEMP/TMP`.

- Существующий RM-121 target-контур без нового теста: `247 passed in 17.23s`.
- Полный suite: `1198 passed in 61.99s`.
- `python -m ruff check .`: passed.
- `python -m ruff format . --check`: passed (`513 files already formatted`).
- `python -m mypy`: passed (`17 source files`).
- `python scripts/check_repository_secrets.py`: passed.
- `python -m pip_audit --skip-editable`: no known vulnerabilities; editable project skipped as
  expected.
- `git diff --check`: passed.

## Решение аудита

RM-121 реализуется одним pure `app/core/ai/financial_risk.py` поверх уже нормализованных current
verified specialized findings. Он расширяет существующий `AiDocumentAnalysis`, analyzer/service
post-processing, versioned JSON payload, AI tab и exporter. Он не читает смету или company
profile, не выполняет числовой финансовый расчёт, не использует legacy engine, не меняет RM-107,
не выполняет I/O и не создаёт новый AI/persistence/UI workflow.
