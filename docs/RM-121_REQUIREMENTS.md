# RM-121 — контракт explainable financial-risk assessment

Baseline: `32510874291da502d6a588e32e633c01e736c274`.

Architecture audit: `docs/RM-121_AUDIT.md`.

## Назначение

RM-121 добавляет в существующий `AiDocumentAnalysis` локальный воспроизводимый реестр
документально подтверждённых финансовых условий, требующих ручной проверки. Реестр не является
финансовой моделью, не прогнозирует убыток, не вычисляет вероятность/сумму ущерба, не заполняет
смету, не читает company profile, не меняет RM-107 и не вызывает provider повторно.

Канонический числовой расчёт текущего Tender Intelligence остаётся в
`app/tenders/commercial_estimator.py`; подтверждённые лимиты компании остаются в
`CompanyCapabilityProfile`. Legacy float-контуры `app/estimates/calculator.py` и
`app/tender_analysis/engine.py` не импортируются новым кодом.

## Domain contract

В `app/core/ai/schemas.py` добавляются frozen/slots types:

```text
AiFinancialRiskStatus:
  no_verified_conditions, complete, partial, unavailable

AiFinancialReviewPriority:
  routine, elevated, urgent

AiFinancialRiskCategory:
  price_and_estimate
  payment_and_cash_flow
  security_and_guarantee_costs
  scope_and_volume_uncertainty
  materials_and_equipment_costs
  execution_schedule_and_resource_load
  acceptance_and_payment_dependency
  customer_inputs_and_dependencies
  warranty_and_defect_costs
  liability_penalties_and_damages
  change_suspension_and_termination
  subcontracting_and_third_party_costs
  national_regime_and_supply_restrictions
  ambiguities_and_clarifications
  contradictions
```

`AiFinancialRiskSourceRef` содержит только `section`, `field`, `citation_id`.
`AiFinancialRiskItem` содержит только `risk_id`, `category`, `review_priority`, `title`,
`source_refs`, `recommended_action`. `AiFinancialRiskAssessment` содержит только `status`,
`policy_version`, `items`, `warnings`.

Разрешённые sections: `requirements`, `technical_specification`, `draft_contract`. Field должен
входить в закрытую source policy. Citation ID: `cit_[0-9a-f]{32}`. Risk ID:
`financial_[0-9a-f]{32}`. Title ограничен 500 символами, action/warning — 1000 символами.
Source refs обязаны быть non-empty, unique и canonical.

## Source policy

### Requirements

```text
price_proposal_and_estimate -> price_and_estimate
bid_security                -> security_and_guarantee_costs
contract_security           -> security_and_guarantee_costs
bank_guarantee              -> security_and_guarantee_costs
warranty                    -> warranty_and_defect_costs
national_regime_and_origin  -> national_regime_and_supply_restrictions
ambiguities                 -> ambiguities_and_clarifications
clarification_points        -> ambiguities_and_clarifications
contradictions              -> contradictions
```

### Technical specification

```text
scope                            -> scope_and_volume_uncertainty
deliverables                     -> scope_and_volume_uncertainty
quantities_and_volumes           -> scope_and_volume_uncertainty
technical_characteristics        -> materials_and_equipment_costs
materials_and_equipment          -> materials_and_equipment_costs
execution_conditions             -> execution_schedule_and_resource_load
stages_and_deadlines             -> execution_schedule_and_resource_load
acceptance_and_quality           -> acceptance_and_payment_dependency
customer_inputs_and_dependencies -> customer_inputs_and_dependencies
ambiguities                      -> ambiguities_and_clarifications
clarification_points             -> ambiguities_and_clarifications
contradictions                   -> contradictions
```

### Draft contract

```text
subject_and_scope                         -> scope_and_volume_uncertainty
term_schedule_and_location                -> execution_schedule_and_resource_load
price_and_price_change                    -> price_and_estimate
payment_terms                             -> payment_and_cash_flow
acceptance_and_closing_documents          -> acceptance_and_payment_dependency
performance_security                     -> security_and_guarantee_costs
warranty_and_defect_remediation           -> warranty_and_defect_costs
customer_obligations_and_dependencies     -> customer_inputs_and_dependencies
contractor_obligations_and_subcontracting -> subcontracting_and_third_party_costs
liability_penalties_and_damages           -> liability_penalties_and_damages
change_suspension_and_termination         -> change_suspension_and_termination
ambiguities                               -> ambiguities_and_clarifications
clarification_points                      -> ambiguities_and_clarifications
contradictions                            -> contradictions
```

Generic root findings, application composition/eligibility/licenses, force majeure, disputes/IP,
legacy RequirementFinding, CommercialEstimator output и company profile исключены.

## Priority policy

