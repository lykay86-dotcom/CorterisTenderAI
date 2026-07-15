# RM-120 — контракт объяснимой оценки юридических рисков

Дата фиксации контракта: 15 июля 2026 года.

## Назначение

RM-120 добавляет в существующий `AiDocumentAnalysis` локальный воспроизводимый реестр
условий, требующих ручной юридической проверки. Реестр является информационной оценкой и не
является юридическим заключением, оценкой законности, соответствия участника, вероятности
спора/отклонения либо рекомендацией об участии.

Provider продолжает только нейтрально извлекать факты. Legal category, review priority, title,
recommended action, status и stable ID вычисляются локально после current provenance.

## Стабильные доменные типы

```text
AiLegalRiskStatus:
  no_verified_risks
  complete
  partial
  unavailable

AiLegalReviewPriority:
  routine
  elevated
  urgent
```

Стабильные `AiLegalRiskCategory`:

```text
application_composition_and_declarations
submission_format_and_signature
grounds_for_rejection
eligibility_and_authorizations
national_regime_and_origin
security_and_guarantees
scope_and_customer_dependencies
price_payment_and_change_mechanism
acceptance_and_closing
liability_penalties_and_damages
change_suspension_and_termination
warranty_and_remedies
subcontracting_and_third_parties
force_majeure_and_notices
disputes_confidentiality_and_ip
standards_and_regulations
ambiguities_and_clarifications
contradictions
```

Категории `grounds_for_rejection`, `contradictions`, `submission_format_and_signature` и
`ambiguities_and_clarifications` разделены намеренно. Это позволяет сохранить единственную
таблицу `category → review priority` без скрытых field/text overrides: `URGENT` применяется
только к rejection/independently verified contradictions, submission остаётся `ELEVATED`, а
ambiguities/clarifications — `ROUTINE`.

```python
@dataclass(frozen=True, slots=True)
class AiLegalRiskSourceRef:
    section: str
    field: str
    citation_id: str

@dataclass(frozen=True, slots=True)
class AiLegalRiskItem:
    risk_id: str
    category: AiLegalRiskCategory
    review_priority: AiLegalReviewPriority
    title: str
    source_refs: tuple[AiLegalRiskSourceRef, ...]
    recommended_action: str

@dataclass(frozen=True, slots=True)
class AiLegalRiskAssessment:
    status: AiLegalRiskStatus
    policy_version: str
    items: tuple[AiLegalRiskItem, ...]
    warnings: tuple[str, ...]
```

Все dataclass immutable/slots. `section` допускает только `requirements`,
`technical_specification`, `draft_contract`; `field` — только разрешённое поле секции;
`citation_id` — canonical `cit_[0-9a-f]{32}` current verified finding. URL, file path и provider
metadata не являются source ref.

## Каноническая source policy

| Section | Fields | Category |
|---|---|---|
| requirements | application_composition, declarations_and_consents, deadlines | application_composition_and_declarations |
| requirements | submission_format_and_signature | submission_format_and_signature |
| requirements | grounds_for_rejection | grounds_for_rejection |
| requirements | participant_eligibility, licenses, certificates | eligibility_and_authorizations |
| requirements | national_regime_and_origin | national_regime_and_origin |
| requirements | bid_security, contract_security, bank_guarantee | security_and_guarantees |
| requirements | ambiguities, clarification_points | ambiguities_and_clarifications |
| requirements | contradictions | contradictions |
| draft_contract | subject_and_scope, term_schedule_and_location, customer_obligations_and_dependencies | scope_and_customer_dependencies |
| draft_contract | price_and_price_change, payment_terms | price_payment_and_change_mechanism |
| draft_contract | acceptance_and_closing_documents | acceptance_and_closing |
| draft_contract | performance_security | security_and_guarantees |
| draft_contract | warranty_and_defect_remediation | warranty_and_remedies |
| draft_contract | contractor_obligations_and_subcontracting | subcontracting_and_third_parties |
| draft_contract | liability_penalties_and_damages | liability_penalties_and_damages |
| draft_contract | change_suspension_and_termination | change_suspension_and_termination |
| draft_contract | force_majeure_and_notifications | force_majeure_and_notices |
| draft_contract | dispute_confidentiality_and_ip | disputes_confidentiality_and_ip |
| draft_contract | ambiguities, clarification_points | ambiguities_and_clarifications |
| draft_contract | contradictions | contradictions |
| technical_specification | standards_and_regulations | standards_and_regulations |
| technical_specification | acceptance_and_quality | acceptance_and_closing |
| technical_specification | customer_inputs_and_dependencies | scope_and_customer_dependencies |
| technical_specification | ambiguities, clarification_points | ambiguities_and_clarifications |
| technical_specification | contradictions | contradictions |

