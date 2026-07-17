# RM-137 — аудит канонической нормализации тендеров

Дата аудита: 17 июля 2026 года.  Baseline:
`cf60941a94bc4023edfa73cba65885f9c6b16b8c` (`origin/main`).

Окружение: Microsoft Windows 10.0.19045 x64, Python 3.12.7, timezone
`Russian Standard Time` (UTC+03:00). Полный baseline:
`1859 passed, 2 warnings in 127.69s`. Из-за закрытого пользовательского `%TEMP%`
pytest запускался с workspace-local `--basetemp`; отдельный `-x -vv` подтвердил, что
первый прогон падал только на `PermissionError` test harness, а не на коде проекта.

## Entry gate

| Проверка | Доказательство |
|---|---|
| Актуальный `origin/main` | `cf60941a94bc4023edfa73cba65885f9c6b16b8c` |
| RM-136 feature | PR #78, merge `d84288ab74553e500ad9eaf9f51a091404490551` |
| RM-136 exact-SHA gate | run `29606492310`, `success`, Python 3.12 и 3.13 |
| RM-136 closeout | PR #79, merge `2a8514df70c4f6f8d856d07f5a2d367e30d60189` |
| Roadmap/status | RM-136 `DONE`, только RM-137 `IN PROGRESS`, RM-138–RM-200 `PLANNED` |
| Рабочее дерево | отдельный чистый worktree на feature-ветке |
| Baseline tests | `1859 passed, 2 warnings in 127.69s` |

После closeout RM-136 в `main` также вошёл PR #80 (`cf60941`), который меняет только
детерминированность существующего CI-теста поиска. Поэтому именно `cf60941`, а не SHA из
подготовленного ТЗ, является baseline RM-137.

## Фактические владельцы

| Область | Владелец до RM-137 | Решение |
|---|---|---|
| Публичная доменная модель | `app/tenders/models.py::UnifiedTender` | reuse; второй root type запрещён |
| Collector normalization/dedup input | `app/tenders/collector/normalizer.py::TenderNormalizer` и `NormalizedTender` | extend; единственный canonical boundary |
| Stable JSON/hash | `app/tenders/collector/codec.py` | reuse; version включить в semantic payload |
| Collector persistence | `CollectorStateRepository`, `COLLECTOR_SCHEMA_VERSION = 14` | reuse; без новой таблицы/миграции |
| Registry persistence | `TenderRegistryRepository`, schema version 1 | сохранить чтение legacy payload |
| Identity/dedup | `TenderNormalizer`, `TenderDeduplicator`, `tender_registry_key` | не создавать второй fingerprint/registry key |
| Field verification/provenance | `app/tenders/collector/verification.py` | не подменять; normalization provenance предшествует verification |
| Manual source mapping | `manual_adapter.py` spec v1, `MappingProvenance` | route offline preview через общий boundary; admission не менять |
| RM-107 decision | participation score/decision и stop-factor owners | не менять код или семантику |

## Текущая цепочка и обходы

Основной Collector уже выполняет
`provider -> UnifiedTender -> TenderNormalizer -> TenderDeduplicator -> verification ->
persistence`. `CollectorService` передаёт один экземпляр `TenderNormalizer` также в
deduplicator и verification, что является правильной DI-точкой.

Обходы и несовпадения:

1. EIS и Moscow Supplier создают `UnifiedTender` внутри provider-specific parser и выполняют
   собственные money/date/status/law mappings до общего normalizer.
2. `TenderNormalizer` сейчас нормализует только comparison-поля и hashes; исходный
   `UnifiedTender` остаётся нетронутым, contract version/typed diagnostics отсутствуют.
3. Legacy `TenderSearchEngine` дедуплицирует и объединяет `UnifiedTender` напрямую. Этот
   существующий путь сохраняется, но его provider output должен проходить тот же pure boundary.
4. `tender_registry.py` содержит исторический параллельный payload codec без `schema_version`;
   Collector codec уже имеет payload schema v1. Оба readers обязаны продолжать читать legacy.
5. Manual API/RSS/FTP/FTPS spec v1 даёт bounded offline `ManualAdapterPreviewRecord` и
   provenance, но compiled providers намеренно остаются non-runnable до admission. Preview ещё
   не создаёт canonical `UnifiedTender` и не вызывает `TenderNormalizer`.