`URGENT`: `contradictions`.

`ELEVATED`: `price_and_estimate`, `payment_and_cash_flow`,
`security_and_guarantee_costs`, `scope_and_volume_uncertainty`,
`acceptance_and_payment_dependency`, `warranty_and_defect_costs`,
`liability_penalties_and_damages`, `change_suspension_and_termination`.

`ROUTINE`: `materials_and_equipment_costs`, `execution_schedule_and_resource_load`,
`customer_inputs_and_dependencies`, `subcontracting_and_third_party_costs`,
`national_regime_and_supply_restrictions`, `ambiguities_and_clarifications`.

Priority означает только очередь ручной проверки. `CRITICAL` отсутствует. Provider statement не
может изменить category, priority, title или action.

Фиксированные русские presentations:

| Category | Title | Recommended action |
| --- | --- | --- |
| price_and_estimate | Цена и состав сметы | Сверить подтверждённые ценовые условия с коммерческим расчётом; значения не переносить автоматически. |
| payment_and_cash_flow | Оплата и денежный поток | Сверить подтверждённые условия аванса и оплаты с коммерческим расчётом; значения не переносить автоматически. |
| security_and_guarantee_costs | Обеспечение и стоимость гарантий | Подтвердить размер и стоимость обеспечения в коммерческом расчёте и проверить доступный лимит компании. |
| scope_and_volume_uncertainty | Неопределённость объёма и состава работ | Уточнить объём и включить подтверждённые дополнительные затраты в смету. |
| materials_and_equipment_costs | Материалы и оборудование | Проверить состав, количество и подтверждённые цены материалов и оборудования вручную. |
| execution_schedule_and_resource_load | Сроки и ресурсная нагрузка | Сверить график выполнения с ресурсами и вручную учесть подтверждённые затраты по срокам. |
| acceptance_and_payment_dependency | Приёмка и зависимость оплаты | Проверить условия приёмки, закрывающие документы и их влияние на срок оплаты. |
| customer_inputs_and_dependencies | Данные и действия заказчика | Уточнить зависимости от заказчика и вручную оценить связанные дополнительные затраты. |
| warranty_and_defect_costs | Гарантийные обязательства и устранение дефектов | Подтвердить гарантийный объём и вручную учесть связанные затраты в смете. |
| liability_penalties_and_damages | Ответственность, штрафы и убытки | Провести ручную оценку потенциальной финансовой нагрузки без автоматического расчёта возможного ущерба. |
| change_suspension_and_termination | Изменение и прекращение договора | Проверить финансовые последствия изменения, приостановки и прекращения договора вручную. |
| subcontracting_and_third_party_costs | Субподряд и расходы третьих лиц | Подтвердить объём субподряда и вручную учесть документально подтверждённые расходы. |
| national_regime_and_supply_restrictions | Национальный режим и ограничения поставки | Проверить влияние ограничений поставки на доступность и стоимость без автоматической подстановки цен. |
| ambiguities_and_clarifications | Неоднозначности финансовых условий | Сформулировать вопрос и запросить разъяснение до фиксации финансовых допущений. |
| contradictions | Противоречия финансово значимых условий | Срочно сопоставить независимые источники и запросить официальное разъяснение до расчёта. |

## Stable ID и ordering

```text
AI_FINANCIAL_RISK_POLICY_VERSION = "1"
risk_id = "financial_" + sha256(canonical(policy_version, category,
                                            sorted(canonical citation IDs)))[:32]
```

Отдельный item создаётся для `(category, citation ID)`. Одинаковые category/citation source refs
объединяются и сортируются; exact duplicates удаляются; другой citation остаётся отдельным item.
Items сортируются по priority (`urgent`, `elevated`, `routine`), category, citations и risk ID.

## Evidence и statuses

Item допускается только для `analysis.is_current_verified(finding)` с evidence и ровно одним
source snapshot ожидаемого `DocumentKind`. Requirements принимает application source kinds, TS —
только TS, contract — только draft contract. Altered/stale/foreign/duplicated evidence fail-closed.

`UNAVAILABLE`: failure status, нет current provenance или безопасная оценка невозможна.

`PARTIAL`: incomplete relevant context, truncation/scoped warning, eligible unverified finding,
source-kind failure или повреждённая persisted financial section. Current items сохраняются с
warnings.

`COMPLETE`: все релевантные контексты полны, каждый eligible finding current verified, есть item,
warnings отсутствуют.

`NO_VERIFIED_CONDITIONS`: контексты полны, eligible findings/items и warnings отсутствуют.
Пользовательский текст: «Подтверждённые финансовые условия, требующие отдельной проверки, не
выявлены». Это не утверждение об отсутствии реального финансового риска.

## Analyzer, cache и версии

