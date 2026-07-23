# PRE-RM-156 Collector P6 — docs-only решение о переходе к РТС-тендер

Дата: 23 июля 2026 года.

Статус: `DECIDED LOCALLY`; publication/exact gate ожидаются.

## 1. Основание

Шестой P6 source `sber_a` прошёл отдельный official read-only access audit и принят как честный
внешний blocker:

- PR #139 head `eb9eb59a14709a42a13a0d8b6422a6e3e1c57ac2`;
- PR-head Quality Gate `29973982757`: jobs `89101773700` (Python 3.12) и `89101773723`
  (Python 3.13) успешны;
- merge commit `642f53bc812593ce2c1d2b1050d7c7e8d8319e2f`;
- exact merge-SHA Quality Gate `29974214317`: jobs `89102457552` (Python 3.12) и
  `89102457455` (Python 3.13) успешны, включая dependency audit.

`sber_a` остаётся `BLOCKED_EXTERNAL`. Official public human registries для 44-ФЗ и 223-ФЗ
существуют, но machine API/feed, automation/data-reuse permission, stable schema/version,
pagination/completeness, rate/retry, timezone/currency/exact-money, raw retention contract и
approved fixtures не опубликованы. Robots закрывает основные document view/download routes;
adapter, fixtures и live verification не созданы.

Предыдущие P6 sources `zakaz_rf`, `roseltorg`, `rad`, `tek_torg` и `ets_nep` также сохраняют
принятые blocker/identity verdicts и не удаляются из очереди. Раздел P6 канонического ТЗ ставит
`rts_tender` на позицию 7 и запрещает guessed endpoints ради соблюдения очереди. Этот package
сохраняет исходный порядок и создаёт только следующий audit gate.

## 2. Решение

1. Не удалять, не переименовывать и не считать завершёнными implementations `zakaz_rf`,
   `roseltorg`, `rad`, `tek_torg`, `ets_nep` и `sber_a`.
2. Сохранить их в позициях 1–6 P6 с принятыми blocker/identity verdicts и возвращаться к каждому
   только после соответствующего external unblock отдельным package от актуального exact baseline.
3. Назначить `rts_tender` (РТС-тендер, позиция 7 P6) следующим **access-audit target**.
4. Не объявлять этим решением доступность API/feed, data-use permission, readiness, fixtures или
   working adapter РТС-тендер. Такие факты устанавливаются только следующим отдельным official
   read-only access/legal/contract audit package.
5. Не переходить к `gazprombank` или P7 sources параллельно.

Нумерация P6 и RM-001–RM-200 не меняется. RM-156 остаётся единственным активным каноническим RM,
а production-модель контрагента, RM-157 и RM-158 остаются приостановлены до Collector closeout.

## 3. Scope boundary

Этот package меняет только документацию. Он не выполняет РТС-тендер network research и не меняет:

- application/test code или dependency inventory;
- provider identity/catalog/settings/readiness;
- endpoints, hostname allowlist, credentials или keyring;
- fixtures, raw artifacts, checkpoints, DB/schema/migrations;
- score, recommendation или critical stop-factor priority.

Отдельный РТС-тендер access-audit worktree создаётся только после merge и успешного exact
merge-SHA Quality Gate этого docs-only package.

## 4. Rollback

До начала РТС-тендер audit rollback — revert этого docs-only commit. После принятого audit история
решений не переписывается: выполняется новое docs-only решение. Rollback не снимает blocker
verdicts с предыдущих sources, не активирует provider и не удаляет P5/P6 evidence.

## 5. Локальная валидация

Точный docs-only working tree проверен на Python 3.12 командами из текущего `pyproject.toml` и
active GitHub Actions workflow:

- focused identity/factory/catalog contour: `33 passed in 11.38s`;
- full suite: `2467 passed, 2 warnings in 245.98s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Pytest использовал workflow `QT_QPA_PLATFORM=offscreen` и fresh command-scoped `--basetemp`.
Repository files/tests/thresholds не менялись. Warnings — неизменные `openpyxl` notices;
dependencies не менялись. PR-head и exact merge-SHA Windows Quality Gate обязательны до принятия
решения.
