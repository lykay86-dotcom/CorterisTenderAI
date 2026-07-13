# RM-111 — аудит существующих AI execution paths

Дата: 13 июля 2026 года. Исходный HEAD: `ebc36f4`. Статус RM-111:
`DONE` (PR #24, merge `f246381`).

## Цель аудита

Определить единственную application-service точку входа для AI-части полного
анализа тендера без создания второго analyzer, repository, Decision Engine,
exporter или параллельного full-analysis workflow.

## Выполненный поиск

Проверены production-код и тесты по символам:

- `AIProvider`, `DisabledProvider`, `OpenAICompatibleProvider`;
- `TenderDocumentAiAnalyzer`, `TenderDocumentAiAnalysisService`;
- `AiDocumentAnalysisRepository`;
- `TenderAIService`, `structured_analysis`;
- `ai_document_analysis`;
- `ParticipationDecisionService`.

Также отдельно проверены прямые вызовы `provider.analyze`, чтения
`repository.latest`, composition roots, UI и exporters.

## Канонический production workflow

Единственная действующая production-цепочка находится в следующих компонентах:

1. `app/tenders/search_runtime.py` создаёт composition root;
2. `TenderDocumentContextBuilder` формирует ограниченный локальный контекст;
3. `TenderDocumentAiAnalysisService` управляет reuse текущего fingerprint и
   безопасным persistence;
4. `TenderDocumentAiAnalyzer` является единственным каноническим местом прямого
   вызова `AIProvider.analyze`;
5. `AiDocumentAnalysisRepository` хранит версионированную append-only историю;
6. `TenderFullAnalysisService` вызывает task-service и явно передаёт результат
   текущего запуска в `ParticipationDecisionService.evaluate`;
7. `DeterministicTenderSummaryGenerator` формирует итоговое резюме из уже
   существующих детерминированных данных и решения RM-107;
8. `TenderFullAnalysisDialog` и `TenderAiAnalysisExporter` только отображают и
   экспортируют готовый `AiDocumentAnalysis`.

Production composition root один: `create_tender_search_runtime()` в
`app/tenders/search_runtime.py`. UI создаёт его через
`TenderSearchUiController`, но не создаёт provider, analyzer или repository.
По умолчанию root использует `DisabledProvider`; выбор provider, модели,
base URL и credentials не выполняется.

## Прямые вызовы AI provider

Найдены два места:

- `app/core/ai/analyzer.py` — канонический production-вызов, после которого
  выполняются нормализация, проверка точной цитаты и безопасные статусы;
- `app/ai/structured_analysis.py` — старый независимый путь с собственным
  prompt, JSON parsing, `score` и `recommendation`.

Второй путь не имеет production-потребителей. Единственная ссылка вне самого
модуля — `tests/test_v14.py`, который импортирует только `_extract_json` и
`validate_citations`. Класс `TenderAIService`, его модели результата и прямой
provider-вызов являются legacy-дублированием. В RM-111 они должны быть удалены,
а две совместимые helper-функции могут временно остаться без provider
orchestration, score, recommendation и repository.

## Repository и cache reads

- `TenderDocumentAiAnalysisService` использует
  `AiDocumentAnalysisRepository.reusable(registry_key, fingerprint)` и
  возвращает кеш только при совпадении текущего контекста и версий.
- `ParticipationDecisionService` умеет читать
  `ai_analysis_repository.latest(registry_key)`, если вызывающая сторона не
  передала AI-результат явно.
- Текущий `TenderFullAnalysisService` уже передаёт
  `ai_document_analysis=...` явно, поэтому старый успешный cache не заменяет
  ошибку текущего запуска.

После RM-111 полный анализ обязан сохранить явную передачу
`orchestration.document_analysis` в RM-107. Orchestrator не должен вызывать
`repository.latest()` после ошибки и не должен иметь собственный repository.

## Consumers

- UI: `app/ui/tender_full_analysis_dialog.py` читает существующее поле
  `TenderFullAnalysisResult.ai_document_analysis`, отображает все безопасные
  статусы и запускает экспорт;
- HTML/JSON: `app/reporting/tender_ai_analysis.py` экспортирует
  `AiDocumentAnalysis.to_payload()` либо экранированный HTML;
- RM-107: `app/tenders/participation_decision_service.py` учитывает только
  findings с `verified=True` и непустым evidence;
- deterministic summary: `app/tenders/tender_summary.py` использует готовое
  решение RM-107, а не рассчитывает AI recommendation.

Публичное поле `TenderFullAnalysisResult.ai_document_analysis` должно быть
сохранено для обратной совместимости UI и exporter.

## Существующие fallback-механизмы

- `DisabledProvider` возвращает безопасный status без сети;
- analyzer преобразует provider exception/error/invalid response в безопасный
  `AiDocumentAnalysis`;
- task-service изолирует ошибки context builder и repository, не раскрывая
  исходный exception;
- corrupt/incompatible cache не становится подтверждённым результатом;
- full analysis продолжает score, RM-107 и deterministic summary при ошибке AI;
- неподтверждённые findings не влияют на решение;
- критический stop-factor возвращается из Decision Engine до анализа score и AI.

В `app/tenders/full_analysis.py` при этом дублируются последняя граница exception
и преобразование AI status в пользовательское предупреждение. Эта политика
должна перейти в Orchestrator.

## Переиспользуемые компоненты

- `app/core/ai/schemas.py`;
- `app/core/ai/analyzer.py`;
- `app/core/ai/document_context.py`;
- `app/core/ai/repository.py`;
- `app/core/ai/prompts.py`;
- `app/ai/provider.py`;
- `app/tenders/participation_decision_service.py`;
- `app/tenders/tender_summary.py`;
- `app/tenders/full_analysis.py` как единственный end-to-end workflow;
- текущие UI и HTML/JSON exporter.

## Изменения БД

Миграция БД не требуется. Orchestrator является stateless application service,
не создаёт таблицу запусков и переиспользует существующий
`AiDocumentAnalysisRepository`. Формат `AiDocumentAnalysis` и его payload не
меняются.

## Границы RM-111

В RM-111 входят только:

- `TenderAiOrchestrator` и `TenderAiOrchestrationResult`;
- единая последняя граница unexpected exception;
- централизованная status-to-warning policy;
- wiring одного Orchestrator в production runtime;
- маршрутизация AI-этапа полного анализа через Orchestrator;
- presentation новой стадии при сохранении существующего payload;
- удаление неиспользуемого legacy provider workflow;
- unit/integration/UI/export regression tests.

Не входят provider selection, local runtime, новая OpenAI integration/schema,
новые agents, retries, failover, parallel execution, новые citations,
специализированные анализаторы, новая БД, AI score или AI recommendation.
C17 canonicalization и C19 live verification также не изменяются.

## Итог приёмки

Требования из `docs/RM-111_REQUIREMENTS.md` реализованы в ветке
`feat/rm-111-ai-orchestrator`. Целевой набор дал `93 passed`, полный локальный
pytest — `748 passed` за 42,79 с; Ruff check/format, mypy для 7 файлов, security
scan и dependency audit успешны. Миграция БД не требуется.

PR #24 слит в `main` коммитом `f246381`. Обязательная Windows matrix
merge-коммита успешно завершена на Python 3.12 и 3.13. RM-111 соответствует
Definition of Done. RM-112 назначен следующим активным этапом.
