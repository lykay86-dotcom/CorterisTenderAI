# RM-122 — контракт explainable competition assessment

Baseline: `554b582eb22d276c00797eaf3b6700c515ab58eb`.

Architecture audit: `docs/RM-122_AUDIT.md`.

## Назначение

RM-122 добавляет в существующий `AiDocumentAnalysis` локальный воспроизводимый реестр
документально подтверждённых условий участия, требующих ручной конкурентной проверки. Реестр не
оценивает число конкурентов, вероятность победы, снижение цены, законность условий или рыночную
долю, не читает `raw_metadata`, не меняет RM-107 и не вызывает provider повторно.

Legacy `app/tender_analysis/engine.py`, `COMP_RULES`, `competition_risk`, provider-specific
результаты торгов и внешние сведения о компаниях не импортируются и не копируются.

## Domain contract

В `app/core/ai/schemas.py` добавляются frozen/slots types:

```text
AiCompetitionStatus:
  no_verified_conditions, complete, partial, unavailable

AiCompetitionReviewPriority:
  routine, elevated, urgent

AiCompetitionCategory:
  application_and_submission_conditions
  participant_eligibility
  experience_and_track_record
  licenses_certificates_and_authorizations
  personnel_and_equipment
  technical_specificity_and_equivalence
  standards_and_compatibility
  national_regime_and_origin
  security_and_financial_access
  geography_site_and_execution_constraints
  subcontracting_and_third_parties
  grounds_for_rejection
  ambiguities_and_clarifications
  contradictions
```

`AiCompetitionSourceRef` содержит только `section`, `field`, `citation_id`.
`AiCompetitionItem` содержит только `condition_id`, `category`, `review_priority`, `title`,
`source_refs`, `recommended_action`. `AiCompetitionAssessment` содержит только `status`,
`policy_version`, `items`, `warnings`.

Разрешённые sections: `requirements`, `technical_specification`, `draft_contract`. Field должен
входить в закрытую source policy. Citation ID: `cit_[0-9a-f]{32}`. Condition ID:
`competition_[0-9a-f]{32}`. Title ограничен 500 символами, action/warning — 1000 символами.
Source refs обязаны быть non-empty, unique и canonical.

Не добавляются score, level, competitor count, predicted discount, win probability, market share,
legality, provider priority/recommendation или provider verification flag.

## Source policy

### Requirements

```text
application_composition           -> application_and_submission_conditions
declarations_and_consents         -> application_and_submission_conditions
documents                         -> application_and_submission_conditions
submission_format_and_signature   -> application_and_submission_conditions
deadlines                         -> application_and_submission_conditions
participant_eligibility           -> participant_eligibility
experience                        -> experience_and_track_record
licenses                          -> licenses_certificates_and_authorizations
certificates                      -> licenses_certificates_and_authorizations
specialists                       -> personnel_and_equipment
equipment                         -> personnel_and_equipment
bid_security                      -> security_and_financial_access
contract_security                 -> security_and_financial_access
bank_guarantee                    -> security_and_financial_access
national_regime_and_origin        -> national_regime_and_origin
grounds_for_rejection             -> grounds_for_rejection
ambiguities                       -> ambiguities_and_clarifications
clarification_points              -> ambiguities_and_clarifications
contradictions                    -> contradictions
```

### Technical specification

```text
technical_characteristics        -> technical_specificity_and_equivalence
materials_and_equipment          -> technical_specificity_and_equivalence
standards_and_regulations        -> standards_and_compatibility
acceptance_and_quality           -> standards_and_compatibility
execution_conditions             -> geography_site_and_execution_constraints
stages_and_deadlines             -> geography_site_and_execution_constraints
customer_inputs_and_dependencies -> geography_site_and_execution_constraints
ambiguities                      -> ambiguities_and_clarifications
clarification_points             -> ambiguities_and_clarifications
contradictions                   -> contradictions
```

### Draft contract

