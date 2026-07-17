# Текущее состояние CorterisTenderAI

Обновлено: 17 июля 2026 года.

## Активный этап

**RM-135 — безопасный конструктор адаптера**

Статус: `IN PROGRESS`

RM-134 завершён после audit-first реализации, feature merge и успешного exact
merge-SHA Windows Quality Gate. RM-135 — единственный активный этап;
RM-136–RM-200 остаются `PLANNED` и не выполняются параллельно.

## Завершённый этап

**RM-134 — выбор протокола**

Статус: `DONE`

Подтверждение:

- audit/plan зафиксированы commit `5889944`, expected-red contract — `6610f11`;
- existing `ProviderEnablementRepository` и `collector_provider_settings.json` расширены до
  schema v4 с in-memory v3 migration, byte-exact backup и optimistic concurrency;
- manual provider получил closed API/RSS/FTP/FTPS selection и honest lifecycle
  `ADAPTER_REQUIRED`, но остался disabled/registration-only/non-runnable;
- credentials, adapter/parser, connection test, DNS и live network не добавлены;
- локально: focused `38 passed in 4.12s`, neighbor
  `169 passed, 2 warnings in 14.66s`, full pytest
  `1796 passed, 2 warnings in 69.63s`; все workflow-equivalent gates успешны;
- feature PR #74 слит в `main` merge commit
  `7ef0378315f9ef76046a651d1211f3da191b7719`;
- PR Quality Gate run `29577913214` и exact merge-SHA run `29578571237` успешны
  на Python 3.12/3.13; full pytest везде — `1796 passed, 2 warnings`;
- deterministic decision logic, legacy bytes и runtime fail-closed guards сохранены;
  RM-135 получает только следующий adapter-construction scope.

## Ранее завершённый этап

**RM-133 — ручное добавление площадки**

Статус: `DONE`

- Feature PR #72 слит в `main` коммитом `c067b5e`.
- Exact merge-SHA Quality Gate run `29573356516` успешен на Python 3.12/3.13.
- Stable manual registration и deterministic decision contracts сохранены.

## Текущее действие

Начать RM-135 с отдельного audit-first пакета и канонического entry gate.
Не начинать RM-136+ и не расширять RM-135 до connection test/normalization behavior без
отдельно утверждённого scope.
