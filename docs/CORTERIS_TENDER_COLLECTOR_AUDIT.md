# Corteris Tender Collector — C1 Audit & Baseline

Дата аудита: 12 июля 2026 г.  
Проект: `CorterisTenderAI 1.5.1`  
Цель: подготовить безопасное внедрение многоплощадочного сборщика без поломки ручного импорта, смет, анализа, отчётов и сборки Windows EXE.

## 1. Проверенный baseline

- В архиве: 173 Python-файла приложения, около 43 167 строк кода.
- В тестах: 132 файла `test_*.py`, статически найдено 373 тестовые функции.
- `python -m compileall -q app tests`: успешно.
- Выбранный core-набор тендеров, документов, анализа и БД: **119 passed**.
- Полный UI-набор в среде аудита не запускался: в ней отсутствует PySide6. На компьютере разработчика PySide6 установлен и UI-тесты должны запускаться отдельно.

Команда проверенного core-набора приведена в `README_COLLECTOR_C1.txt`.

## 2. Архитектура, которую нужно сохранить

### Единая модель и провайдеры

- `app/tenders/models.py` — `UnifiedTender`, `TenderMoney`, `TenderDocument`, `TenderCustomer`.
- `app/tenders/provider_base.py` — стабильный контракт `TenderProvider`, `TenderSearchQuery`, capabilities, descriptor и health.
- `app/tenders/provider_registry.py` — регистрация, порядок, включение/отключение.
- `app/tenders/provider_factory.py` — composition root провайдеров.
- `app/tenders/search_engine.py` — параллельный поиск, изоляция ошибок и первичная дедупликация.

### Уже реализованные рабочие компоненты

- `app/tenders/providers/eis.py` — реальный публичный HTML-коннектор ЕИС, не официальный API.
- `app/tenders/corteris_filter.py` и `corteris_search.py` — классификация и релевантность Кортерис.
- `app/tenders/search_profiles.py` — встроенные профили поиска.
- `app/tenders/tender_registry.py` — локальный реестр результатов и история поисковых запусков.
- `app/tenders/document_storage.py` — загрузка, SHA-256, повторное использование файлов.
- `app/tenders/document_text_extractor.py` — PDF/DOCX/XLSX/TXT/ZIP.
- `app/tenders/requirement_analysis.py` — лицензии, опыт, обеспечение, сроки и риски.
- `app/ui/tender_search_ui_controller.py` — сетевые операции вынесены из GUI-потока через `QThreadPool`.
- `app/core/json_serialization.py` — безопасный JSON для Decimal и других типов.
- `app/core/path_manager.py`, `log_manager.py`, `security/secrets.py` — пути, ротация логов и Windows keyring.

Эти модули нужно расширять, а не создавать параллельную несовместимую систему.

## 3. Текущее состояние источников

| Провайдер | Реализация | Статус аудита |
|---|---|---|
| ЕИС | публичный HTML | реализован, нестабилен при SSL/изменениях вёрстки |
| Сбер А | placeholder | не подключён |
| РТС-тендер | placeholder | не подключён |
| Росэлторг | placeholder | не подключён |
| B2B-Center | placeholder | не подключён |
| ТЭК-Торг | placeholder | не подключён |
| ЭТП ГПБ | placeholder | не подключён |
| Портал поставщиков Москвы | отсутствует | добавить первым после сетевого ядра |
| OTC | отсутствует | добавить descriptor/adapter после исследования |
| Фабрикант | отсутствует | добавить descriptor/adapter после исследования |

Ни один placeholder нельзя показывать пользователю как рабочее подключение.

## 4. Критические риски

### C1. Небезопасная распаковка ручного импорта

`app/services/import_service.py` использует `ZipFile.extractall(base)` без проверки путей. Архив с `../` способен записать файл вне папки тендера. До автоматического скачивания архивов это нужно заменить безопасным extractor-ом.

### C2. Несколько несвязанных хранилищ SQLite

Сейчас используются:

- `corteris_tender_ai.db` — основная SQLAlchemy БД;
- `tender_registry.sqlite3` — найденные тендеры;
- `tender_documents/document_catalog.sqlite3` — файлы;
- `tender_text/text_catalog.sqlite3` — извлечённый текст;
- `tender_analysis.sqlite3` — анализ требований.

Система работает, но единая транзакция «сбор → изменение → документы → анализ» отсутствует. Для Collector не следует создавать шестую независимую БД. Таблицы `provider_status`, `collection_runs`, `tender_changes`, `tender_sources` и checkpoints рекомендуется добавить версионированной миграцией в `tender_registry.sqlite3`, сохранив совместимость.

### C3. Таймаут ThreadPool не отменяет выполняющийся запрос

`TenderSearchEngine` помечает future как timed out и вызывает `cancel()`, но уже запущенный поток не останавливается. При зависающих площадках возможны фоновые запросы после завершения поиска. Новое сетевое ядро должно иметь реальную cooperative cancellation через `asyncio`/`httpx`.

## 5. Высокие риски и технический долг

