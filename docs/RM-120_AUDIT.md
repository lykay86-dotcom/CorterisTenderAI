# RM-120 — аудит объяснимой оценки юридических рисков

Дата аудита: 15 июля 2026 года.

## Входной gate и границы

- Фактический baseline: `7f21be719277314dc244a1e22d158be9d5c207ea`, merge-коммит
  docs-only PR #42 (`docs/rm-119-completion`).
- Feature PR RM-119 #41 слит коммитом `dedc361c1ed88b16e0aa00e7e9f07f9ac131422a`.
- Post-merge Windows Quality Gate RM-119 run `29406013475` завершён `SUCCESS` на Python
  3.12 и 3.13; канонические документы фиксируют RM-119 как `DONE`, RM-120 как
  `IN PROGRESS`.
- Ветка `feat/rm-120-legal-risk-analysis` создана непосредственно от указанного baseline.
- До этого аудита application-код RM-120 не изменялся.

Цель RM-120 — информационный локальный реестр условий, требующих ручной юридической
проверки. Он не является юридическим заключением, не проверяет действующее законодательство
через сеть, не оценивает соответствие участника и не меняет решение об участии.

## Единственный production-граф Tender Intelligence

Подтверждена существующая цепочка:

```text
TenderDocumentTextService
→ TenderDocumentContextBuilder
→ TenderDocumentAiAnalysisService
→ TenderDocumentAiAnalyzer
→ один AIProvider.analyze()
→ RM-116 citation resolver/provenance
→ AiDocumentAnalysisRepository
→ TenderAiOrchestrator
→ TenderFullAnalysisService
→ RM-107
→ существующие UI/export
```

Доказательства:

- единственный production-вызов `provider.analyze()` находится в
  `app/core/ai/analyzer.py`;
- production composition root в `app/tenders/search_runtime.py` создаёт по одному analyzer,
  task service, repository и Orchestrator;
- `TenderFullAnalysisService` запускает Orchestrator в единственной стадии `RUNNING_AI` и
  явно передаёт результат текущего запуска в RM-107;
- `TenderFullAnalysisDialog` и `TenderAiAnalysisExporter` уже являются едиными UI/export
  путями для `AiDocumentAnalysis`.

Новый provider, provider call, AI workflow/stage, analyzer, Orchestrator, repository,
классификатор документов или citation resolver не требуются.

## Существующие источники фактов

`AiDocumentAnalysis` уже содержит:

- `requirements: TenderRequirements` с 21 группой и application-specific status;
- `technical_specification: AiTechnicalSpecificationAnalysis` с 13 группами;
- `draft_contract: AiDraftContractAnalysis` с 16 группами;
- generic `risks`, `suspicious_conditions` и `contradictions`;
- current `AiAnalysisProvenance` и canonical `AiEvidence`.

Текущий analyzer строго проверяет один provider response, разрешает evidence единым RM-116
citation resolver, ограничивает finding локально классифицированными документами и применяет
правила независимости citations к contradictions. `AiDocumentAnalysis.is_current_verified()`
повторно проверяет payload/provenance versions, context fingerprint, checksum, source ref и
canonical citation ID.

Юридическая policy может использовать только current verified findings из разрешённых полей
requirements/technical specification/draft contract. Корневые generic findings не переносятся:
это исключает дублирование и двойное влияние на RM-107.

## Детерминированные и legacy-контуры

`app/tenders/requirement_analysis.py` уже содержит локальные regex-правила, категории,
severity/risk level и `TenderRequirementAnalysis`, включая contract risks и stop factors.
Отдельный `StopFactorEngine` остаётся каноническим источником critical stop-factor assessment.
RM-120 не копирует эти regex-правила, не создаёт `CRITICAL` legal priority и не создаёт новый
stop factor.

