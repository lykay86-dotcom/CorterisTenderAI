# Архитектура EIS parser stage 1

## Цель и граница

RM-126.1 укрепляет существующий `AsyncEisTenderProvider`; источником истины остаётся
публичный HTML ЕИС. Основная цепочка не меняется:

```text
AsyncHttpClient
→ AsyncProviderSearchEngine
→ AsyncEisTenderProvider
→ UnifiedTender
→ CollectorStateRepository
→ Verification → Scoring → Full Analysis
```

Новые parser-компоненты являются внутренними адаптерами. `app.tenders.providers.eis`
остаётся публичным facade для существующих sync imports, shared URL/search helpers и
обратной совместимости. Внутренний package называется `eis_parser`, потому что Python не
позволяет одновременно иметь `providers/eis.py` и `providers/eis/`; это избегает опасного
массового переноса публичного модуля в рамках hardening stage.

## Поток данных

```text
search URL discovery
→ search-card parser (eis-search-v3)
→ EisParseDiagnostics + strict search validation
→ deterministic EisLawType detection
→ allowed detail URL resolver
→ notice 44 parser (eis-notice-44-v1)
   или notice 223 parser (eis-notice-223-v1)
→ required-field validation
→ merge detail over exact search facts
→ UnifiedTender + raw_metadata.eis_details + field_provenance
```

`UNKNOWN` никогда не выбирает parser случайно. Отсутствующее optional value остаётся
`None`/пустым tuple. Обязательные `procurement_number`, `title`, `source_url`, `law` и
`customer.name` проверяются fail-closed.

## Модули

Планируемый внутренний package:

```text
app/tenders/providers/eis_parser/
    __init__.py
    errors.py             # typed blocked/structure/validation errors
    models.py             # EisLawType, details, diagnostics, health result
    page_detection.py     # blocked/error/maintenance/search/44/223 detection
    search_parser.py      # strict search diagnostics/validation facade
    detail_router.py      # law detection, allowlisted URL resolution, dispatch
    notice_44_parser.py   # 44-ФЗ detail fields
    notice_223_parser.py  # 223-ФЗ detail fields/lots
    documents_parser.py   # document metadata only, no downloads
    validation.py         # mandatory fields, success-rate threshold, URL safety
    snapshots.py          # opt-in safe snapshots
```

Текущий lightweight DOM из `eis.py` сохраняется на этапе 1: новые production dependencies
не требуются, EXE/build risk не увеличивается. Его можно заменить после отдельного
доказательства необходимости; parser API и fixtures из этого этапа создают boundary для
такой замены.

## Модель и merge

`EisTenderDetails` использует `Decimal`, timezone-aware `datetime` и tuples. Поля,
которые уже есть в `UnifiedTender`, обновляются только при точно распознанном detail value.
Остальные сериализуются в `raw_metadata["eis_details"]` строками/списками:

- ИНН, КПП, organization code и контакты;
- delivery place, funding source;
- bid/contract/warranty security и advance percent как decimal strings;
- OKPD2, KTRU, requirements, restrictions, advantages, lots;
- parser versions и structured parse diagnostics.

`customer.inn`, `customer.kpp`, `customer.address`, `classification_codes`, dates,
`documents` и provenance заполняются существующими model fields. Новая DB migration не
нужна, поскольку collector codec уже versioned и сохраняет `raw_metadata`.

## URL и transport policy

Перед каждым detail/documents request URL валидируется:

- scheme только `https` (существующий тестовый `http` допустим лишь через явно injected
  config без production network);
- host только `zakupki.gov.ru` или `www.zakupki.gov.ru`;
- запрещены credentials in URL, localhost, IP literals, private/link-local/loopback hosts;
- fragment удаляется, procurement number нормализуется;
- ни parser, ни snapshot writer не выполняют сетевых запросов самостоятельно.

Все async requests идут через injected `AsyncHttpClient` и сохраняют retry, rate limit,
response-size limit и cancellation. CAPTCHA/403 превращаются в typed access-blocked error;
обход не выполняется.

## Structural-change policy

`EisParserStructureChangedError` поднимается, если:

- `total > 0`, но карточек нет;
- карточки есть, но ни одна не разобрана;
- при `cards_detected >= 3` success rate ниже `0.70`;
- отсутствует обязательный container/field;
- page type, law или detail adapter не распознаны;
- распознана maintenance/error page;
- HTML malformed настолько, что обязательная структура не подтверждается.

Корректная explicit-empty page возвращает пустой result и диагностику, не ошибку.

## Health, diagnostics и snapshots

Health check выполняет два логически раздельных probe:

1. network probe — один минимальный публичный search request и HTTP result;
2. parser probe — page detection, разбор search и required-field validation.

Probe не пишет checkpoint/registry, не запускает AI и не загружает документы. Итог остаётся
совместимым с `ProviderHealth`; structured split доступен провайдеру для тестов/operations.

Snapshots выключены по умолчанию. При opt-in они пишутся в
`<data_directory>/collector/debug/eis/YYYY-MM-DD/` атомарно, с timestamp и SHA-256 prefix.
Metadata строится из allowlist полей; cookies, request headers, Authorization и bearer
tokens не принимаются writer API.

## Совместимость и проверка

Сохраняются `ProviderDescriptor.id = "eis"`, `TenderSource.EIS`, public imports,
checkpoint scope, async factory/DI, SQLite schema, UI call sites и downstream workflows.
Fixtures полностью offline. Live canary — отдельный явный script, максимум один search и
10 результатов, без persistence/AI/documents и без обхода защиты.

Проверка идёт слоями: unit fixtures → router/detail/get_tender integration → EIS/Collector
target → workflow smokes → full pytest → Ruff/format/mypy/secret scan/pip-audit/diff check.

