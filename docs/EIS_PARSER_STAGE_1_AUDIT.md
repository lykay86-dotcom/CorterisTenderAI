# RM-126.1 — аудит парсера ЕИС, этап 1

Дата: 16 июля 2026 года.
Baseline: `45d63ff4eba95d8443baed37275e619280634e12`.
Ветка: `feat/rm-126-eis-parser-hardening-stage-1`.
Среда: Windows, Python 3.12.7, Europe/Moscow (UTC+03:00).

## Вывод

Текущий EIS-контур пригоден для укрепления без второго Collector, HTTP-клиента,
модели тендера, базы данных или workflow анализа. Основной функциональный разрыв:
`EisTenderProvider.get_tender()` и `AsyncEisTenderProvider.get_tender()` выполняют точный
поиск и возвращают поисковую карточку, но не загружают и не разбирают detail-page закупки.
Поисковый парсер частично fail-closed, однако не отличает корректную пустую выдачу от
изменения структуры во всех требуемых случаях, не публикует структурированную диагностику
и не разделяет network health и parser health.

Production-код до фиксации этого аудита не изменялся.

## Проверенный контур

- `app/tenders/providers/eis.py`: общий sync-провайдер, HTML DOM, search/documents parser,
  URL builder и фильтрация;
- `app/tenders/providers/eis_async.py`: целевой нативный async-адаптер Collector;
- `app/tenders/collector/async_http.py`: единый async HTTP transport, retry, rate limit,
  cancellation и ограничения размера ответа;
- `app/tenders/collector/eis_checkpoint.py`: скользящее окно публикации и checkpoint;
- `app/tenders/models.py`, `app/tenders/provider_base.py`: единые модели и контракты;
- `app/tenders/collector/codec.py`, `app/tenders/collector/store.py`: JSON payload внутри
  существующего `tender_registry.sqlite3`;
- `app/tenders/collector/verification.py`: provenance и уровень доверия официальной ЕИС;
- `app/tenders/collector/health_monitor.py`, `app/tenders/collector/async_engine.py`:
  circuit breaker и operational health;
- существующие EIS, checkpoint, health и persistence tests.

## Фактическое состояние

### Модель и persistence

`UnifiedTender` уже содержит необходимые стабильные поля: источник, идентификаторы,
название, заказчика, URL, даты, `TenderMoney`, закон, регион, классификаторы, документы и
`raw_metadata`. `TenderCustomer` поддерживает ИНН, КПП, регион и адрес. Деньги хранятся как
`Decimal`, сериализуются строкой; документы сериализуются вместе с timezone-capable
`published_at`. Дополнительные detail-поля можно безопасно хранить в versioned
`raw_metadata["eis_details"]`, поэтому миграция SQLite для RM-126.1 не требуется.

`CollectorStateRepository` остаётся единственным persistence root. Existing codec
round-trip сохраняет `raw_metadata` и документы, следовательно отдельная БД или таблица
не нужна.

### Search parser

`EisHtmlParser.parse_search()` поддерживает current/legacy card containers, извлекает
номер, title, customer, region, price, даты, закон, статус, процедуру и URL. Он уже
отбрасывает неразобранные карточки и завершает запрос ошибкой, если карточки найдены, но
не разобрана ни одна. Недостающие возможности:

- нет `EisLawType` и детерминированного law detection по card/URL/HTML priority;
- отсутствует `EisParseDiagnostics` и порог success rate `< 0.70` при трёх карточках;
- `total > 0` при нуле карточек не считается structural change;
- maintenance/error/malformed/unknown page не классифицируются отдельно;
- обязательный customer сейчас подменяется строкой «Заказчик не указан», что нарушает
  правило «отсутствует → None/ошибка, не выдумывать»;
- parser version — общий `eis-html-2`, а не требуемый набор версий;
- search datetimes создаются naive и требуют timezone-aware нормализации.

### Detail и документы

Настоящего detail parser нет. Оба `get_tender()` возвращают найденный search item.
`list_documents()` после повторного поиска отдельно открывает documents tab и использует
общий link parser. ИНН, КПП, `organizationCode`, контакты, delivery, funding, securities,
advance, OKPD2/KTRU, requirements/restrictions/advantages и lot data не извлекаются.

