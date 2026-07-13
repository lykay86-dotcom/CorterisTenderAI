# RM-111 — требования к TenderAiOrchestrator

Дата: 13 июля 2026 года. Статус: `APPROVED FOR IMPLEMENTATION` в пределах
активного RM-111.

## Ответственность

`TenderAiOrchestrator` — единственная application-service точка входа для
запуска существующего AI task-service из полного анализа. Он координирует один
вызов `TenderDocumentAiAnalysisService`, формирует безопасный envelope текущего
запуска и не содержит domain policy.

## Публичный контракт

Создать `app/core/ai/orchestrator.py`:

```python
@dataclass(frozen=True, slots=True)
class TenderAiOrchestrationResult:
    registry_key: str
    document_analysis: AiDocumentAnalysis
    started_at: str
    completed_at: str
    warnings: tuple[str, ...]

    @property
    def degraded(self) -> bool: ...


class TenderAiOrchestrator:
    def __init__(
        self,
        document_analysis_service: TenderDocumentAiAnalysisService,
    ) -> None: ...

    def run(
        self,
        registry_key: str,
        *,
        force: bool = False,
    ) -> TenderAiOrchestrationResult: ...
```

Экспортировать оба типа из `app/core/ai/__init__.py`.

## Функциональные требования

1. Пустой после `strip()` `registry_key` отклоняется через `ValueError`.
2. Task-service вызывается ровно один раз за `run`.
3. `force` передаётся без изменения семантики.
4. Возвращается `AiDocumentAnalysis` именно текущего вызова.
5. Findings, evidence, summary и payload task-service не переписываются.
6. Неожиданное исключение последней границей преобразуется в новый безопасный
   результат текущего запуска со status `provider_error`.
7. Текст exception, traceback, credentials и приватный путь не копируются в
   result или warnings.
8. Предупреждения task-service и status-policy дедуплицируются с сохранением
   первого порядка.
9. `started_at` и `completed_at` — timezone-aware ISO 8601.
10. `degraded=True` для любого status кроме `complete`.

## Status policy

Orchestrator централизованно преобразует status в безопасное предупреждение:

- `complete` — без дополнительного предупреждения;
- `partial` — анализ выполнен частично;
- `no_documents` — подходящие документы отсутствуют;
- `provider_disabled` — provider отключён, локальная цепочка продолжается;
- `provider_error` — provider недоступен, локальная цепочка продолжается;
- `invalid_response` — ответ отклонён защитной проверкой;
- `cache_incompatible` — сохранённый payload несовместим.

Неизвестный status нормализуется существующей моделью
`AiDocumentAnalysis` в `invalid_response`; UI не определяет эту policy.

## Интеграция runtime

`create_tender_search_runtime()` создаёт ровно по одному экземпляру:

- `AiDocumentAnalysisRepository`;
- `TenderDocumentContextBuilder`;
- `TenderDocumentAiAnalyzer` с `DisabledProvider`;
- `TenderDocumentAiAnalysisService`;
- `TenderAiOrchestrator`.

`TenderSearchRuntime` получает поле
`ai_orchestrator: TenderAiOrchestrator | None = None`. Provider selection,
model, base URL и credentials не добавляются.

## Интеграция полного анализа

- `TenderFullAnalysisService` зависит от Orchestrator, а не от task-service;
- добавляется `FullAnalysisStage.RUNNING_AI` с presentation label
  «AI-анализ документации»;
- `total_steps` корректируется для новой стадии;
- `orchestrator.run(key)` вызывается один раз;
- `orchestration.document_analysis` сохраняется в обратно совместимом поле
  `TenderFullAnalysisResult.ai_document_analysis`;
- `orchestration.warnings` добавляются в общие warnings;
- текущий analysis явно передаётся в
  `ParticipationDecisionService.evaluate(ai_document_analysis=...)`;
- full analysis больше не содержит AI exception/status policy;
- deterministic summary формируется после Decision Engine как прежде.

## Decision safety

- Orchestrator не вычисляет score, recommendation или confidence;
- он не вызывает `ParticipationDecisionService` сам;
- RM-107 получает текущий result явно из full analysis;
- только существующая проверка exact quote может сделать finding verified;
- unverified finding не влияет на решение;
- stale cache не подменяет ошибку текущего запуска;
- critical stop-factor сохраняет абсолютный приоритет.

## UI и export compatibility

- UI только показывает новую progress stage и существующие безопасные statuses;
- UI не вызывает provider и не содержит status/orchestration policy;
- вкладка AI и кнопка экспорта сохраняются;
- `TenderAiAnalysisExporter` не меняет JSON payload и поддерживает все statuses;
- HTML продолжает экранировать пользовательские и AI-строки.

## Legacy cleanup

`app/ai/structured_analysis.py` не должен оставаться вторым provider workflow.
Неиспользуемые `TenderAIService`, собственные result models, prompt, score и
recommendation удаляются. `_extract_json` и `validate_citations` могут временно
остаться как совместимые legacy helpers для `tests/test_v14.py`; они не должны
импортировать provider или выполнять AI orchestration.

## Persistence и миграции

Новых таблиц, полей и repository не создаётся. Миграция БД: **не требуется**.
Существующая cache reuse/force semantics остаётся ответственностью
`TenderDocumentAiAnalysisService`.

## Приёмка

Обязательны новые `tests/test_ai_orchestrator.py` и
`tests/test_ai_orchestrator_runtime_integration.py`, обновление integration/UI/
export tests и выполнение целевого набора из задания. После него обязательны:

```text
python -m pytest -q
python -m ruff check .
python -m ruff format . --check
```

RM-111 переводится в `DONE` только после зелёных локальных и GitHub checks,
обновления ROADMAP/STATUS/HISTORY и merge PR в `main`. Только затем разрешено
назначить RM-112.