Иные поля, generic root findings и legacy `AnalysisEngine` legal rules не входят в policy.

## Priority и локальные presentation templates

`URGENT`:

- `grounds_for_rejection`;
- `contradictions`.

`ELEVATED`:

- `submission_format_and_signature`;
- `eligibility_and_authorizations`;
- `national_regime_and_origin`;
- `security_and_guarantees`;
- `price_payment_and_change_mechanism`;
- `liability_penalties_and_damages`;
- `change_suspension_and_termination`;
- `subcontracting_and_third_parties`;
- `disputes_confidentiality_and_ip`.

Остальные категории имеют `ROUTINE`. Значение `CRITICAL` не существует. Для каждой категории
policy содержит один фиксированный русский title и один фиксированный recommended action.
Provider statement показывается только как исходный statement/citation, но никогда не становится
title/action и не влияет на priority.

## Stable ID и deduplication

```text
AI_LEGAL_RISK_POLICY_VERSION = "1"
risk_id = "legal_" + sha256(canonical(policy_version, category,
                                       sorted(canonical citation IDs)))[:32]
```

Policy создаёт отдельный item для пары `(category, canonical citation ID)`. Несколько source refs
с тем же citation/category объединяются и сортируются; exact duplicates удаляются. Иной citation
остаётся отдельным item. Итоговые items сортируются по priority (`urgent`, `elevated`, `routine`),
category, citation IDs и `risk_id`, поэтому input order не влияет на payload.

## Evidence и status

Assessor принимает только `analysis.is_current_verified(finding)` и дополнительно сверяет section
с `document_kind` source snapshot. Повреждённые checksum/fingerprint/citation/source registry,
foreign kind, locator conflict и unverified finding не создают item.

`UNAVAILABLE`:

- no documents, provider disabled/error, invalid response, incompatible cache;
- нет current provenance или безопасная оценка невозможна.

`PARTIAL`:

- requirements/draft contract не `complete`;
- найденный relevant TS не `complete`;
- context truncated, scoped warning или часть eligible findings не current verified;
- source ref/persisted legal section повреждены;
- подтверждённые items разрешено сохранить, но warnings обязательны.

`NO_VERIFIED_RISKS` допустим только при complete requirements/draft context, complete relevant TS,
current provenance, отсутствии eligible findings/items и warnings. Пользовательский текст:
«Подтверждённые условия, требующие отдельной юридической проверки, не выявлены».

`COMPLETE` допустим только при полном контексте, current verified evidence для всех eligible
findings, наличии хотя бы одного item и отсутствии warnings.

## Analyzer, cache и версии

```text
provider output schema: 4 (без изменения)
response format: corteris_tender_analysis_v4 (без изменения)
prompt: 6 (без изменения)
context: 5 (без изменения)
citation resolver: 1 (без изменения)
persisted payload: 7
analyzer: 8
legal risk policy: 1
```

Порядок: один provider response → strict decode → normalize findings → build provenance → attach
provenance → local legal assessor → единый `AiDocumentAnalysis`. После применения context
completeness task service локально пересчитывает assessment без provider call.

Current payload v7 содержит exact root key `legal_risk_assessment`; exact nested keys:

```text
assessment: status, policy_version, items, warnings
item: risk_id, category, review_priority, title, source_refs, recommended_action
source ref: section, field, citation_id
```

