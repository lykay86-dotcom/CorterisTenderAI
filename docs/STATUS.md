# Текущее состояние CorterisTenderAI

Обновлено: 17 июля 2026 года.

## Активный этап

**RM-138 — параллельный поиск**

Статус: `IN PROGRESS`

RM-137 завершён после audit-first реализации, feature merge и успешного exact
merge-SHA Windows Quality Gate. RM-138 — единственный активный этап;
RM-139–RM-200 остаются `PLANNED` и не выполняются параллельно.

## Завершённый этап

**RM-137 — отраслево-независимая нормализация**

Статус: `DONE`

Подтверждение:

- audit/plan зафиксированы commit `32a1257`, expected-red contract — `209acd7`;
- existing `UnifiedTender`, `TenderNormalizer`, Collector/repository/dedup/verification и DI paths
  переиспользованы; новый model/repository/DB/search engine не добавлялся;
- pure versioned normalization contract v1 нормализует text/IDs/money/aware UTC dates/URLs/
  collections, выдаёт bounded diagnostics, safe provenance и semantic fingerprint;
- Collector, legacy provider-result path и offline manual mappings проходят через один normalizer;
  live manual/commercial admission остаётся fail-closed;
- Collector schema 14, Registry schema 1 и legacy payload readers сохранены без migration;
- RM-107 score/recommendation/hard-exclusion и critical stop-factor priority неизменны;
- локально: focused `20 passed`, full pytest `1879 passed, 2 warnings`; secret scan,
  Ruff/format, mypy, workflow smokes, dependency audit и diff-check успешны;
- feature PR #81 слит в `main` merge commit
  `e38c8c13f0ec822fde76bdbc6319a18a05fd500b`;
- PR Quality Gate run `29614656151` успешен: Python 3.12 —
  `1879 passed, 2 warnings in 147.32s`, Python 3.13 —
  `1879 passed, 2 warnings in 96.35s`;
- exact merge-SHA run `29615080804` успешен: Python 3.12 —
  `1879 passed, 2 warnings in 105.98s`, Python 3.13 —
  `1879 passed, 2 warnings in 94.45s`; все обязательные jobs завершились `success`.

## Ранее завершённый этап

**RM-136 — тест подключения**

Статус: `DONE`

- Feature PR #78 слит в `main` коммитом `d84288a`.
- Exact merge-SHA Quality Gate run `29606492310` успешен на Python 3.12/3.13.
- Manual-provider health/admission и deterministic boundaries сохранены.

## Текущее действие

Начать RM-138 с отдельного audit-first пакета и канонического entry gate.
Не начинать RM-139+ и не изменять deterministic decision/scoring/critical stop-factor priority
до отдельно утверждённого parallel-search contract.