```text
term_schedule_and_location                -> geography_site_and_execution_constraints
performance_security                      -> security_and_financial_access
contractor_obligations_and_subcontracting -> subcontracting_and_third_parties
ambiguities                               -> ambiguities_and_clarifications
clarification_points                      -> ambiguities_and_clarifications
contradictions                            -> contradictions
```

Generic root findings, legacy `RequirementFinding`, participation score/stop factors, commercial
estimate, company profile, `raw_metadata`, external company data и неподтверждённые tender results
исключены. Provider statement не участвует в выборе category, priority, title или action.

## Priority и presentation policy

`URGENT`: `grounds_for_rejection`, `contradictions`.

`ELEVATED`: `participant_eligibility`, `experience_and_track_record`,
`licenses_certificates_and_authorizations`, `personnel_and_equipment`,
`technical_specificity_and_equivalence`, `national_regime_and_origin`,
`security_and_financial_access`, `geography_site_and_execution_constraints`.

`ROUTINE`: `application_and_submission_conditions`, `standards_and_compatibility`,
`subcontracting_and_third_parties`, `ambiguities_and_clarifications`.

Priority означает только очередь ручной проверки. `CRITICAL` отсутствует.

| Category | Title | Recommended action |
| --- | --- | --- |
| application_and_submission_conditions | Состав и процедура подачи заявки | Оценить административную нагрузку и однозначность выполнения требований к подаче; не трактовать их как ограничение конкуренции автоматически. |
| participant_eligibility | Требования к допуску участника | Проверить обязательность и соразмерность требований к участнику и их возможное влияние на круг допустимых участников. |
| experience_and_track_record | Опыт и подтверждённая квалификация | Проверить соразмерность требуемого опыта предмету закупки и допустимые способы его подтверждения. |
| licenses_certificates_and_authorizations | Лицензии, сертификаты и авторизации | Проверить обязательность документов, допустимые аналоги и доступность подтверждения без автоматического вывода об ограничении. |
| personnel_and_equipment | Персонал и оборудование участника | Проверить требования к собственным ресурсам, возможность аренды, привлечения партнёров или эквивалентного подтверждения. |
| technical_specificity_and_equivalence | Техническая специфика и эквивалентность | Проверить функциональность характеристик, допустимость эквивалентов и нейтральность технического описания; не делать автоматический вывод о заточке. |
| standards_and_compatibility | Стандарты, качество и совместимость | Проверить применимость стандартов, методы подтверждения качества и доступность совместимых решений. |
| national_regime_and_origin | Национальный режим и происхождение | Проверить применимые ограничения, допустимые товары и документы о происхождении. |
| security_and_financial_access | Обеспечение и финансовый порог участия | Проверить форму и условия обеспечения и их влияние на доступность участия без расчёта уровня конкуренции. |
| geography_site_and_execution_constraints | География, объект и сроки исполнения | Проверить обязательность присутствия или осмотра, территориальные условия и реалистичность сроков для потенциальных участников. |
| subcontracting_and_third_parties | Субподряд, партнёры и третьи лица | Проверить ограничения на субподряд и партнёрскую модель исполнения и их влияние на допустимый круг участников. |
| grounds_for_rejection | Основания отклонения заявки | Срочно проверить однозначность основания отклонения и возможность полного выполнения требования до подачи заявки. |
| ambiguities_and_clarifications | Неоднозначности условий участия | Сформулировать запрос на разъяснение; не делать вывод о состоянии конкуренции до получения официального ответа. |
| contradictions | Противоречия условий участия | Срочно сопоставить независимые источники и запросить официальное разъяснение. |

## Pure policy, stable ID и ordering

Один новый модуль `app/core/ai/competition_review.py` предоставляет:

```text
AI_COMPETITION_POLICY_VERSION = "1"
assess_competition_conditions(analysis) -> AiCompetitionAssessment
condition_id = "competition_" +
  sha256(canonical(policy_version, category, sorted(canonical citation IDs)))[:32]
```

