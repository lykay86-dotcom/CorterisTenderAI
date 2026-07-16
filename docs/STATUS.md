# Текущее состояние CorterisTenderAI

Обновлено: 16 июля 2026 года.

## Активный этап

**RM-127 — новая структура вкладок**

Статус: `IN PROGRESS`

RM-126 и технический подэтап RM-126.1 завершены после feature merge и успешного post-merge Windows
Quality Gate. RM-127 назначен единственным активным этапом; RM-128–RM-200 остаются `PLANNED` и не
выполняются параллельно.

## Завершённый этап

**RM-126 — аудит раздела Тендеры и укрепление провайдера ЕИС**

Статус: `DONE`

Подтверждение:

- общий audit PR #55 слит коммитом `f09d07e`; его post-merge Quality Gate run `29453928900`
  успешен на Python 3.12/3.13;
- позднее дополнение RM-126.1 было явно активировано владельцем проекта отдельным docs PR #57;
- EIS audit и архитектурный план зафиксированы commit `955ec6a` до изменения application-кода;
- `AsyncEisTenderProvider` сохранён в единой Collector/DI цепочке; второй Collector, HTTP client,
  tender model, persistence root, DB schema, migration, scoring или analysis workflow не добавлены;
- `get_tender()` теперь открывает detail-page через общий `AsyncHttpClient`, детерминированно разделяет
  44-ФЗ и 223-ФЗ, строго валидирует обязательные поля и объединяет факты с search card;
- добавлены `EisLawType`, versioned parsers, diagnostics, structural fail-closed policy, URL allowlist,
  отдельные network/parser health, opt-in sanitized snapshots и read-only live canary;
- `Decimal`, aware UTC+03:00 datetime, ИНН, КПП, `organizationCode`, provenance и JSON persistence
  проверены offline tests; старые public imports и `ProviderDescriptor.id = "eis"` сохранены;
- локальный EIS/Collector target: `69 passed in 6.35s`; полный pytest: `1524 passed in 54.24s`;
- feature PR #58 слит в `main` коммитом `b6369c8`
  (`b6369c85791b9c06a97f03a1fbb2504c88a1dea7`);
- post-merge Quality Gate run `29460395144` успешен: Python 3.12 —
  `1524 passed in 95.38s`, Python 3.13 — `1524 passed in 71.31s`;
- на обеих версиях прошли repository secret scan, Ruff check/format (`537 files`), mypy (20 файлов),
  offline/migration/import/composition/build smoke tests и dependency audit;
- live ЕИС автоматически не вызывалась: canary создан, его `--help` smoke успешен, сам сетевой запуск
  остаётся явной operator action и не входит в offline CI.

## Ранее завершённый этап

**RM-125 — стабилизация AI-платформы**

Статус: `DONE`

Подтверждение:

- feature PR #53 слит в `main` коммитом `bdceb70`;
- post-merge Quality Gate run `29450245855` успешен на Python 3.12 и 3.13;
- полный Windows suite: Python 3.12 — `1496 passed in 95.46s`, Python 3.13 —
  `1496 passed in 61.69s`;
- immutable AI execution contract, deterministic decision и critical stop-factor priority сохранены.

## Текущее действие

Начать RM-127 с обязательного аудита текущей структуры вкладок и сверки handoff D-01/C1–C20 из
`docs/RM-126_AUDIT.md` и `docs/RM-126_REQUIREMENTS.md`. Production-код RM-127 не менять до
фиксации аудита и отдельного плана реализации.