```text
provider output schema: 4 (без изменения)
response format: corteris_tender_analysis_v4 (без изменения)
prompt: 6 (без изменения)
context: 5 (без изменения)
citation resolver: 1 (без изменения)
legal risk policy: 1 (без изменения)
persisted payload: 8
analyzer: 9
financial risk policy: 1
```

Порядок: один provider response -> strict decode -> normalize -> provenance -> legal assessor ->
financial assessor -> единый `AiDocumentAnalysis`. Service после completeness локально
пересчитывает обе derived assessments без provider call.

Current v8 root содержит exact key `financial_risk_assessment` с exact nested keys доменного
контракта. При чтении financial section пересчитывается из восстановленных current findings и
сравнивается exact. Mismatch возвращает только canonical recalculation с `partial/unavailable` и
warning. Legacy v1-v7 получает unavailable financial section; future/corrupt data fail-closed.
SQLite schema и migration не меняются.

## UI/export и границы

Расширяются только существующая вкладка `AI-анализ` и существующий JSON/HTML exporter. Секция
показывает status, disclaimer, policy version, priority counts, title/action, source statements,
canonical citations и warnings. Весь внешний текст экранируется.

Disclaimer: «Информационная оценка условий документации; не является финансовым прогнозом,
расчётом убытка или рекомендацией об участии».

`financial_risk_assessment` не входит в `_current_verified_ai_findings()`, score, recommendation,
actions, decision evidence или stop factors. Он не отменяет `DATA_INSUFFICIENT` неполной сметы.
CommercialEstimator и CompanyCapabilityProfile не изменяются; новые денежные значения не
создаются. Critical deterministic stop factor остаётся абсолютным при score 100.

## Acceptance

Обязательны pure-policy/schema/analyzer/service/repository/provenance/provider/UI/export/security,
RM-107 и CommercialEstimator regressions; target/full pytest; Ruff check/format; mypy; secret scan;
dependency audit; `git diff --check`; static proof одного AI graph/stage, отсутствия DB migration,
legacy import, float money и I/O в financial policy. Feature merge не переводит RM-121 в `DONE`:
после post-merge Windows gate 3.12/3.13 нужен отдельный docs-only closeout.

## Local implementation acceptance

Implementation checkpoint: `999c2ec929cd6f0ccd024442a0708ba47ee75609`
Baseline: `32510874291da502d6a588e32e633c01e736c274`
Python: `3.12.7`

- Exact RM-121 target contour: `337 passed in 13.12s`.
- Full suite: `1289 passed in 55.25s`.
- `python -m ruff check .`: passed.
- `python -m ruff format . --check`: passed (`515 files already formatted`).
- `python -m mypy`: passed (`18 source files`).
- `python scripts/check_repository_secrets.py`: passed.
- `python -m pip_audit --skip-editable`: no known vulnerabilities; the editable project was
  skipped as expected. The sandbox-blocked first network attempt was repeated with explicitly
  allowed network access and a worktree-local cache.
- `git diff --check`: passed.

The adversarial review found exactly one production `provider.analyze(...)`, one
`TenderAiOrchestrator`, one `AiDocumentAnalysisRepository` class and one `RUNNING_AI` enum stage
with its existing execution path. The only new policy component is the pure local
`app/core/ai/financial_risk.py`; it performs no I/O, provider calls, regex/money parsing,
commercial calculation or legacy `AnalysisEngine` import. No provider output root, response
format, prompt, context builder, citation resolver, repository, database table or migration was
added or changed beyond the required persisted payload/analyzer version bumps.

The financial-condition registry is derived only from current verified specialized requirements,
technical specification and draft-contract findings. Category and review priority come from fixed
mappings; stable IDs and ordering use canonical citation IDs. Generic root findings and
deterministic stop-factors are not copied. Missing, unverified, foreign-kind, stale or damaged
evidence fails closed, while current v8 cache content is locally recomputed and compared before
use. Legacy v1-v7 remains unavailable and future/corrupt data stays incompatible.

The existing AI tab and JSON/HTML exporter display the four statuses, policy version, priority
counts, escaped titles/actions, current internal citations, warnings and the required informational
financial disclaimer. Provider output remains financial-conclusion neutral. RM-107 production
policy files are unchanged; the registry does not alter score, recommendation, actions, decision
evidence or the absolute priority of a deterministic critical stop-factor. `CommercialEstimator`
remains the canonical `Decimal` calculation boundary, and an empty draft remains
`DATA_INSUFFICIENT` without invented total cost, profit or margin.

This is feature-branch acceptance only. RM-121 remains `IN PROGRESS` until feature merge,
post-merge Windows Quality Gate on Python 3.12 and 3.13, and a separate docs-only closeout PR.