6. `TenderMoney.from_value` исторически принимает `float`; provider parsers в production
   используют `Decimal`, но публичный float input противоречит новому strict contract.
7. `UnifiedTender` допускает naive datetimes; Collector freshness позднее помечает неизвестную
   timezone, но canonical normalization должна fail-closed убрать naive значение.
8. EIS price parser подставляет RUB даже когда currency marker не найден, а Moscow parser
   локализует naive/API date-only значения в UTC. Эти guesses должны стать явными diagnostics
   или быть оставлены missing на common boundary.
9. Status parsers используют широкие substring rules; common boundary не должен угадывать
   новый status и принимает только уже typed `TenderStatus`.

## Provider matrix

| Family | Текущий output | Текущий mapping | Действие RM-137 |
|---|---|---|---|
| ЕИС public HTML | `UnifiedTender` | `EisHtmlParser`, detail parsers; aware MSK dates | route/reuse, common validation |
| Moscow official API | `UnifiedTender` | `MosSupplierApiParser`; Decimal/date/status helpers | route/reuse, запрет silent timezone/currency guess |
| Commercial built-ins | descriptor-only, non-runnable | данных нет | сохранить fail-closed; contract tests без выдуманного parser |
| Manual API | spec v1 preview, non-runnable live | declarative mappings/transforms | preview-to-common boundary, admission unchanged |
| Manual RSS | то же | XML/RSS parser preview | то же |
| Manual FTP | то же | JSON/XML/CSV preview | то же |
| Manual FTPS | то же | JSON/XML/CSV preview | то же |

## Compatibility matrix

| Consumer | Поля/контракт | Риск и защита |
|---|---|---|
| Collector persistence | canonical key, aliases, content hash, tender payload | HIGH: старые payload v1 читать без rewrite; schema 14 не менять |
| Registry | procurement identity, flattened columns, legacy JSON | HIGH: не менять registry key и schema v1 |
| Dedup/history | aliases, `content_hash`, `duplicate_hash` | HIGH: versioned semantic hash меняется один раз предсказуемо |
| Verification | normalized field candidates, source metadata | HIGH: не повышать trust/verified |
| Freshness/UI/export | tender dates/money/status | MEDIUM: invalid optional становится missing + diagnostic |
| RM-107 | verified facts, score, recommendation, critical stop-factor | CRITICAL: unchanged valid fixtures должны дать byte/value-equivalent decision |
| AI context | `UnifiedTender` и verified evidence | CRITICAL: diagnostics не становятся фактом |

## Версии и legacy payloads

- `UnifiedTender` не имеет отдельной schema version.
- Collector tender JSON: `schema_version = 1`.
- Collector SQLite: version 14.
- Tender registry SQLite: version 1; его embedded tender JSON не имеет version.
- Manual adapter spec: version 1.
- Provider settings: version 6; manual health evidence: version 2.

Читаемость сохраняется для Collector payload v1, unversioned registry payload, persisted naive
legacy datetime и numeric/string money. RM-137 не выполняет destructive rewrite, не повышает
SQLite schema и не создаёт backup, потому что записи обновляются только обычным существующим
ingestion path.

## Reuse / extend / consolidate

- `UnifiedTender`: **reuse**, минимальные invariant helpers без нового типа.
- `TenderNormalizer`/`NormalizedTender`: **extend** typed result metadata, diagnostics,
  provenance и versioned semantic fingerprint.
- Provider parsers: **consolidate policy**, но сохранить source parsing и explicit mapping.
- Codec/hash: **reuse**, удалить дублирование только там, где это не ломает legacy reader.
- Verification provenance: **reuse downstream**, normalization provenance не выдаёт verified.
- Persistence/dedup/search: **reuse**, новая БД/repository/engine не нужны.

## Риски и stop conditions

Главные риски: изменение content hash создаёт новую версию наблюдения; исторические naive
datetime/float payloads; raw API records в `raw_metadata`; provider-specific currency/timezone
guesses; duplicate registry codec; manual provider lifecycle. Реализация останавливается, если
для совместимости потребуется новая таблица, ослабление RM-136 security/admission, изменение
RM-107 или новый provider/search pipeline.

Открытый вопрос для acceptance: production commercial/manual providers честно non-runnable;
поэтому parity доказывается offline contract fixtures и тем, что общий boundary подключён до
persistence, а не фиктивным live результатом.
