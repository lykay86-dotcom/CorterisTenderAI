# RM-122 — аудит существующего анализа конкуренции

Дата аудита: 15 июля 2026 года.

Baseline: `554b582eb22d276c00797eaf3b6700c515ab58eb` (`origin/main`).

## Entry gate

- `docs/ROADMAP.md` и `docs/STATUS.md` фиксируют RM-121 как `DONE`, а RM-122 как
  единственный `IN PROGRESS`.
- Feature PR RM-121 #45 слит merge-коммитом
  `ac1cec2e11ce4cb08ec7aab3b4ab74ad255da746`.
- Post-merge Windows Quality Gate RM-121 run `29416563733` завершён успешно на Python 3.12 и
  Python 3.13.
- Docs-only closeout PR RM-121 #46 слит merge-коммитом
  `554b582eb22d276c00797eaf3b6700c515ab58eb`.
- Финальный main Quality Gate после closeout, run `29417488058`, также завершён успешно на
  Python 3.12 и Python 3.13.
- Ветка реализации создана как `feat/rm-122-competition-analysis` от указанного baseline.

Entry gate пройден. До этого аудита application-код RM-122 не изменялся.

## Проверенные файлы и контуры

- `app/core/ai/schemas.py`;
- `app/core/ai/output_schema.py`;
- `app/core/ai/prompts.py`;
- `app/core/ai/document_context.py`;
- `app/core/ai/citations.py`;
- `app/core/ai/analyzer.py`;
- `app/core/ai/orchestrator.py`;
- `app/core/ai/repository.py`;
- `app/core/ai/legal_risk.py`;
- `app/core/ai/financial_risk.py`;
- `app/reporting/tender_ai_analysis.py`;
- `app/ui/tender_full_analysis_dialog.py`;
- `app/tenders/models.py`;
- `app/tenders/full_analysis.py`;
- `app/tenders/participation_decision_policy.py`;
- `app/tenders/participation_decision_service.py`;
- `app/tenders/requirement_analysis.py`;
- `app/tenders/collector/models.py`;
- `app/tenders/collector/codec.py`;
- `app/tenders/collector/store.py`;
- `app/tenders/collector/participation_score.py`;
- provider adapters в `app/tenders/providers/`;
- `app/ai/structured_analysis.py`;
- `app/tender_analysis/engine.py`;
- модели, миграции и тесты, найденные статическим поиском по competition/competitor,
  участникам, победителям, протоколам, ставкам и снижению цены.

## Текущий AI-граф

Статический поиск подтвердил:

- единственный production-вызов `provider.analyze(...)` находится в
  `app/core/ai/analyzer.py`;
- определён один `TenderAiOrchestrator` в `app/core/ai/orchestrator.py`;
- определён один `AiDocumentAnalysisRepository` в `app/core/ai/repository.py`;
- в полном анализе существует одна стадия `RUNNING_AI` и одно её production-использование;
- bootstrap создаёт один analyzer/service/repository/orchestrator graph;
- persisted AI history хранится в одной таблице `tender_ai_document_analyses` как versioned
  JSON;
- юридическая и финансовая оценки уже вычисляются локально после provenance и повторно после
  определения completeness; тот же extension point подходит RM-122.

RM-122 не требует второго provider call, analyzer, service, orchestrator, repository, workflow,
stage, classifier или cache.

## Что в проекте уже называется анализом конкуренции

Единственный исполняемый специализированный контур найден в
`app/tender_analysis/engine.py`. Это legacy engine:

- `COMP_RULES` содержит regex/keyword-правила для бренда без эквивалента, письма авторизации,
  статуса партнёра/дилера, обязательного осмотра и офиса/склада в регионе;
- веса совпавших правил суммируются в integer `competition_risk` от 0 до 100;
- показатель даёт 15% старого score и может менять старую recommendation;
- engine читает legacy repository и company profile, использует `float` для коммерческих
  вычислений и сохраняет отдельный legacy report;
- старые модели и миграции содержат поля `competition_risk`, а `tests/test_analysis.py`
  проверяет `competition_risks` именно этого отчёта.

