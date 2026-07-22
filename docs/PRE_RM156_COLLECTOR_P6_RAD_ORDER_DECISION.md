# PRE-RM-156 Collector P6 — docs-only решение о переходе к Rad

Дата: 23 июля 2026 года.

Статус: `ACCEPTED`; PR #131 и exact merge-SHA Quality Gate успешны.

## 1. Основание

Второй P6 source `roseltorg` прошёл отдельный read-only access audit и принят как честный
внешний blocker:

- PR #130 head `ebbdcf640fa87162db136147d9fc3be4420eaa29`;
- PR-head Quality Gate `29961223536`: jobs `89062439998` (Python 3.12) и `89062440086`
  (Python 3.13) успешны;
- merge commit `aa9825b5b4d515958c3b02c00d63a215a5af8b27`;
- exact merge-SHA Quality Gate `29961900274`: jobs `89064615441` (Python 3.12) и
  `89064615340` (Python 3.13) успешны, включая dependency audit.

`roseltorg` остаётся `BLOCKED_EXTERNAL`: public HTML search/detail и robots indexability не
заменяют отсутствующие procurement API/feed либо явно разрешённый stable HTML contract,
data-use/raw-retention permission, schema/version/rate rules и approved fixtures. API отдельного
ЭДО не является tender API. Adapter, fixture и live verification не были созданы.

Первый P6 source `zakaz_rf` также остаётся `BLOCKED_EXTERNAL` по принятому PR #128 и не удаляется
из очереди. Раздел P6 канонического ТЗ разрешает изменить фактический порядок только docs-only
решением по доступности официальных контрактов и запрещает guessed endpoints ради исходной
очереди. Этот package реализует именно такое последовательное решение.

## 2. Решение

1. Не удалять, не переименовывать и не считать завершёнными implementations `zakaz_rf` и
   `roseltorg`.
2. Сохранить `zakaz_rf` и `roseltorg` в позициях 1 и 2 P6 со статусом `BLOCKED_EXTERNAL` и
   возвращаться к каждому только после соответствующего external unblock отдельным package от
   актуального exact baseline.
3. Назначить `rad` (Российский аукционный дом / Lot-online, позиция 3 P6) следующим
   **access-audit target**.
4. Не объявлять этим решением доступность API/feed, data-use permission, readiness, fixtures или
   working adapter Rad. Такие факты устанавливаются только следующим отдельным official read-only
   access/legal/contract audit package.
5. Не переходить к `tek_torg` и последующим sources параллельно.

Нумерация P6 и RM-001–RM-200 не меняется. RM-156 остаётся единственным активным каноническим RM,
а production-модель контрагента, RM-157 и RM-158 остаются приостановлены до Collector closeout.

## 3. Scope boundary

Этот package меняет только документацию. Он не выполняет Rad network research и не меняет:

- application/test code или dependency inventory;
- provider identity/catalog/settings/readiness;
- endpoints, hostname allowlist, credentials или keyring;
- fixtures, raw artifacts, checkpoints, DB/schema/migrations;
- score, recommendation или critical stop-factor priority.

Отдельный Rad access-audit worktree создаётся только после merge и успешного exact merge-SHA
Quality Gate этого docs-only package.

## 4. Rollback

До начала Rad audit rollback — revert этого docs-only commit. После принятого Rad audit история
решений не переписывается: выполняется новое docs-only решение. Rollback не снимает
`BLOCKED_EXTERNAL` с `zakaz_rf` или `roseltorg`, не активирует provider и не удаляет P5/P6
evidence.

## 5. Локальная валидация

Точный docs-only working tree проверен на Python 3.12 командами из текущего `pyproject.toml` и
active GitHub Actions workflow:

- full suite: `2467 passed, 2 warnings in 163.59s`;
- Ruff: `All checks passed`;
- format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan: passed;
- `git diff --check`: passed.

Первый full-suite attempt был инфраструктурно недействителен: pytest не имел доступа к старому
global temp root `pytest-of-сooocorteris` и завершился setup `PermissionError`, не test assertion.
Fail-fast reproduction подтвердил общий `tmp_path` root cause; исходно падавший test прошёл
`1 passed in 0.35s` с новым уникальным command-scoped `--basetemp`, после чего полный suite выше
прошёл с другим уникальным `--basetemp`. Repository files, tests и thresholds для обхода ошибки не
менялись.

Warnings — неизменные `openpyxl` extension/conditional-formatting notices в
`test_rm132_legacy_credentials_handoff`; новых warnings нет. Dependency inventory не менялся.
PR-head и exact merge-SHA Windows Quality Gate остаются обязательными до принятия решения.

## 6. Publication acceptance

- PR #131 head `c4df48df5bfbc4fc1d2dc55a8fedd5fd6ff66803`;
- PR-head Quality Gate `29963756719`: jobs `89070568520` (Python 3.12) и `89070568448`
  (Python 3.13) успешны;
- merge commit `4e5adfec20d7ad95ac2fe4decd005b0041e60909`;
- exact merge-SHA Quality Gate `29964235838`: jobs `89072056995` (Python 3.12) и
  `89072057051` (Python 3.13) успешны, включая dependency audit.

Только после exact success создан отдельный Rad access-audit worktree.