1. `app/database/base.py::json_safe()` преобразует `Decimal` во `float`. Системное исправление JSON сделано не во всех путях.
2. `TenderSearchQuery.min_price/max_price` и поисковые профили используют `float`; денежные фильтры должны перейти на `Decimal` с обратной совместимостью JSON.
3. Дедупликация сейчас в основном опирается на `procurement_number`; нет полной цепочки external ID → ИНН+название+цена+deadline → content hash.
4. Реестр обновляет текущую запись, но не хранит field-level историю изменений НМЦК, срока, статуса и документов.
5. Нет persisted HealthMonitor, consecutive failures, circuit breaker и автоматического повторного включения источника.
6. Нет per-domain RateLimiter, обработки `Retry-After`, 429 и 5xx на общем уровне.
7. `httpx` и CA bundle не объявлены в зависимостях.
8. Placeholder-провайдеры имеют заявленные capabilities, хотя вызов заканчивается `NOT_CONFIGURED`; состояние нужно разделить на capability, implementation и configuration.
9. Старый `app/connectors/eis.py` дублирует новый `app/tenders/providers/eis.py`.
10. Старый `app/parsers/documents.py` дублирует новый document pipeline.
11. `app/database/models.py` затенён пакетом `app/database/models/`; файл не участвует в runtime и создаёт риск ошибочного редактирования.
12. Крупные модули превышают 1 000 строк: registry, extractor, requirement analyzer и часть UI. Новые Collector-модули должны быть небольшими и разделёнными по ответственности.

## 6. Средние риски

- В архиве присутствуют `__pycache__` и готовый installer EXE; их следует исключить из исходного контроля и аудиторских архивов.
- `README.md` ссылается на документы в `docs/`, которых не было в предоставленном архиве.
- Заголовок `ModernMainWindow` содержит `1.3 Alpha`, тогда как версия приложения — `1.5.1`.
- `pyproject.toml` допускает Python 3.13, а build script требует строго Python 3.12.
- optional dev dependency ограничивает `pytest<9`, а фактическая среда пользователя использует pytest 9.1.1.
- PyInstaller spec требует `data/` и `assets/`; эти каталоги не входили в аудит-архив, поэтому сборку EXE на C1 подтвердить нельзя.

## 7. Целевая архитектура Collector

### Сохраняем

- `UnifiedTender` как основную доменную модель.
- Синхронный `TenderProvider` как backward-compatible контракт.
- `TenderProviderRegistry`, `TenderSearchEngine`, профили, фильтр, реестр, документы и анализ.

### Добавляем без поломки старого API

1. Опциональные async-методы провайдера с default bridge через `asyncio.to_thread`.
2. Native async transport на `httpx.AsyncClient`.
3. `CollectorService`, который запускает провайдеры через `asyncio.gather(return_exceptions=True)`.
4. Per-domain rate limiter и retry policy.
5. Persisted HealthMonitor и circuit breaker.
6. Normalizer и многоуровневый Deduplicator.
7. ChangeTracker с field-level diff.
8. Checkpoint для инкрементальных обновлений.
9. Scheduler, запускаемый в worker thread, без блокировки Qt.
10. Панель источников и явные состояния подключения.

## 8. План изменений по коммитам

### Collector C2 — Network Reliability Foundation

Новые файлы:

- `app/tenders/collector/config.py`
- `app/tenders/collector/async_http.py`
- `app/tenders/collector/rate_limiter.py`
- `app/tenders/collector/health_monitor.py`
- соответствующие unit tests

Изменяемые файлы:

- `pyproject.toml`
- `requirements.txt`
- `app/tenders/provider_base.py`
- `app/tenders/search_runtime.py`

### Collector C3 — Normalize, Dedupe, Changes

Новые файлы:

- `normalizer.py`
- `deduplicator.py`
- `change_tracker.py`
- `checkpoint.py`
- `collector_service.py`

Изменяемые:

- `models.py`
- `tender_registry.py` с idempotent schema upgrade
- `search_engine.py` или новый collector orchestration слой

### Collector C4 — ЕИС official-data research + adapter hardening

Сначала исследуется разрешённый официальный источник. Текущий HTML provider сохраняется как fallback и явно маркируется `public_html`.

### Collector C5 — Портал поставщиков Москвы

Добавляется только после фиксации реального разрешённого ответа и fixtures. Никаких вымышленных endpoint-ов.

### Collector C6+ — коммерческие площадки, UI, scheduler, рейтинг и EXE

Каждый источник получает отдельный adapter, fixtures и диагностику конфигурации.

## 9. Решение по обратной совместимости

- Не менять существующий `TenderProvider.search()` одним коммитом на async-only.
- Не удалять старые таблицы и JSON-профили.
- Не переносить сразу все данные между SQLite-файлами.
- Не запускать сеть при старте приложения.
- Не включать placeholder-провайдеры как рабочие.
- Не использовать `verify=False`.
- Все schema upgrades — повторно запускаемые, с резервной копией и тестом старой БД.

## 10. Результат C1

C1 добавляет только side-effect-free namespace, read-only baseline snapshot, документацию и regression tests. Поведение приложения, сеть, БД и UI не изменяются.