Модуль не выполняет I/O/network/provider/repository/database calls, не использует regex или
keyword matching statements, не читает `raw_metadata`, не импортирует legacy engine/COMP_RULES,
не рассчитывает деньги/float и не обращается к `CompanyCapabilityProfile`.

Отдельный item создаётся для `(category, citation ID)`. Одинаковые category/citation source refs
объединяются и сортируются; exact duplicates удаляются; другой citation остаётся отдельным item.
Items сортируются по priority (`urgent`, `elevated`, `routine`), category, citations и condition ID.

## Evidence и statuses

Item допускается только для `analysis.is_current_verified(finding)` с evidence, canonical citation
и ровно одним source snapshot ожидаемого `DocumentKind`. Requirements принимает application
source kinds, TS — только TS, contract — только draft contract. Missing/unverified/stale/altered,
foreign-kind, duplicated-source, locator/checksum conflict и invalid citation fail-closed с
bounded safe warning.

`UNAVAILABLE`: global AI failure, нет current provenance или безопасная оценка невозможна.

`PARTIAL`: отсутствующие/неполные requirements или TS, неполный присутствующий contract,
truncation/scoped warning, eligible finding не прошёл verification, source-kind mismatch или
повреждённая persisted competition section.

`COMPLETE`: обязательные контексты полны, каждый eligible finding verified, есть item, warnings
отсутствуют.

`NO_VERIFIED_CONDITIONS`: обязательные контексты полны, eligible items и warnings отсутствуют.
Пользовательский текст: «Документально подтверждённые условия, включённые в текущую политику
конкурентной проверки, не выявлены.» Это не утверждение об отсутствии ограничения или нарушения.

Отсутствующее ТЗ всегда даёт `partial`. Draft contract влияет только когда присутствует.

## Analyzer, cache и версии

```text
provider output schema: 4 (без изменения)
response format: corteris_tender_analysis_v4 (без изменения)
prompt: 6 (без изменения)
context: 5 (без изменения)
citation resolver: 1 (без изменения)
legal risk policy: 1 (без изменения)
financial risk policy: 1 (без изменения)
persisted payload: 8 -> 9
analyzer: 9 -> 10
competition policy: 1
```

Порядок: один provider response -> strict decode -> normalize -> provenance -> legal assessor ->
financial assessor -> competition assessor -> единый `AiDocumentAnalysis`. Service после
completeness локально пересчитывает все три derived assessments без provider call.

Current v9 root содержит exact key `competition_assessment` с exact nested keys доменного
контракта. При чтении section пересчитывается из restored current findings и exact-сравнивается.
Mismatch возвращает только canonical recalculation с safe status/warning. Legacy v1–v8 получает
unavailable competition section; future/corrupt data fail-closed. SQLite schema/migration не
меняются.

## UI/export и границы RM-107

Расширяются только существующая вкладка `AI-анализ` и существующий JSON/HTML exporter. Секция
«Анализ конкуренции» показывает status, disclaimer, policy version, priority counts, local
title/action, current verified statements, canonical internal citations и warnings. Внешний текст
экранируется и bounded.

Disclaimer: «Информационная оценка документально подтверждённых условий участия. Не является
оценкой числа конкурентов, вероятности победы, законности условий закупки или рекомендацией об
участии.»

`competition_assessment` не входит в `_current_verified_ai_findings()`, score, recommendation,
actions, decision evidence, stop factors, confidence или commercial completeness. RM-107
production files не меняются. Critical deterministic stop factor остаётся абсолютным при score
100.

## Acceptance

Обязательны pure-policy/schema/analyzer/service/repository/provenance/provider/UI/export/security,
RM-107 regression и architecture tests из ТЗ. Target contour содержит новый test file и текущие
schema/analyzer/service/repository/provenance/provider/legal/financial/decision/export/dialog tests.

Baseline: target `368 passed in 12.85s`; full `1289 passed in 56.34s`; Ruff check/format, mypy,
secret scan, dependency audit и diff check passed. Финальные точные counts и времена будут
записаны после feature implementation acceptance.
