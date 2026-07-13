# RM-110 follow-up — аудит стабилизации Collector C1–C20

Дата: 13 июля 2026 года.

Основание: внешний статический аудит
`CORTERIS_COLLECTOR_C1_C20_AUDIT_RM110.md`, выполненный для устаревшего HEAD
`6573355`. Повторная проверка проведена на `main` после merge PR #19, HEAD
`fdd57b1`.

## Граница follow-up

RM-110 остаётся завершённым, RM-111 остаётся активным по дорожной карте. Эта
ветка является корректирующим follow-up к найденным дефектам Collector и не
реализует AI Orchestrator или функции RM-112+.

Не создаются второй Decision Engine, ranker, коммерческий расчёт, provenance,
freshness или миграционный механизм. Исправляются существующие контракты.

## Устаревшие выводы внешнего аудита

- RM-110 уже `DONE`, а RM-111 назначен активным.
- Полный регресс воспроизведён локально: `701 passed`.
- `python -m ruff check .` и `ruff format . --check` проходят.
- STATUS и рабочая ветка обновлены.

## Подтверждённые дефекты

### P0-01 — Decimal serialization

`app/database/base.py::json_safe` преобразует `Decimal` во `float`.
`ImportService.create_tender` принимает `nmck: float`. Это нарушает единый
денежный контракт и может терять точность.

Исправление: JSON-граница хранит Decimal строкой; legacy API принимает
`Decimal | str | int | float`, а float нормализуется только через
`Decimal(str(value))` существующим денежным normalizer.

### P0-02 — timezone boundary

`UnifiedTender` и `TenderDocument` принимают naive datetime. StopFactorEngine
вызывает `astimezone(UTC)` напрямую, а deduplicator выполняет `min/max` над
смешанными datetime. Возможны локальная интерпретация неизвестной зоны,
ошибочная блокировка и `TypeError`.

Исправление: модельная граница запрещает naive datetime для подтверждённых
моментов; codec сохраняет offset; stop-factor для неизвестной зоны возвращает
DATA_INSUFFICIENT; deduplicator сравнивает только aware значения и не
выдумывает timezone.

### P0-03 — C19 live acceptance

Gate реализован корректно, но репозиторий явно фиксирует, что ни одному
источнику C19 статус `WORKING` не присвоен. Offline fixture не заменяет
разрешённый live-smoke.

В этом follow-up статус не подделывается. Для закрытия C19 отдельно необходим
фактический Windows/live артефакт search → card → documents → provenance →
verification → DB → UI → full analysis без сохранения токена.

### P0-04 — C20 identity matching

`AggregatorDiscoveryRepository.resolve` проверяет только тип официального
источника. Любой EIS/MOS tender, возвращённый callback, может стать
`OFFICIAL_MATCH_FOUND` без совпадения с discovery record.

Исправление: сильный procurement number обязателен при его наличии. Без него
используется консервативный multi-field matcher с customer INN, нормализованным
названием, точной ценой и deadline. Конфликт блокирует автоматическое
разрешение; слабое совпадение остаётся на ручной проверке. История попыток
сохраняется append-only.

## Подтверждённые P1

1. `_SOURCE_PRIORITY` не содержит `MOS_SUPPLIER`; verification и deduplicator
   используют разные представления доверия.
2. Центральный `CollectorSchemaMigrator` и repositories параллельно владеют
   DDL C17–C20.
3. `canonical_term` каталога C17 сохраняется, но не участвует в формировании
   search profile.

В follow-up вводится один source trust contract и переиспользуется в
deduplicator. Для DDL сначала устраняется реальный drift и добавляется guard
версии; полное переписывание миграций 1→13 без production fixtures не
выполняется. C17 canonicalization относится к отдельному бизнес-требованию и
не смешивается с P0 исправлениями.

## Acceptance

- Decimal round-trip не использует float;
- naive/aware даты не вызывают падение и не создают ложный stop-factor;
- C20 отвергает несвязанный официальный tender;
- официальный number match подтверждается;
- конфликт полей не разрешается автоматически;
- history повторных C20 проверок сохраняется;
- Moscow official source имеет приоритет над custom/commercial;
- C19 остаётся UNVERIFIED без реального live-smoke;
- полный pytest, Ruff и format check проходят.

## Итог follow-up

Локально завершены и покрыты регрессией:

- P0-01: денежные значения проходят JSON/API-границы без преобразования `Decimal` во
  `float`;
- P0-02: неизвестный часовой пояс не локализуется автоматически, mixed naive/aware
  значения не приводят к `TypeError`, а stop-factor возвращает `DATA_INSUFFICIENT`;
- P0-04: C20 использует консервативный identity matcher и сохраняет неизменяемую
  историю успешных, отклонённых и неуспешных попыток проверки;
- P1 source trust: deduplicator и verification используют единый `SourceTrustLevel`,
  включая `MOS_SUPPLIER`;
- P1 DDL: collector-таблицы создаёт только `CollectorSchemaMigrator`, добавлен guard
  против понижения более новой версии БД; версия схемы повышена до 14.

Фактическая финальная проверка ветки:

- `721 passed`;
- `python -m ruff check .` — успешно;
- `python -m ruff format . --check` — успешно, 490 файлов отформатированы.

Не подменяются локальной реализацией:

- C19 остаётся `UNVERIFIED`, пока не выполнен реальный разрешённый live-smoke с
  сохранённым артефактом и без публикации токена;
- применение `canonical_term` C17 к поисковой канонизации требует отдельного
  бизнес-решения и не входит в исправление подтверждённых P0-дефектов.
