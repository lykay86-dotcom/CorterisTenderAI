# RM-110 — аудит стабилизации Tender Intelligence

Дата: 13 июля 2026 года.

## Область аудита

Проверены актуальный `main` после PR #18, проектные документы, история PR
RM-107–RM-109 и существующая цепочка Tender Intelligence. RM-110 укрепляет
существующие компоненты и не создаёт второй анализатор, repository, Decision
Engine, слой экспорта или UI бизнес-логику.

## Текущий путь данных

```text
TenderDocumentDownloadService
→ TenderDocumentTextService (локально извлечённый текст и checksum)
→ TenderDocumentContextBuilder
→ TenderDocumentAiAnalysisService
→ TenderDocumentAiAnalyzer / AIProvider
→ exact quote verification
→ AiDocumentAnalysisRepository (SQLite, fingerprint)
→ ParticipationDecisionService (только verified findings)
→ DeterministicTenderSummaryGenerator
→ TenderFullAnalysisResult
→ TenderFullAnalysisDialog
→ TenderAiAnalysisExporter (HTML/JSON)
```

Production composition root `app/tenders/search_runtime.py` создаёт один
`AiDocumentAnalysisRepository`, один analyzer и один service. Тот же repository
передаётся в RM-107. По умолчанию используется `DisabledProvider`, поэтому
локальный анализ обязан оставаться основным рабочим режимом.

## Переиспользуемые компоненты

| Компонент | Ответственность RM-110 |
|---|---|
| `app/core/ai/schemas.py` | укрепить существующие контракты и безопасную сериализацию |
| `app/core/ai/analyzer.py` | нормализовать ответ провайдера и изолировать ошибки |
| `app/core/ai/document_context.py` | сделать существующий контекст ограниченным и воспроизводимым |
| `app/core/ai/repository.py` | версионировать существующий кеш и восстанавливать историю |
| `app/tenders/full_analysis.py` | добавить защитную границу вокруг существующего AI-сервиса |
| `app/tenders/participation_decision_service.py` | сохранить правило: влияют только verified findings текущего запуска |
| `app/ui/tender_full_analysis_dialog.py` | отображать статусы, предупреждения и partial result |
| `app/reporting/tender_ai_analysis.py` | сохранить существующий HTML/JSON-экспорт для любого безопасного статуса |

## Форматы и статусы результата

Сейчас `AiDocumentAnalysis.status` является произвольной строкой. Фактически
используются `complete`, `no_documents`, `provider_error` и
`invalid_response`; значение по умолчанию — `partial`. Нет отдельного статуса
для отключённого провайдера и несовместимого кеша. Payload не имеет версии, а
`created_at` хранится только в SQLite и создаётся через `CURRENT_TIMESTAMP`
без offset.

RM-110 вводит совместимый типизированный набор:

- `complete` — ответ целиком прошёл защитную нормализацию;
- `partial` — корректные части сохранены, повреждённые отброшены;
- `no_documents` — подходящего локально извлечённого текста нет;
- `provider_disabled` — AI явно отключён, локальный workflow продолжен;
- `provider_error` — провайдер/сеть завершились ошибкой;
- `invalid_response` — ответ нельзя безопасно интерпретировать;
- `cache_incompatible` — запись имеет неподдерживаемую версию.

Статусы ошибок не являются успешным AI-анализом и не должны давать verified
findings.

## Проверка evidence и влияние на RM-107

`TenderDocumentAiAnalyzer` считает finding подтверждённым только если
`document_id` известен, quote непустая и точная quote содержится в локально
извлечённом тексте этого документа. `ParticipationDecisionService` уже
фильтрует risks, suspicious conditions и contradictions по `item.verified` и
наличию evidence. Это правило сохраняется.

Обнаружена интеграционная проблема: после ошибки нового AI-запуска RM-107
читает `repository.latest(registry_key)` и может получить старый успешный
анализ другого контекста. RM-110 должен передавать безопасный результат
текущего запуска в Decision Engine либо гарантировать эквивалентную привязку к
текущему fingerprint. Неподтверждённый или устаревший finding не должен влиять
на решение. Абсолютный приоритет критического стоп-фактора уже реализован до
обработки score и AI evidence и изменяться не будет.

