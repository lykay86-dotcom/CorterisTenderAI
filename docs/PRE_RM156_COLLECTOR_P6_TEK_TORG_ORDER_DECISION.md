# PRE-RM-156 Collector P6 — docs-only решение о переходе к TekTorg

Дата: 23 июля 2026 года.

Статус: `DECIDED LOCALLY`; publication и exact merge-SHA Quality Gate ожидаются.

## 1. Основание

Третий P6 source `rad` прошёл отдельный official read-only access audit и принят как честный
внешний blocker:

- PR #132 head `6ca84f2f523dce6f853cfb919420d6e36caca06e`;
- PR-head Quality Gate `29965371309`: jobs `89075592391` (Python 3.12) и `89075592367`
  (Python 3.13) успешны;
- merge commit `38fe2d75f80beb544e9b5a7a2d18462963c4f232`;
- exact merge-SHA Quality Gate `29965734080`: jobs `89076696779` (Python 3.12) и
  `89076696809` (Python 3.13) успешны, включая dependency audit.

`rad` остаётся `BLOCKED_EXTERNAL`: действующее operator agreement прямо требует письменного
разрешения для scripts/access/collection и запрещает automated extraction/copying. Procurement
API/feed/schema/rate/raw-retention contract и approved fixtures не найдены. Adapter, fixture и
live verification не были созданы.

Предыдущие P6 sources `zakaz_rf` и `roseltorg` также остаются `BLOCKED_EXTERNAL` и не удаляются
из очереди. Раздел P6 канонического ТЗ разрешает изменить фактический порядок только docs-only
решением по доступности официальных контрактов и запрещает guessed endpoints ради исходной
очереди. Этот package реализует именно такое последовательное решение.

## 2. Решение

1. Не удалять, не переименовывать и не считать завершёнными implementations `zakaz_rf`,
   `roseltorg` и `rad`.
2. Сохранить их в позициях 1–3 P6 со статусом `BLOCKED_EXTERNAL` и возвращаться к каждому только
   после соответствующего external unblock отдельным package от актуального exact baseline.
3. Назначить `tek_torg` (ТЭК-Торг, позиция 4 P6) следующим **access-audit target**.
4. Не объявлять этим решением доступность API/feed, data-use permission, readiness, fixtures или
   working adapter TekTorg. Такие факты устанавливаются только следующим отдельным official
   read-only access/legal/contract audit package.
5. Не переходить к `ets_nep` и последующим sources параллельно.

Нумерация P6 и RM-001–RM-200 не меняется. RM-156 остаётся единственным активным каноническим RM,
а production-модель контрагента, RM-157 и RM-158 остаются приостановлены до Collector closeout.

## 3. Scope boundary

Этот package меняет только документацию. Он не выполняет TekTorg network research и не меняет:

- application/test code или dependency inventory;
- provider identity/catalog/settings/readiness;
- endpoints, hostname allowlist, credentials или keyring;
- fixtures, raw artifacts, checkpoints, DB/schema/migrations;
- score, recommendation или critical stop-factor priority.

Отдельный TekTorg access-audit worktree создаётся только после merge и успешного exact merge-SHA
Quality Gate этого docs-only package.

## 4. Rollback

До начала TekTorg audit rollback — revert этого docs-only commit. После принятого TekTorg audit
история решений не переписывается: выполняется новое docs-only решение. Rollback не снимает
`BLOCKED_EXTERNAL` с предыдущих sources, не активирует provider и не удаляет P5/P6 evidence.

## 5. Локальная валидация

Точный docs-only working tree проверен на Python 3.12 командами из текущего `pyproject.toml` и
active GitHub Actions workflow:

- full suite: `2467 passed, 2 warnings in 174.82s`;
- Ruff: `All checks passed`;
- format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Full suite использовал fresh command-scoped `--basetemp` из-за ранее диагностированного ACL
дефекта старого global pytest temp root; repository files, tests и thresholds не менялись.
Warnings — неизменные `openpyxl` notices; dependencies не менялись. PR-head и exact merge-SHA
Windows Quality Gate остаются обязательными до принятия решения.
