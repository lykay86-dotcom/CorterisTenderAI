# PRE-RM-156 — полное техническое задание на Collector и адаптеры тендерных площадок

Дата решения владельца: 22 июля 2026 года.
Технический baseline для анализа: `origin/main` commit
`d007460f72bccc9486d1f330a865b74f15a6d368` от 21 июля 2026 года.

## 1. Статус документа и обязательное изменение порядка работ

Этот документ задаёт обязательный Collector prerequisite, который владелец проекта решил выполнить
до production-реализации RM-156. Само наличие этого файла не изменяет канонический активный этап.

Перед первым изменением application-кода необходимо отдельным docs-only PR:

1. Зафиксировать в `docs/STATUS.md`, что production-реализация RM-156 приостановлена владельцем до
   завершения Collector prerequisite.
2. Зафиксировать тот же порядок в `docs/ROADMAP.md` без изменения нумерации RM-001–RM-200 и без
   добавления нового RM.
3. Добавить запись в `docs/ROADMAP_HISTORY.md` с датой, причиной, ссылкой на docs-only PR и влиянием
   на RM-156–RM-158.
4. Сохранить RM-156 единственным каноническим RM и обозначить Collector как prerequisite, а не как
   параллельный RM.
5. После завершения prerequisite выполнить отдельный closeout, вернуть RM-156 в production work и
   только затем продолжать модель контрагента.

До merge этого docs-only PR разрешены только read-only аудит, исследование публичной документации,
создание ТЗ и offline fixtures без секретов. Production-код Collector менять нельзя.

Работу начинать в чистом отдельном worktree от актуального `origin/main`. Текущая локальная ветка
может отставать и содержать пользовательские изменения; их нельзя переносить, очищать, reset-ить или
перезаписывать.

## 2. Цель

Довести существующий Corteris Tender Collector до промышленной архитектуры многоплощадочного сбора:

- сохранить один канонический `CollectorService` и один `AsyncProviderSearchEngine`;
- исправить выявленные gaps действующего Collector;
- добавить нативные `AsyncTenderProvider` для всех площадок обязательного built-in реестра;
- обеспечить инкрементальный сбор, pagination/cursor, checkpoints и безопасное возобновление;
- сохранять доказуемое происхождение каждого поля и сырого ответа;
- поддерживать частичный результат при отказе отдельных площадок;
- не выдавать заглушку или неподтверждённый endpoint за работающий источник;
- исключить влияние AI и агрегаторов на детерминированное решение об участии;
- обеспечить offline CI, безопасные live diagnostics и воспроизводимые fixtures.

## 3. Ключевое архитектурное решение

### 3.1. Что сохраняется

Каноническими владельцами остаются:

| Область | Канонический владелец |
|---|---|
| Оркестрация | `app.tenders.collector.collector_service.CollectorService` |
| Параллельный поиск | `app.tenders.collector.async_engine.AsyncProviderSearchEngine` |
| Контракт площадки | `app.tenders.collector.async_provider.AsyncTenderProvider` |
| HTTP runtime | `CollectorNetworkRuntime` + `AsyncHttpClient` |
| Rate limit | `AsyncRateLimiter` |
| Circuit breaker/health | `ProviderHealthMonitor` и RM-139 source monitoring |
| Нормализация | `TenderNormalizer` |
| Дедупликация | `TenderDeduplicator` |
| Field verification | `TenderVerificationService` |
| Реестр и run history | `CollectorStateRepository` + `CollectorSchemaMigrator` |
| Настройки площадок | `CollectorProviderManager` и существующие versioned JSON stores |
| Секреты | `app.security.secrets` / Windows Credential Manager |
| Scheduler | существующий Collector scheduler/run-session boundary |
| Решение об участии | существующие RM-107 decision/stop-factor owners |

Запрещены второй Collector, второй search engine, третий provider catalog/factory, новый secret vault,
новая параллельная normalization/dedup chain и новый источник истины для `tender_records`.

### 3.2. Как используется Kingfisher Collect