Этот контур не является current verified AI graph. RM-122 не импортирует и не копирует
`COMP_RULES`, веса, regex, score, recommendation, repository access или финансовые вычисления
legacy engine. Сам legacy production-код остаётся без изменений.

`app/ai/structured_analysis.py` содержит generic `competition_flags`, но относится к другому
legacy structured-analysis contract и не предоставляет provenance-verified assessment для
текущего `AiDocumentAnalysis`.

## Доступность данных о фактической конкуренции

Аудит canonical tender, collector и provider contracts не обнаружил нормализованных сущностей
или полей для:

- поданных заявок и количества участников;
- участников, конкурентов и допущенных заявителей;
- победителя, места участника или award result;
- первоначальных и итоговых ставок;
- процента снижения и истории торгов;
- протоколов рассмотрения, допуска, подведения итогов или заключения контракта.

`TenderProcedureType.OPEN_COMPETITION` — только нормализованный тип процедуры, а не сведения о
фактической конкурентности конкретной закупки.

Некоторые adapters сохраняют provider-specific `raw_metadata`; Mos Supplier может сохранять
непрозрачный API record целиком. Эти данные не имеют общего проверенного protocol/schema,
canonical evidence и source registry. Они не являются допустимым источником RM-122. EIS adapter
также не формирует нормализованную историю результатов.

Следовательно, по текущим данным нельзя достоверно вычислять число конкурентов, вероятность
победы, ожидаемое снижение цены, рыночную концентрацию, повторяемость победителей или поведение
конкретных поставщиков. RM-122 не должен имитировать такие метрики.

## Допустимый предмет новой оценки

Текущая strict provider schema v4 уже нейтрально извлекает документально подтверждённые условия
из существующих requirements, technical specification и draft-contract buckets. RM-122 может
без нового provider contract построить локальный реестр условий участия из следующих полей:

- requirements: состав заявки, декларации и согласия, документы, формат/подпись, сроки,
  требования к участнику, опыт, лицензии, сертификаты, специалисты, оборудование, обеспечение
  заявки и исполнения, банковская гарантия, национальный режим, основания отклонения,
  неоднозначности, вопросы на разъяснение и противоречия;
- technical specification: технические характеристики, материалы и оборудование, стандарты,
  приёмка и качество, условия/этапы/сроки исполнения, исходные данные заказчика,
  неоднозначности, вопросы на разъяснение и противоречия;
- draft contract: срок, график и место исполнения, обеспечение исполнения, обязанности
  подрядчика и субподряд, неоднозначности, вопросы на разъяснение и противоречия.

Эта оценка описывает только подтверждённые условия доступа и исполнения. Она не оценивает их
законность, не предсказывает действия конкурентов и не формирует решение об участии.

Generic root `risks`, `suspicious_conditions` и `contradictions`, legacy
`RequirementFinding`, `competition_flags`, commercial results, company profile и
`raw_metadata` не являются источниками нового registry. Category, priority, title и action
определяются только локальной фиксированной policy по положению finding в schema, а не по тексту
provider statement, keyword или regex.

## Evidence и provenance

`AiDocumentAnalysis.is_current_verified()` уже проверяет current provenance, checksum, context
fingerprint, canonical source ref и citation ID. Реализации RM-120 и RM-121 показывают безопасный
шаблон source-kind validation и локального пересчёта persisted derived section. RM-122 может
переиспользовать этот audited protocol со своей закрытой source policy.

Разрешённые source kinds:

- requirements — только текущие application source kinds;
- technical specification — только `TECHNICAL_SPECIFICATION`;
- draft contract — только `DRAFT_CONTRACT`.

Stale, altered, unverified, foreign-kind, duplicated-source и locator-conflicting evidence должны
обрабатываться fail-closed. `condition_id` и `source_refs` должны выводиться только из canonical
verified citations. Новая policy не читает raw document text и не выполняет statement matching.

## Persistence и версии

Фактические версии baseline:

```text
provider output schema: 4
response format: corteris_tender_analysis_v4
prompt: 6
context: 5
citation resolver: 1
persisted payload: 8
analyzer: 9
legal risk policy: 1
financial risk policy: 1
```

