# Текущее состояние CorterisTenderAI

Обновлено: 17 июля 2026 года.

## Активный этап

**RM-134 — выбор протокола**

Статус: `IN PROGRESS`

RM-133 завершён после audit-first реализации, feature merge и успешного exact
merge-SHA Windows Quality Gate. RM-134 — единственный активный этап;
RM-135–RM-200 остаются `PLANNED` и не выполняются параллельно.

## Завершённый этап

**RM-133 — ручное добавление площадки**

Статус: `DONE`

Подтверждение:

- audit/plan зафиксированы docs-only commit `31e1456`, expected-red contract — `d3f8906`;
- существующий `ProviderEnablementRepository` и `collector_provider_settings.json`
  расширены до schema v3 без второго catalog/store и без DB migration;
- ручные регистрации имеют stable ID и inert состояние `PROTOCOL_REQUIRED`; credentials,
  protocol/adapter, connection test, DNS и live network не добавлены;
- локально: focused `51 passed in 4.31s`, neighbor `160 passed, 2 warnings in 12.65s`,
  full pytest `1758 passed, 2 warnings in 66.57s`; все workflow-equivalent gates успешны;
- feature PR #72 слит в `main` merge commit
  `c067b5ecbc24428906dd006abe1e0ee6eef48e12`;
- PR Quality Gate run `29572356676` и exact merge-SHA run `29573356516` успешны
  на Python 3.12/3.13; full pytest везде — `1758 passed, 2 warnings`;
- deterministic decision logic, provider execution до выбора протокола и legacy bytes
  сохранены; RM-134 получает только следующий protocol-selection scope.

## Ранее завершённый этап

**RM-132 — безопасный ввод API и credentials**

Статус: `DONE`

- Feature PR #70 слит в `main` коммитом `1ae9c36`.
- Exact merge-SHA Quality Gate run `29567132554` успешен на Python 3.12/3.13.
- Единый credential owner и deterministic decision contracts сохранены.

## Текущее действие

Начать RM-134 с отдельного audit-first пакета и канонического entry gate.
Не начинать RM-135+ и не расширять RM-134 до executable adapter/connection behavior без
отдельно утверждённого scope.