Архитектурной основой и источником проверенных паттернов выбран
[Open Contracting Partnership / Kingfisher Collect](https://github.com/open-contracting/kingfisher-collect),
проверенный commit `835e015dbcba597518cf4a741e1169e3111c47b4` от 21 июля 2026 года.

Из Kingfisher применяются идеи:

- один source-specific adapter/spider на источник;
- общие base-паттерны для API, index, periodic/date-window и compressed-file источников;
- `from_date`/`until_date`, sample/dry-run, incremental collection;
- обработка JSON, line-delimited JSON, CSV, XLSX, ZIP/RAR и больших файлов;
- повтор запросов с `Retry-After`, статистика и проверка всех адаптеров;
- исходные файлы и metadata до преобразования;
- OCDS release/record как внешний обменный и исторический формат.

Не переносить:

- Scrapy/Scrapyd как второй runtime;
- Kingfisher Process, RabbitMQ и отдельную PostgreSQL composition;
- их storage/business ownership;
- browser impersonation, Cloudflare/access bypass;
- настройку `ROBOTSTXT_OBEY=False`;
- код площадок, для которых Corteris не имеет разрешённого способа доступа.

По умолчанию используется clean-room адаптация архитектурных паттернов. Если отдельный фрагмент
BSD-3-Clause кода переносится буквально или производно, обязательны code-level provenance,
сохранение copyright/license notice и запись в `THIRD_PARTY_NOTICES.md`. Kingfisher нельзя добавлять
как runtime dependency, git submodule или vendored project без отдельного dependency/лицензионного
аудита.

Лицензия основы: [BSD-3-Clause](https://github.com/open-contracting/kingfisher-collect/blob/main/LICENSE).

## 4. Граница понятия «все площадки»

«Все площадки» в этом ТЗ означает:

1. Все обязательные built-in источники таблицы ниже.
2. Все будущие разрешённые источники через существующий declarative custom/manual adapter boundary.
3. Агрегаторы только как discovery-only источники.

Это не означает автоматический scraping любого сайта в интернете. Источник без разрешённого
machine-readable контракта, договора, API/feed или допустимой публичной выгрузки остаётся
`BLOCKED_EXTERNAL`/`NOT_CONFIGURED` и не считается работающим.

## 5. Обязательный built-in реестр источников

Перечень федеральных операторов проверяется перед реализацией по актуальной редакции распоряжения
Правительства РФ № 1447-р. Reference на дату ТЗ:
[перечень операторов](https://www.consultant.ru/document/cons_doc_LAW_302473/3a4088b4429ca53189a0b3b932e98e10935cf57e/).

| ID | Площадка/источник | Текущий статус | Требуемый результат |
|---|---|---|---|
| `eis` | ЕИС, `zakupki.gov.ru` | реализован | аудит, исправление, bulk/incremental hardening |
| `mos_supplier` | Портал поставщиков Москвы | реализован, нужен token | аудит API-контракта, pagination/checkpoint hardening |
| `zakaz_rf` | АГЗРТ / ZakazRF | отсутствует в enum/catalog | новый built-in adapter после access audit |
| `roseltorg` | Единая электронная торговая площадка / Росэлторг | commercial placeholder | единый adapter для разрешённых секций, без duplicate identity |
| `rad` | Российский аукционный дом / Lot-online | отсутствует | новый built-in adapter после access audit |
| `tek_torg` | ТЭК-Торг | commercial placeholder | нативный adapter после access audit |
| `ets_nep` | Электронные торговые системы / НЭП | отсутствует | новый built-in adapter после access audit |
| `sber_a` | Сбербанк-АСТ | commercial placeholder | нативный adapter после access audit |
| `rts_tender` | РТС-тендер | commercial placeholder | нативный adapter после access audit |
| `gazprombank` | ЭТП ГПБ | commercial placeholder | нативный adapter после access audit |
| `b2b_center` | B2B-Center | commercial placeholder | нативный adapter после access audit |
| `fabrikant` | Фабрикант | commercial placeholder | нативный adapter после access audit |
| `otc` | OTC | commercial placeholder | нативный adapter после access audit |
| `tenderguru_discovery` | TenderGuru | отсутствует | optional discovery-only adapter, никогда не authoritative |
| `custom` | Пользовательский источник | declarative contour существует | сохранить безопасный расширяемый contract |

Перед изменением `TenderSource` выполнить identity/schema audit. Новые значения добавляются
versioned migration, не переименовывают существующие IDs и не ломают старые записи, настройки,
exports или сохранённые профили.

Для Росэлторг, Сбер А, РТС, ГПБ и других операторов государственные/223/коммерческие секции не
создают независимые business adapters, если используют один подтверждённый контракт и одну source
identity. Разные API/схемы оформляются как protocol/schema strategies внутри одного provider owner.

## 6. Уровни доверия источников

Ввести или расширить существующую typed trust policy без дублирования verification service:

1. `OFFICIAL_REGISTER` — ЕИС и иные нормативно признанные реестры.
2. `OFFICIAL_OPERATOR` — API/выгрузка оператора федеральной ЭТП.
3. `PRIMARY_COMMERCIAL_OPERATOR` — собственная разрешённая выгрузка коммерческой площадки.
4. `DECLARED_CUSTOM_SOURCE` — пользовательский источник с подтверждённым контрактом.
5. `DISCOVERY_ONLY` — TenderGuru и другие агрегаторы.

Выбор значения поля выполняется детерминированно по trust policy, freshness, полноте и стабильному
provider priority. Все кандидаты и конфликты сохраняются. AI не участвует в выборе.

`DISCOVERY_ONLY`:

- не проходит в normalizer/deduplicator основного реестра;
- не создаёт/обновляет `tender_records`;
- не участвует в score, stop-factor, recommendation, KPI или отчёте как подтверждённый факт;
- может создать только запись в `collector_aggregator_discoveries` и запрос официальной проверки;
- закрывается только совпадением от разрешённого official source.

## 7. Честная модель готовности адаптера

Каждый provider проходит последовательные состояния:

1. `CATALOGUED` — identity и homepage известны, сети нет.
2. `ACCESS_REVIEW` — проверяются договор, ToS, API/feed и допустимость хранения.
3. `CONTRACT_CAPTURED` — зафиксированы schema/auth/rate limits/endpoint host allowlist.
4. `FIXTURE_VERIFIED` — сохранён обезличенный реальный fixture и его metadata.
5. `IMPLEMENTED_OFFLINE` — parser/adapter проходит offline contract tests.
6. `LIVE_VERIFIED` — explicit diagnostic успешно выполнен с разрешёнными credentials.
7. `WORKING` — fixture, live check, health, mapping и rollback подтверждены.
8. `BLOCKED_EXTERNAL` — нет договора, документации, ключа или разрешённого endpoint.
9. `DISABLED` — отключён пользователем.

Нельзя выставлять `WORKING` только по наличию API key/base URL, успешному TCP/HTTP ответу, HTML
странице входа или искусственному fixture.

Для каждой площадки создать `docs/providers/<provider_id>.md` со следующими полями:

- юридическое лицо/оператор и публичный homepage;
- разрешённый тип доступа и основание;
- дата и автор проверки;
- hostname allowlist;
- auth scheme без значений секретов;
- endpoint paths/templates без query credentials;
- pagination/cursor/date-window contract;
- rate limits и `Retry-After` semantics;
- response formats, encoding, timezone, currency;
- mapping полей;
- документы/архивы;
- fixture inventory и redaction record;
- известные ограничения;
- live verification status;
- rollback/disable procedure.

Договоры, персональные данные, ключи и закрытая API-документация в Git не сохраняются. В документе
допустимы только безопасные ссылки/идентификаторы подтверждения.

## 8. Целевая последовательность данных

```text
Provider contract
  -> разрешённый shared transport
  -> raw artifact + transport metadata
  -> provider parser/mapping
  -> discovery gate
  -> TenderNormalizer
  -> TenderDeduplicator
  -> TenderVerificationService
  -> freshness
  -> deterministic stop-factor/ranking
  -> CollectorStateRepository
```

Discovery gate обязан выполняться до normalization/dedup. Добавить expected-red regression test,
который доказывает, что aggregator item не может попасть в deduplication, verification, persistence
или ranking даже когда engine уже сформировал partial deduplication snapshot.

## 9. Расширение `AsyncTenderProvider` без второго engine

Сохранить существующие методы `search`, `get_tender`, `list_documents`, `check_health`.

Для многостраничного и bulk-сбора добавить backward-compatible typed page iterator. Точная форма
утверждается аудитом, но контракт должен быть эквивалентен:

```python
@dataclass(frozen=True, slots=True)
class ProviderCollectionPage:
    provider_id: str
    items: tuple[UnifiedTender, ...]
    page_number: int
    next_cursor: ProviderCursor | None
    is_last: bool
    artifact_refs: tuple[RawArtifactReference, ...]
    warnings: tuple[str, ...] = ()

class AsyncTenderProvider:
    async def iter_search_pages(
        self,
        query: TenderSearchQuery,
        *,
        resume: ProviderResumeState | None = None,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> AsyncIterator[ProviderCollectionPage]: ...
```

Требования:

- метод имеет default implementation из одной страницы через существующий `search`;
- существующие fake/legacy providers не ломаются;
- `AsyncProviderSearchEngine` остаётся единственным владельцем concurrency/timeout/cancellation;
- provider не создаёт собственный глобальный event loop/thread pool;
- page/item/file limits конечны и задаются проверенным provider contract;
- пустая промежуточная страница не означает конец без явного `is_last`/cursor rule;
- повтор cursor/page обнаруживается и завершает источник безопасной ошибкой;
- cancellation проверяется до запроса, после ответа, между страницами и при streaming parse;
- provider timeout и overall timeout остаются bounded;
- partial pages маркируются честно и не превращают run в `COMPLETED`.

Исправить статус run: ноль успешных источников при наличии failures должен давать `FAILED`; часть
успешных и часть failed — `PARTIAL`; все выбранные успешно обработаны — `COMPLETED`; cancellation и
timeout должны сохранять собственные terminal states.

## 10. Pagination, incremental и checkpoints

Поддержать typed cursor kinds:

- `PAGE_NUMBER`;
- `OPAQUE_TOKEN`;
- `DATE_WINDOW`;
- `UPDATED_SINCE`;
- `FILE_INDEX`;
- `FEED_POSITION`.

Не хранить cursor в `TenderSearchQuery.extra` как невалидируемую строку. Использовать typed internal
resume state и существующий checkpoint repository/migration path.

Правила:

1. Cursor привязан к `provider_id`, версии parser/contract и fingerprint области запроса.
2. Изменение filters/schema/parser не продолжает несовместимый checkpoint молча.
3. Checkpoint не продвигается раньше сохранения raw artifact и принятия страницы.
4. Committed checkpoint продвигается только после успешной persistence страницы/пакета.
5. При падении между fetch и commit страница безопасно переигрывается; dedup остаётся идемпотентным.
6. Для date-window используется overlap window, чтобы не терять записи на границе; дубли удаляются
   canonical chain.
7. Clock/timezone не угадываются. Все внутренние timestamps aware UTC, source timezone сохраняется
   в provenance.
8. Corrupt/future checkpoint quarantined/fail closed; он не удаляется молча.
9. Reset checkpoint — explicit user action с подтверждением и audit record.

Если существующая checkpoint schema достаточна, расширить её versioned payload. Новую таблицу или
второй checkpoint repository создавать только при документированном schema gap.

## 11. Raw artifacts и provenance

Каждый сетевой/file ответ, использованный для построения тендера, должен иметь immutable metadata:

- `provider_id`;
- sanitized request URL без credentials/query secrets;
- request fingerprint;
- `fetched_at` aware UTC;
- HTTP status;
- content type/encoding;
- ETag/Last-Modified, если доступны;
- SHA-256 исходных bytes;
- byte size;
- parser version и provider contract version;
- source timezone;
- storage reference;
- redaction/retention status.

Bytes хранить content-addressed и атомарно, вне SQLite, если аудит подтвердит риск разрастания БД.
SQLite хранит metadata/reference через существующий schema migrator. Не создавать raw storage до
проверки существующего `raw_metadata`/version history и retention requirements.

Обязательны:

- bounded retention и cleanup без удаления tender provenance;
- checksum verification при чтении;
- collision-safe path;
- отсутствие hostname/query/credential утечек в filename;
- безопасное восстановление после interrupted atomic write;
- export/support bundle по умолчанию не включает raw bodies;
- персональные/коммерчески ограниченные raw bodies не сохраняются без разрешения.

## 12. Форматы и parser boundary

Поддержать через общие audited utilities:

- JSON и line-delimited JSON;
- XML/SOAP и RSS/Atom;
- CSV;
- XLSX;
- ZIP/RAR/7z только через существующие safe archive utilities;
- HTML только для публичной стабильной страницы, если это разрешено;
- large/bulk files со streaming parse;
- file import для пользовательской выгрузки.

Parser площадки:

- не выполняет сеть;
- принимает bytes/stream + typed metadata;
- возвращает provider DTO или `UnifiedTender` через единственный mapping owner;
- не пишет в БД;
- не рассчитывает score/recommendation;
- выдаёт bounded sanitized diagnostics;
- не подставляет отсутствующие значения;
- отвергает/маркирует naive datetime, ambiguous money/currency и malformed identity;
- сохраняет неизвестные source fields только в bounded provenance/raw metadata.

Для больших XML использовать incremental parse и освобождение элементов. Для больших JSON сначала
провести dependency audit streaming parser; новая dependency допускается только при наличии Windows
wheels для Python 3.12/3.13, pin/range в `pyproject.toml`, успешном `pip-audit` и доказанном выигрыше.

## 13. HTTP, rate limits и retries

Все нативные adapters используют только `CollectorNetworkRuntime`/`AsyncHttpClient` и общий rate
limiter. Прямой `httpx.AsyncClient`, `requests`, Selenium/Playwright или browser extension внутри
adapter запрещены.

Требования:

- TLS verification включена;
- redirects bounded и проверяют allowlisted destination host;
- SSRF/private-network access запрещён, кроме явно разрешённого enterprise endpoint;
- auth headers/query redacted до logs/errors/artifacts;
- retries только для идемпотентных операций и разрешённых status/transport failures;
- `429` и `Retry-After` соблюдаются;
- exponential backoff имеет bounded jitter и maximum;
- rate limit per provider/domain, а не общий бесконтрольный sleep;
- response size и decompression ratio bounded;
- Content-Type не считается достаточным: используется safe format validation;
- login HTML вместо API payload классифицируется как auth/contract error;
- startup/composition/offline test не выполняет сеть.

Browser-assisted режим не входит в первый implementation path. Он допускается отдельным аудитом
только при явном пользовательском запуске, разрешённых условиях площадки и без CAPTCHA/anti-bot
bypass, cookie theft, fingerprint spoofing или фонового сохранения сессии.

## 14. Документы тендера

Переиспользовать существующие safe download/extraction paths.

- Search получает только metadata и ссылки, если contract не требует иного.
- `list_documents` возвращает стабильные IDs, имя, URL, MIME, size, published time, checksum при
  наличии.
- Download выполняется лениво и явно либо по разрешённому schedule.
- Filename sanitization, traversal protection, archive bomb limits, nested archive limits и MIME
  verification обязательны.
- Поддерживаемые parser paths PDF/DOCX/XLSX/ZIP не дублируются в provider package.
- Защищённые/подписанные документы сохраняют оригинал и provenance; невозможность чтения не
  превращается в пустой подтверждённый текст.
- OCR не добавляется этим prerequisite без отдельного scope/dependency audit.

## 15. Нормализация, identity и dedup

Обязательные инварианты:

- `identity_key = provider/source + stable external_id` сохраняется;
- procurement number нормализуется без удаления значимых leading zeros;
- cross-source merge использует номер, закон, заказчика и доказательства, а не только fuzzy title;
- отсутствие procurement number у коммерческого tender не выдумывается; используется source-local
  identity, а cross-source статус остаётся неподтверждённым;
- одинаковая закупка с ЕИС и operator source сохраняет обе observations и field candidates;
- `Decimal` остаётся finite/non-negative и не преобразуется во float;
- currency explicit; неизвестная currency не становится RUB;
- timestamps aware; timezone source-specific и фиксируется в provider contract;
- status/procedure/law/classification используют versioned mapping tables;
- parser version change создаёт новую observation/version, но не новый canonical tender без причины;
- результат не зависит от порядка завершения concurrent providers.

Добавить property/golden tests на permutation invariance и repeated replay idempotence.

## 16. Структура provider package

Рекомендуемая структура нового нативного источника:

```text
app/tenders/providers/<provider_id>/
  __init__.py
  adapter.py       # AsyncTenderProvider, без parser business logic
  client.py        # provider-specific request construction над shared HTTP port
  contract.py      # typed endpoints/capabilities/pagination/rate policy
  dto.py           # source response DTO
  parser.py        # pure parsing
  mapping.py       # DTO -> UnifiedTender
  diagnostics.py   # sanitized provider errors/status mapping
```

Это не обязательное механическое разбиение: перед созданием файлов проверить существующий код и не
создавать пустые слои. ЕИС сохраняет существующий `eis_parser` owner; его нельзя переписать ради
единообразия. Общая логика выносится только после появления минимум двух реальных consumers и
characterization tests.

## 17. Настройки и credentials

Переиспользовать `CollectorProviderManager`, provider settings schema и `app.security.secrets`.

Для каждого built-in provider:

- `enabled` default определяется descriptor и безопасной policy;
- public источники могут быть включены по умолчанию только после live verification;
- коммерческие/credential sources disabled по умолчанию;
- endpoint задаётся только для enterprise/custom override, официальный built-in endpoint идёт из
  audited contract;
- API key/token/password сохраняется только в keyring или explicit environment override;
- UI показывает только `configured/not configured`, но не masked secret value;
- replacement/delete secret — explicit operations;
- settings/export/log/support bundle не содержит secret, auth header, cookie или credential query;
- corrupt/future settings fail closed и не запускают сеть.

## 18. Observability и UI

Расширить существующие progress/health/source-monitoring contracts, не создавать новый monitor.

На provider и run уровне доступны:

- состояние readiness и причина;
- connection/operational/freshness/circuit status;
- parser/contract version;
- last attempt/last success aware timestamps;
- latency, pages, items, bytes, retries, rate-limit waits;
- checkpoint age и safe cursor kind без raw token;
- raw artifact count/retention state;
- item counts: fetched, parsed, rejected, discovery-only, normalized, merged, persisted;
- sanitized last error category/code;
- explicit `sample`, `diagnostic` и `production` run mode.

UI не показывает `working`, если источник только настроен. Health check — explicit user action или
включённое расписание. Никакой live network при открытии страницы, старте приложения или построении
DI.

## 19. Обязательные исправления действующего Collector

До добавления третьего рабочего источника закрыть следующие contracts:

1. Discovery classification выполняется до canonical deduplication и persistence.
2. `FAILED/PARTIAL/COMPLETED/CANCELLED/TIMED_OUT` согласованы между engine, service и run history.
3. Bulk pagination не ограничивается одной страницей и не теряет `next_page_token`.
4. Checkpoint имеет commit/replay semantics и query/contract fingerprint.
5. Partial/cancelled result сохраняет только полностью принятые страницы с честным status.
6. Один provider failure не отменяет остальных, но zero-success run не становится partial success.
7. Duplicate provider/source identities отвергаются во всех factories/catalogs/manual registrations.
8. Provider warnings/errors проходят единый bounded redaction.
9. Source priority/trust/freshness policy детерминирована и покрыта permutation tests.
10. Search/detail/documents capability mismatch возвращает typed `UNSUPPORTED`, а не generic failure.
11. Cursor loop, page loop и unlimited file list имеют guards.
12. Shutdown отменяет page iterator, transport и progress delivery без late signals/tasks.

Каждое исправление сначала получает characterization и expected-red test.

## 20. Реализация по пакетам

Работы идут последовательно; один package/branch/PR не смешивается с другим.

### P0 — governance docs-only

- обновить canonical status/roadmap/history;
- зафиксировать owner decision и rollback;
- не менять application-код.

### P1 — audit-first Collector baseline

- inventory engine/service/providers/factories/catalogs/settings/checkpoints/DB/UI/scheduler;
- зафиксировать runtime ownership и duplicate map;
- проверить текущие migrations и production composition;
- записать access/readiness matrix всех площадок;
- измерить offline baseline и текущий full test result;
- создать contract, implementation plan и rollback plan до кода.

### P2 — expected-red correctness contracts

- discovery-before-dedup;
- honest run terminal status;
- pagination/cursor loop;
- checkpoint replay/commit;
- cancellation between pages;
- deterministic ordering/dedup;
- secret/error redaction.

### P3 — shared page/artifact/checkpoint foundation

- backward-compatible page iterator;
- engine integration без второго engine;
- raw artifact metadata/store после schema audit;
- typed resume/checkpoint;
- progress/stats;
- versioned DB migration/backup/rollback при необходимости.

### P4 — ремонт и эталонные adapters

1. `eis` — public/reference adapter.
2. `mos_supplier` — credential/reference adapter.

Они обязаны пройти новый общий contract и стать эталонами для public и authenticated sources.

### P5 — identity/catalog expansion

- добавить недостающие `zakaz_rf`, `rad`, `ets_nep` identities;
- устранить расхождения sync/async/commercial/manual catalogs;
- выполнить settings/DB/export migration;
- все новые источники остаются disabled/not configured до своего PR.

### P6 — федеральные operator adapters

Отдельный audit/fixture/implementation/live-verification PR на каждый источник:

1. `zakaz_rf`;
2. `roseltorg`;
3. `rad`;
4. `tek_torg`;
5. `ets_nep`;
6. `sber_a`;
7. `rts_tender`;
8. `gazprombank`.

Порядок может измениться только docs-only решением по фактической доступности официальных
контрактов. Нельзя реализовывать guessed endpoints ради соблюдения порядка.

### P7 — коммерческие adapters

Отдельный PR на каждый разрешённый source:

1. `b2b_center`;
2. `fabrikant`;
3. `otc`;
4. коммерческие sections федеральных операторов внутри их existing owner.

### P8 — aggregator discovery

- optional `tenderguru_discovery` только при разрешённом API/data access;
- output исключительно в существующую official verification queue;
- отрицательные тесты против попадания в decision path.

### P9 — stabilization и prerequisite closeout

- all-provider offline `checkall`/sample diagnostics;
- performance/resource/cancellation/shutdown runs;
- migration/backup/restore;
- Windows Python 3.12/3.13 Quality Gate;
- honest matrix `WORKING/BLOCKED_EXTERNAL/DISABLED`;
- docs/operations/support/rollback;
- отдельный canonical closeout и возврат к RM-156.

## 21. Definition of Ready для каждого adapter PR

Код площадки нельзя начинать, пока нет:

- подтверждённой provider identity;
- разрешённого access method;
- безопасной документации контракта;
- hostname allowlist;
- auth/rate/pagination/timezone/currency rules;
- минимум одного обезличенного positive fixture;
- fixtures empty/pagination/error/auth/rate-limit/schema-drift;
- field mapping и trust level;
- expected-red contract tests;
- решения по raw retention;
- rollback/disable plan.

Если любого обязательного пункта нет, Codex оформляет `BLOCKED_EXTERNAL` evidence и не угадывает
реализацию.

## 22. Обязательные тесты каждого provider

### Unit

- descriptor/identity/capabilities;
- configuration validation;
- request construction без secret leakage;
- parsing каждого fixture/schema variant;
- mapping money/currency/timezone/status/procedure/law/customer/documents;
- empty/missing/null/malformed/unknown fields;
- pagination/cursor/date-window;
- duplicate/replayed page;
- 401/403/404/409/429/5xx and transport failures;
- response size/content-type/encoding;
- sanitized error/warnings;
- cancellation.

### Contract

Один parametrized suite должен запускаться для всех working adapters:

- `search`;
- `iter_search_pages`;
- `get_tender`;
- `list_documents`;
- `check_health`;
- no-network construction;
- deterministic result;
- aware time/Decimal/provenance;
- finite page/item bounds;
- configuration/health honesty.

### Integration offline

- fake shared transport;
- multi-provider partial failure;
- engine concurrency/order;
- discovery isolation;
- normalization/dedup/verification/persistence;
- checkpoint replay after simulated crash;
- DB migration/backup/restore;
- scheduler/manual mutual exclusion;
- shutdown during DNS/connect/body/parse/page transition/save/progress callback.

### Live diagnostics

- никогда не запускаются в обычном pytest/CI;
- только explicit command/action;
- требуют opt-in и credentials из keyring/environment;
- выводят sanitized metadata, schema fingerprint и counts;
- не печатают body, token, cookie, auth header или private URL query;
- сохраняют fixture только после отдельной redaction/approval операции;
- live success сам по себе не переводит provider в `WORKING` без offline contract acceptance.

## 23. Security и legal negative requirements

Запрещено:

- обходить CAPTCHA, anti-bot, Cloudflare или ограничения доступа;
- использовать украденные cookies/browser profile;
- угадывать закрытые endpoints или reverse-engineer private protocol без разрешения;
- скрывать/подменять User-Agent вопреки требованиям площадки;
- игнорировать robots/ToS/data license;
- хранить secrets в Git, JSON, SQLite, fixtures, logs, traces, crash/support bundle;
- отключать TLS verification;
- выполнять произвольный Python/JS из custom adapter;
- разрешать custom URL обращаться к localhost/link-local/private metadata без allowlist;
- считать агрегатор official source;
- передавать raw tender/customer data внешнему AI в рамках Collector;
- позволять AI менять выбранное поле, score, recommendation или critical stop-factor.

## 24. Performance и resource acceptance

До оптимизации зафиксировать baseline на актуальном `origin/main`. После изменений:

- не ухудшить существующий 10,000-record exact-data contract;
- concurrency bounded глобально и per domain;
- ни один adapter не загружает неограниченный response/archive целиком в память;
- pagination имеет explicit maximum pages/items/time для interactive run;
- scheduled bulk run использует streaming/chunked persistence;
- progress queue остаётся bounded;
- repeated 25-cycle run/close не оставляет tasks, threads, timers, file handles или temp files;
- cancellation/shutdown завершается в измеренном bounded budget;
- performance report содержит p50/p95, peak memory, bytes/pages/items и baseline delta;
- sampling не используется для доказательства полноты production result.

Точные числовые budgets утверждаются в P1 после baseline и фиксируются до implementation P3.

## 25. Database и migration

Любое изменение schema:

1. Идёт через `CollectorSchemaMigrator` с новой последовательной версией.
2. Имеет old/current/future/corrupt tests.
3. Имеет dry-run/inventory, backup и rollback evidence.
4. Не выполняется обычным read path.
5. Использует transaction/atomic replace и readback verification.
6. Сохраняет существующие tender IDs, aliases, versions, conflicts, resolutions, scores и run history.
7. Не преобразует `Decimal` во float и aware datetime в naive.
8. Не удаляет старые provider IDs без compatibility mapping.

Новая БД запрещена. Raw bytes могут храниться отдельно только как scoped content-addressed artifact
store с metadata в существующей collector DB и lifecycle ownership у Collector.

## 26. Точные команды локальной и CI-приёмки

Команды уточнить по актуальному `origin/main`, `pyproject.toml` и
`.github/workflows/quality-gate.yml`. Минимальный обязательный набор:

```powershell
python scripts/check_repository_secrets.py
python -m ruff check .
python -m ruff format . --check
python -m mypy
python -m pytest -q <focused provider/collector tests>
python -m pytest -q tests/test_collector_provider_control.py::test_manager_exposes_all_sources_without_network tests/test_mos_supplier_diagnostic_script.py::test_mos_diagnostic_runs_from_scripts_path_without_app_error
python -m pytest -q tests/test_database_migrations_121.py tests/test_collector_schema_contract.py
python -m pytest -q tests/test_bootstrap_tender_search_integration.py
python -m pytest -q tests/test_build_release_contract.py tests/test_frozen_self_test.py
python scripts/check_rm155_compatibility.py
python -m pytest -q
python -m pip_audit --skip-editable
git diff --check
```

Если prerequisite меняет required mypy contour, это фиксируется в `pyproject.toml` и проходит на
Python 3.12/3.13. Финальный PR и exact merge SHA должны иметь успешный Windows Quality Gate.

## 27. Общий Definition of Done prerequisite

Prerequisite завершён только когда:

- canonical docs законно переведены в prerequisite и затем закрыты отдельным closeout;
- P1 audit, contract, plan и expected-red зафиксированы до application changes;
- нет второго engine/catalog/factory/settings/credential/health/checkpoint owner;
- обязательные исправления раздела 19 закрыты;
- ЕИС и Портал поставщиков проходят новый общий adapter contract;
- все 13 built-in sources присутствуют с уникальной identity и честным readiness;
- каждый `WORKING` provider имеет access evidence, real redacted fixtures, offline tests и live
  verification;
- каждый недоступный provider честно `BLOCKED_EXTERNAL`, а не placeholder success;
- все working adapters поддерживают bounded pagination/cancellation/checkpoints/provenance;
- агрегаторы доказуемо discovery-only;
- schema migrations/backups/rollback проверены;
- secrets/access restrictions соблюдены;
- focused, full, Ruff, format, mypy, secret scan, pip-audit, build/frozen/offline/Windows gates прошли;
- exact результаты, commit/PR/run IDs записаны в roadmap docs;
- feature PR слит и exact merge-SHA Quality Gate успешен;
- после closeout RM-156 снова назначен текущим production action.

Важно: наличие `BLOCKED_EXTERNAL` означает, что техническая основа и catalog могут быть приняты, но
утверждение «адаптеры всех площадок работают» запрещено. Для буквального завершения требования
«все работают» нужны договоры/ключи/документация от всех соответствующих операторов. Владелец должен
отдельно решить, блокирует ли отсутствие внешнего доступа весь prerequisite или принимается как
документированный внешний blocker.

## 28. Rollback

Rollback выполняется по package границам:

- provider отключается через existing manager без удаления данных;
- adapter feature merge может быть reverted независимо;
- parser/contract version возвращается вместе;
- checkpoint несовместимой версии не используется старым кодом и сохраняется для диагностики;
- schema downgrade не выполняется автоматически; используется проверенный backup/forward-compatible
  read path;
- новые source IDs не переиспользуются для другой площадки;
- raw artifacts удаляются только retention procedure, не rollback-командой;
- RM-107 decision data и пользовательские settings/profiles не откатываются/не стираются.

## 29. Инструкция Codex на первый запуск

Codex должен выполнить только следующие действия, пока P0 не слит:

1. Проверить `git status`, текущую ветку и актуальность `origin/main`.
2. Не трогать dirty working tree владельца.
3. Создать чистый worktree/branch `codex/pre-rm156-collector-governance` от актуального
   `origin/main`.
4. Перечитать `AGENTS.md`, `docs/STATUS.md`, `docs/ROADMAP.md`,
   `docs/DEFINITION_OF_DONE.md`, `docs/ROADMAP_HISTORY.md`.
5. Подготовить только P0 docs-only diff и показать его владельцу/PR.
6. Не начинать application-код до merge P0.
7. После P0 создать отдельную audit branch/worktree, выполнить P1 и зафиксировать audit/contract/
   plan отдельными commits до expected-red и implementation.
8. Для каждого provider использовать отдельный последовательно выполняемый work package/PR.

Codex не должен трактовать это ТЗ как разрешение на network scraping, регистрацию аккаунтов,
заключение договоров, получение платных API, обход защит или загрузку закрытой документации. Такие
действия требуют внешней координации владельца.

## 30. Итоговое решение

Действующий Collector **дополняется и исправляется**, а не заменяется. Kingfisher Collect служит
проверенной архитектурной основой для source adapters, incremental/date-window collection, formats,
artifacts и diagnostics. Corteris сохраняет собственные async engine, DI, repositories,
normalization, verification, deterministic decision и Windows desktop constraints.