Обнаружен старый контур `app/tender_analysis/engine.py`: его `AnalysisEngine` вычисляет
числовой `legal_risk`, собственные score/recommendation и regex-based `LEGAL_RULES`, сохраняемые
через legacy repository/bridge. Это не текущий evidence-first Tender Intelligence contract.
Новый `AiLegalRiskAssessment` не импортирует, не копирует и не расширяет этот контур; legacy
БД-поля `legal_risk` также не используются.

## Граница RM-107

`ParticipationDecisionService._current_verified_ai_findings()` использует только generic
current verified `risks`, `suspicious_conditions` и `contradictions`. Специализированные
requirements/TS/contract findings в RM-107 не входят. Generic verified finding может добавить
ручную проверку, но не создаёт новый stop factor; unverified finding не влияет.

Production-файлы `participation_decision.py`, `participation_decision_policy.py` и
`participation_decision_service.py` для реализации RM-120 менять не требуется. Новый legal
registry не должен менять score, thresholds, recommendation, action plan или decision evidence.
Существующий deterministic critical stop factor проверяется раньше score/AI evidence и сохраняет
абсолютный приоритет.

## Persistence и версии

`AiDocumentAnalysisRepository` использует существующую таблицу
`tender_ai_document_analyses`. В `payload_json` сохраняется canonical `to_payload()`; raw provider
response, prompt и полный текст документов не сохраняются. Колонка `payload_version` уже
поддерживает versioned JSON и fail-closed чтение повреждённых/future записей.

Физическое изменение SQLite schema и миграция не требуются. Предусмотренные изменения версий:

```text
provider output schema: 4 (без изменения)
response format: corteris_tender_analysis_v4 (без изменения)
prompt: 6 (без изменения)
context: 5 (без изменения)
citation resolver: 1 (без изменения)
persisted payload: 6 → 7
analyzer: 7 → 8
legal risk policy: 1
```

Provider output не должен содержать legal-risk fields. Локальный assessment строится только
после присоединения current provenance и должен безопасно пересчитываться/деградировать при
чтении cache, не доверяя сохранённым title, action, priority или source refs без сверки с policy
и current verified findings.

## UI и экспорт

Существующая вкладка `AI-анализ` и существующий `TenderAiAnalysisExporter` могут быть расширены
одной секцией «Юридические риски». Новая вкладка и новый формат не требуются. JSON продолжает
использовать canonical `to_payload()`, HTML — escaped external values и существующие внутренние
citation links. Raw response, prompt, credentials, traceback, exception, полный документ и
private path не выводятся.

## Offline baseline

Окружение: Windows, workspace `.venv`, Python `3.12.7`, worktree-local `TEMP/TMP`,
`QT_QPA_PLATFORM=offscreen`.

- целевой RM-120 contour до добавления нового тестового файла: `247 passed in 12.30s`;
- полный pytest: `1114 passed in 56.16s`;
- Ruff check: `All checks passed`;
- Ruff format: `511 files already formatted`;
- mypy: `Success: no issues found in 16 source files`;
- repository secret scan: `passed`;
- dependency audit: `No known vulnerabilities found` (editable project корректно пропущен);
- `git diff --check`: успешно;
- offline credential isolation smoke: `2 passed in 4.02s`.

Тесты выполнялись с disabled/fake providers и явными network/keyring guards; production provider
call, DNS и host keyring не использовались. Первичная команда через системный Python остановилась
до pytest из-за отсутствующего модуля; повтор через канонический workspace `.venv` прошёл без
изменения зависимостей.

## Вывод аудита

Оптимальная реализация — один pure-модуль `app/core/ai/legal_risk.py` с versioned policy,
стабильным deduplication/risk ID и локальными title/action templates. Он классифицирует только
разрешённые current verified специализированные findings после provenance, возвращает
fail-closed status/warnings и включается в существующий `AiDocumentAnalysis` payload/UI/export.
Параллельный AI или persistence контур, изменение provider schema/context/prompt, миграция БД и
изменение RM-107 не нужны.
