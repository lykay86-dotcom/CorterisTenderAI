# PRE-RM-156 Collector P6 — docs-only решение о переходе к Roseltorg

Дата: 23 июля 2026 года.

Статус: `ACCEPTED`; PR #129 и exact merge-SHA Quality Gate успешны.

## 1. Основание

Первый P6 source `zakaz_rf` прошёл отдельный access audit и принят как честный внешний blocker:

- PR #128 head `2af262d9575f6a9947a51c866d249f28530cec97`;
- PR-head Quality Gate `29956095948`: jobs `89045424680` (Python 3.12) и `89045424729`
  (Python 3.13) успешны;
- merge commit `14bc30300fa40a4008b35df7897d725e682e2437`;
- exact merge-SHA Quality Gate `29958227968`: jobs `89052589841` (Python 3.12) и
  `89052589770` (Python 3.13) успешны, включая dependency audit.

`zakaz_rf` остаётся `BLOCKED_EXTERNAL`: официальный public HTML registry не заменяет отсутствующие
access/data-use contract, schema, pagination/rate/retention rules и approved fixtures. Adapter,
fixture и live verification не были созданы.

Раздел P6 канонического ТЗ разрешает изменить фактический порядок только docs-only решением по
доступности официальных контрактов и запрещает guessed endpoints ради исходной очереди. Этот
package реализует именно такое решение.

## 2. Решение

1. Не удалять, не переименовывать и не считать завершённым implementation `zakaz_rf`.
2. Сохранить `zakaz_rf` в позиции 1 P6 и вернуться к нему после external unblock отдельным
   package от актуального exact baseline.
3. Назначить `roseltorg` (позиция 2 P6) следующим **access-audit target**.
4. Не объявлять этим решением доступность API/feed, readiness, fixtures или working adapter
   Roseltorg. Такие факты устанавливаются только следующим отдельным read-only audit package.
5. Не переходить к `rad` и последующим sources параллельно.

Нумерация P6 и RM-001–RM-200 не меняется. RM-156 остаётся единственным активным каноническим RM,
а production-модель контрагента, RM-157 и RM-158 остаются приостановлены до Collector closeout.

## 3. Scope boundary

Этот package меняет только документацию. Он не выполняет Roseltorg network research и не меняет:

- application/test code или dependency inventory;
- provider identity/catalog/settings/readiness;
- endpoints, hostname allowlist, credentials или keyring;
- fixtures, raw artifacts, checkpoints, DB/schema/migrations;
- score, recommendation или critical stop-factor priority.

Следующий Roseltorg worktree создаётся только после merge и успешного exact merge-SHA Quality Gate
этого docs-only package.

## 4. Rollback

До начала Roseltorg audit rollback — revert этого docs-only commit. После принятого Roseltorg audit
история решений не переписывается: выполняется новое docs-only решение. Rollback не снимает
`BLOCKED_EXTERNAL` с `zakaz_rf`, не активирует provider и не удаляет P5/P6 evidence.

## 5. Локальная валидация

Точный docs-only working tree проверен на Python 3.12:

- full suite: `2467 passed, 2 warnings in 278.40s`;
- Ruff: `All checks passed`;
- format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan: passed;
- `git diff --check`: passed.

Warnings — неизменные `openpyxl` extension/conditional-formatting notices в
`test_rm132_legacy_credentials_handoff`; новых warnings нет. Dependency inventory не менялся.
PR-head и exact merge-SHA Windows Quality Gate остаются обязательными до принятия решения.

Publication acceptance: PR #129 head `6df486b31d0953ae140be2c03939bab848b757b3`, PR-head run
`29959486498`; merge `862dac27b38968f235f831402139980e17cc90f3`, exact run `29959911671`.
Обе Python 3.12/3.13 jobs и dependency audit успешны. Только после этого создан отдельный
Roseltorg access-audit worktree.