При чтении v7 canonical assessment пересчитывается из уже проверенных current findings. Stored
section/field/citation, priority/title/action/risk ID сверяются с текущей policy. Exact mismatch,
duplicate/unknown value либо повреждение дают fail-closed `partial/unavailable`; tampered value не
возвращается. Legacy v1–v6 не повышает findings до verified и получает unavailable legal section.
Future/corrupt payload остаётся fail-closed. SQLite schema и migration не меняются.

## UI/export и безопасность

Расширяется только существующая вкладка `AI-анализ` и существующий exporter. Секция
«Юридические риски» показывает русский status, disclaimer «Информационная оценка; не является
юридическим заключением», policy version, counts, category/title/priority, исходные statements,
canonical citations, action и warnings. JSON равен `to_payload()`, HTML экранирует external text,
source list остаётся единым и дедуплицированным. Raw response/prompt/full document/credentials/
traceback/exception/private path не выводятся.

## Граница RM-107

Legal assessment не входит в `_current_verified_ai_findings()`, не меняет score, thresholds,
recommendation, actions/decision evidence и не создаёт stop factor. Generic current verified
RM-109 findings сохраняют прежнее поведение. Deterministic critical stop factor остаётся
абсолютным при score 100. Production-файлы RM-107 по умолчанию не изменяются.

## Приёмка

Обязательны новый pure-policy contour, schema/analyzer/repository/provenance/provider/runtime,
UI/export/security и RM-107 regression tests; target/full pytest; Ruff check/format; mypy; secret
scan; dependency audit; `git diff --check`; static proof одного provider call/Orchestrator/
repository/stage и отсутствия DB migration. Затем feature PR, post-merge Windows Quality Gate
3.12/3.13 и отдельный docs-only closeout.

## Local implementation acceptance

Implementation checkpoint: `a0dacc7798083fb914be7146a4d38774552c1c49`
Baseline: `7f21be719277314dc244a1e22d158be9d5c207ea`
Python: `3.12.7`

- Exact RM-120 target contour: `342 passed in 11.92s`.
- Full suite: `1198 passed in 51.00s`.
- `python -m ruff check .`: passed.
- `python -m ruff format . --check`: passed (`513 files already formatted`).
- `python -m mypy`: passed (`17 source files`).
- `python scripts/check_repository_secrets.py`: passed.
- `python -m pip_audit --skip-editable`: no known vulnerabilities; the editable project was
  skipped as expected. The sandbox-blocked first network attempt was repeated with explicitly
  allowed network access and a worktree-local cache.
- `git diff --check`: passed.

The adversarial review found exactly one production `provider.analyze(...)`, one
`TenderAiOrchestrator`, one `AiDocumentAnalysisRepository` class and one `RUNNING_AI` stage. The
only new policy component is the pure local `app/core/ai/legal_risk.py`; it performs no I/O,
provider calls, regex-based legal classification or network verification. No provider schema,
response format, prompt, context builder, citation resolver, repository, database table or
migration was added or changed beyond the required persisted payload/analyzer version bumps.

The legal registry is derived only from current verified specialized requirements, technical
specification and draft-contract findings. Category and review priority come from fixed mappings;
stable IDs and ordering use canonical citation IDs. Generic root risks and deterministic
stop-factors are not copied. Missing, unverified, foreign-kind, stale or damaged evidence fails
closed, while current v7 cache content is locally recomputed and compared before use. Legacy
v1-v6 remains unavailable and future/corrupt data stays incompatible.

The existing AI tab and JSON/HTML exporter display the four statuses, policy version, priority
counts, escaped titles/actions, current internal citations, warnings and the informational legal
disclaimer. Provider output remains legal-risk neutral. RM-107 production files are unchanged;
the registry does not alter score, recommendation, action/evidence lists or the absolute priority
of a deterministic critical stop-factor.

This is feature-branch acceptance only. RM-120 remains `IN PROGRESS` until feature merge,
post-merge Windows Quality Gate on Python 3.12 and 3.13, and a separate docs-only closeout PR.