## Кеш, fingerprint и SQLite

Текущий fingerprint содержит только входной порядок троек `document_id`,
`checksum_sha256`, `verification_status`. Он не сортирует логически одинаковую
выборку и не учитывает prompt/schema/analyzer/context versions и параметры
контекста. Изменение алгоритма может переиспользовать устаревший результат.

Таблица `tender_ai_document_analyses` создаётся самим специализированным
repository в отдельной БД `tender_ai_analysis.sqlite3`. У неё нет версии
payload/schema; `created_at` использует SQLite `CURRENT_TIMESTAMP`. Методы
`reusable` и `latest` читают одну строку и напрямую вызывают `json.loads` и
`from_payload`. Повреждённая последняя запись поэтому блокирует предыдущую
корректную историю. Миграция должна быть идемпотентной внутри этого repository:
добавить столбец версии без удаления истории и читать старые записи защитно.

## Контекст

`TenderDocumentContextBuilder` использует только результаты локального
извлечения и не выполняет сетевых запросов или чтения оригинальных документов.
Это правильная граница. При этом текущая реализация:

- зависит от порядка `list_results`;
- не дедуплицирует одинаковый checksum;
- не имеет лимита на документ и общего лимита;
- не сохраняет признак сокращения и статистику;
- не включает параметры формирования контекста в fingerprint.

RM-110 добавит стабильную сортировку, исключение пустых значений и дублей,
Unicode-safe slicing, явный признак сокращения и детерминированную статистику.

## Места возможного прерывания полного анализа

1. `AIProvider.analyze`: timeout, сеть или произвольное исключение сейчас не
   перехватываются анализатором.
2. Ответ провайдера не Mapping, JSON верхнего уровня не object,
   `requirements` не Mapping, неверные collections и значения evidence могут
   вызвать `AttributeError`, `TypeError` или `ValueError`.
3. `AiEvidence` отклоняет нечисловой, NaN/Infinity или выходящий за диапазон
   confidence; page не нормализуется.
4. `AiDocumentAnalysisRepository.reusable/latest`: повреждённый JSON или payload
   прерывает чтение всей истории.
5. `initialize/save`: ошибка SQLite или файловой системы выходит наружу.
6. `TenderDocumentAiAnalysisService` не изолирует ошибки build/read/analyze/save.
7. `TenderFullAnalysisService.run` обрабатывает только отмену; AI-исключение
   препятствует RM-107, summary, persistence, UI и экспорту.

Пользовательские предупреждения должны быть фиксированными и безопасными: без
API-ключа, Authorization header, полного ответа провайдера и traceback.

## Offline и UI/экспорт

`DisabledProvider` возвращает `status=disabled`, но analyzer сейчас переводит
его в `provider_error`. UI показывает сырое значение статуса и не объясняет
`partial`, `no_documents`, отключение провайдера, несовместимый кеш или
сокращение контекста. HTML/JSON-экспорт уже отделён от UI и пригоден для
переиспользования, но должен получать только безопасно нормализованный payload.

## Отказные сценарии RM-110

- provider disabled, exception, timeout или status error;
- не-JSON и JSON не-object;
- повреждённые уровни requirements/findings/evidence;
- неизвестный документ, пустая/неточная quote;
- неверные confidence/page и слишком длинные поля;
- частично корректный payload;
- изменение документа, версий алгоритма или лимитов контекста;
- повреждённая/несовместимая последняя запись кеша;
- ошибка записи SQLite;
- отсутствие, недоступность, дублирование или сокращение документов;
- отображение и экспорт complete/partial/error-safe результата;
- повторный запуск после ошибки.

Во всех случаях детерминированные score, RM-107 и summary продолжают работу;
AI-ошибка переводит полный анализ в `PARTIAL`, но не создаёт AI-факты.

## Границы этапа

RM-110 не реализует AI Orchestrator, выбор провайдера, локальный AI runtime,
новую OpenAI-compatible интеграцию, публичную строгую JSON Schema, новую
систему provenance, специализированный анализ ТЗ/договора/заявки и редизайн
UI. Эти функции относятся к RM-111–RM-119. Изменения RM-110 должны быть
минимальными и обратно совместимыми.