Для RM-122 требуется повысить только persisted payload `8 -> 9` и analyzer `9 -> 10`, добавить
competition policy version `1`. Provider schema/format, prompt, context, citation resolver,
legal policy и financial policy остаются без изменений.

Таблица `tender_ai_document_analyses` уже содержит `payload_json` и `payload_version`. Новая
колонка, таблица, migration или отдельный competition repository не требуются. Current payload
должен принимать только точное локально пересчитанное значение; legacy payload versions 1–8 не
имеют доверенной competition assessment, а future/corrupt payload должен оставаться fail-closed.

## Completeness и безопасные статусы

Новая оценка зависит от completeness существующих специализированных разделов, а не от наличия
ключевых слов:

- глобальный сбой, отсутствие current provenance или невозможность верификации дают
  `unavailable`;
- отсутствующие или неполные requirements и technical specification дают `partial`;
- draft contract влияет только когда присутствует: неполный присутствующий contract даёт
  `partial`;
- truncation, warnings, rejected eligible evidence или tampered persisted assessment дают
  `partial` либо fail-closed согласно current payload contract;
- полные обязательные контексты с items и без warnings дают `complete`;
- полные обязательные контексты без items и warnings дают `no_verified_conditions`.

Отсутствующее ТЗ для RM-122, в отличие от некоторых более узких specialized policies, является
неполнотой и должно давать `partial`.

## Граница RM-107

`_current_verified_ai_findings()` в `app/tenders/participation_decision_service.py` перечисляет
только generic root `risks`, `suspicious_conditions` и `contradictions`. Specialized legal и
financial assessments туда не входят; competition assessment также не должна входить.

`participation_decision_policy.py` и `collector/participation_score.py` сохраняют владельца
детерминированных score bands, recommendation и critical stop-factor priority. Новая оценка не
меняет score, thresholds, recommendation, actions, decision evidence, stop factors, commercial
completeness или company capability projection. Критический stop factor остаётся абсолютным даже
при score 100.

## UI и экспорт

Существующая вкладка `AI-анализ` и существующий JSON/HTML exporter уже отображают specialized
legal и financial sections и canonical internal citations. RM-122 должен добавить только секцию
«Анализ конкуренции» в эти поверхности. Новая вкладка, export format, source registry, citation
resolver или navigation workflow не нужны.

Внешние title/action/warning обязаны экранироваться. Raw provider response, prompt, полный
документ, credentials, traceback, private paths и `raw_metadata` не выводятся.

Обязательный disclaimer фиксирует границу результата: оценка является информационной оценкой
документально подтверждённых условий участия и не является оценкой числа конкурентов,
вероятности победы, законности условий закупки или рекомендацией об участии.

## Baseline acceptance

Окружение: Python `3.12.7`, `QT_QPA_PLATFORM=offscreen`, worktree-local `TEMP/TMP`.

- Существующий RM-122 target-контур без нового теста: `368 passed in 12.85s`.
- Полный suite: `1289 passed in 56.34s`.
- `python -m ruff check .`: passed.
- `python -m ruff format . --check`: passed (`515 files already formatted`).
- `python -m mypy`: passed (`18 source files`).
- `python scripts/check_repository_secrets.py`: passed.
- `python -m pip_audit --skip-editable`: no known vulnerabilities; editable project skipped as
  expected.
- `git diff --check`: passed.

## Решение аудита

RM-122 реализуется одним pure `app/core/ai/competition_review.py` поверх уже нормализованных
current verified specialized findings. Он расширяет существующий `AiDocumentAnalysis`,
analyzer/service post-processing, versioned JSON payload, вкладку AI и exporter.

Новый модуль не выполняет I/O, network, provider или repository calls; не читает DB,
`raw_metadata`, company profile, commercial estimate или legacy reports; не использует regex,
keywords, `COMP_RULES`, деньги или `float`; не меняет RM-107 и не создаёт новый
AI/persistence/UI workflow. Результат — объяснимый реестр документально подтверждённых условий
участия с canonical citations и фиксированным review priority, а не прогноз конкурентной среды.
