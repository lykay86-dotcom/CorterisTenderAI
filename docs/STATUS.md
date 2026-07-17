# Текущее состояние CorterisTenderAI

Обновлено: 17 июля 2026 года.

## Активный этап

**RM-136 — тест подключения**

Статус: `IN PROGRESS`

RM-135 завершён после audit-first реализации, feature merge и успешного exact
merge-SHA Windows Quality Gate. RM-136 — единственный активный этап;
RM-137–RM-200 остаются `PLANNED` и не выполняются параллельно.

## Завершённый этап

**RM-135 — безопасный конструктор адаптера**

Статус: `DONE`

Подтверждение:

- audit/plan зафиксированы commit `b0f1048`, expected-red contract — `e7b9121`;
- существующий `ProviderEnablementRepository` повышен до schema v5 с in-memory v4 migration,
  byte-exact backup, atomic replace, monotonic revisions и bounded rollback history;
- immutable `ManualAdapterSpec` v1, static API/RSS/FTP/FTPS compiler и bounded offline
  JSON/XML/RSS/Atom/CSV preview добавлены без второго store/catalog/factory/Collector;
- manual adapter соответствует `AsyncTenderProvider`, но остаётся disabled, unverified,
  non-runnable и `CONNECTION_TEST_REQUIRED`; live methods fail closed;
- network, DNS, TLS handshake, credential resolution, connection test и live health не добавлены;
- локально: focused `27 passed`, neighbor `205 passed, 2 warnings`, full pytest
  `1823 passed, 2 warnings`; все workflow-equivalent gates успешны;
- feature PR #76 слит в `main` merge commit
  `306b20977b6c23956488dc471da63af17f197e25`;
- PR Quality Gate run `29584304208` успешен на Python 3.12/3.13;
- exact merge-SHA run `29586643112` успешен: Python 3.12 rerun —
  `1823 passed, 2 warnings in 86.41s`, Python 3.13 —
  `1823 passed, 2 warnings in 88.19s`; первый Python 3.12 attempt завершился native
  Windows access violation без test assertion, failed-only rerun прошёл без изменений;
- deterministic decision logic, legacy bytes, credential boundary и runtime admission guards
  сохранены; RM-136 получает только explicit connection-test/health scope.

## Ранее завершённый этап

**RM-134 — выбор протокола**

Статус: `DONE`

- Feature PR #74 слит в `main` коммитом `7ef0378`.
- Exact merge-SHA Quality Gate run `29578571237` успешен на Python 3.12/3.13.
- Closed protocol selection и non-runnable lifecycle сохранены.

## Текущее действие

Начать RM-136 с отдельного audit-first пакета и канонического entry gate.
Не начинать RM-137+ и не разрешать production admission manual provider без отдельно
утверждённых connection verification, SSRF/DNS, redirect, TLS и FTP/FTPS transport решений.