### Network, безопасность URL и блокировки

Async-путь уже использует `AsyncHttpClient`, provider network settings, retry, rate limit и
`CollectorCancellationToken`. CAPTCHA markers распознаются, HTTP 403 не обходится.
Однако `EisProviderConfig.base_url`, detail URL и document URL пока принимают любой
абсолютный HTTP(S) host. Для RM-126.1 нужен единый allowlist только
`zakupki.gov.ru`/`www.zakupki.gov.ru` с запретом `file://`, localhost, private IP и иных
hosts до сетевого вызова.

### Health и snapshots

`AsyncEisTenderProvider.check_health()` проверяет только home-page и смешивает доступность
с распознаванием текста. Общий `ProviderHealthMonitor` хранит connection mode и один
parser version, но не отдельные результаты network/parser probe. Без изменения общей
схемы разделение можно выразить в structured health result/message и диагностике
провайдера; operational circuit breaker переиспользуется.

Безопасных HTML snapshots нет. Требуется opt-in writer в
`<data_directory>/collector/debug/eis/YYYY-MM-DD/`, который сохраняет только body,
sanitized metadata и error text, не сохраняет request headers, cookies, Authorization или
bearer token.

### Совместимость и decision boundary

`ProviderDescriptor.id = "eis"`, `TenderSource.EIS`, async factory, checkpoint,
Collector, verification, scoring и full analysis уже связаны корректно. Их публичные
контракты необходимо сохранить. Парсер может добавлять факты и provenance, но не должен
менять score, recommendation или приоритет critical stop-factor.

## Риски и решения

| Риск | Уровень | Решение RM-126.1 |
|---|---:|---|
| `get_tender()` не открывает detail-page | HIGH | search discovery → detail fetch → law router → strict adapter → merge |
| HTML drift выглядит как пустая выдача | HIGH | page detection, diagnostics и `EisParserStructureChangedError` |
| Неизвестный закон выбирает неверный parser | HIGH | `EisLawType.UNKNOWN` и запрет случайного fallback |
| Любой host может попасть в URL helper | HIGH | централизованный allowlist до HTTP request |
| Naive datetime | HIGH | фиксированная timezone ЕИС Europe/Moscow |
| Подстановка customer скрывает отсутствие факта | HIGH | обязательные поля detail fail-closed |
| Network и parser health смешаны | MEDIUM | отдельные probes без записи в registry |
| Debug HTML может содержать чувствительные данные | MEDIUM | opt-in safe snapshots с sanitized metadata |
| Перенос `eis.py` в одноимённый package ломает импорты | MEDIUM | оставить публичный facade `eis.py`, новые внутренние модули разместить в `eis_parser/` |

## Baseline validation

Локально, до application changes:

- EIS/health target: `21 passed in 6.05s`;
- repository secret scan: passed;
- Ruff check: `All checks passed!`;
- Ruff format: `523 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- offline smoke: `2 passed in 3.74s`;
- migration/schema smoke: `5 passed in 2.68s`;
- public import: `DashboardController`;
- composition smoke: `1 passed in 0.18s`;
- release/build smoke: `6 passed in 3.23s`;
- full pytest: `1496 passed in 57.55s`;
- dependency audit: `No known vulnerabilities found`;
- post-activation main Quality Gate run `29457841490`: Python 3.12
  `1496 passed in 84.22s`, Python 3.13 `1496 passed in 61.43s`; secret scan, Ruff,
  format (`523 files`), mypy (20 files), smoke tests и dependency audit passed.

Первый локальный `pip-audit` был заблокирован sandbox-доступом к `pypi.org`; повторный
разрешённый запуск завершился успешно. Это инфраструктурное ограничение, а не дефект
репозитория.

## Граница реализации

Реализация должна расширить существующий provider/Collector путь. Не входят: browser или
Playwright, обход CAPTCHA/403/rate limits, загрузка содержимого документов, второй
collector/client/model/database/workflow, новый UI, изменения scoring/AI и live network в
обычных тестах.
