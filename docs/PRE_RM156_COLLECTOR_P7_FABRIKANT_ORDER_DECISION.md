# PRE-RM-156 Collector P7 — docs-only решение о переходе к Фабриканту

Дата: 23 июля 2026 года.

Статус: `LOCALLY VALIDATED`; publication и exact merge-SHA Quality Gate ожидаются.

## 1. Основание

Первый P7 source `b2b_center` прошёл отдельный official read-only access audit и принят как честный
внешний blocker:

- PR #145 head `d4c0f2fb41fe77c5df642884d29016af0cd0442c`;
- PR-head Quality Gate `29980582710`: jobs `89121318689` (Python 3.12) и `89121318642`
  (Python 3.13) успешны;
- merge commit `f7b20a4a5c5d0ee260b04721347c66b8ee2dad2a`;
- exact merge-SHA Quality Gate `29980836778`: jobs `89122049907` (Python 3.12) и
  `89122049924` (Python 3.13) успешно прошли fresh run, включая dependency audit.

`b2b_center` остаётся `BLOCKED_EXTERNAL / CONTRACT_AND_PERMISSION_GATED`. Official API/web service
существует, но method catalog, documentation и XML examples gated Личным кабинетом и тарифом.
Публичный Регламент запрещает automated collection без письменного consent Оператора и задаёт
ceiling 60 HTTP requests/minute. Entitlement/consent, exact endpoint/method/auth and coverage,
schema/version, pagination/completeness, API rate/retry, timezone/money, retention/reuse и approved
fixtures отсутствуют. Human HTML/login automation, adapter, fixtures и live verification не
созданы.

Каноническое ТЗ и implementation plan ставят `fabrikant` вторым source P7 и запрещают guessed
endpoints ради соблюдения порядка. Этот package сохраняет порядок и создаёт только следующий audit
gate; ранее принятые P6 blocker/identity verdicts и B2B-Center verdict неизменны.

## 2. Решение

1. Сохранить `b2b_center` в позиции 1 P7 с принятым blocker verdict и возвращаться к его
   implementation только после external unblock отдельным package от актуального exact baseline.
2. Назначить `fabrikant` (Фабрикант, позиция 2 P7) следующим **access-audit target**.
3. Не объявлять этим решением доступность API/feed, data-use permission, provider readiness,
   fixtures или working adapter Фабриканта. Эти факты устанавливаются только следующим отдельным
   official read-only access/legal/contract audit package.
4. Не начинать `otc`, commercial sections, P8/P9 или production RM-156 параллельно.

Нумерация P7 и RM-001–RM-200 не меняется. RM-156 остаётся единственным активным каноническим RM;
production-модель контрагента, RM-157 и RM-158 остаются приостановлены до Collector closeout.

## 3. Scope boundary

Этот package меняет только документацию. Он не выполняет network research Фабриканта и не меняет:

- application/test code или dependency inventory;
- provider identity/catalog/settings/readiness;
- endpoints, hostname allowlist, credentials или keyring;
- fixtures, raw artifacts, checkpoints, DB/schema/migrations;
- RM-107 score, recommendation или critical stop-factor priority.

Отдельный Фабрикант access-audit worktree создаётся только после merge и успешного exact merge-SHA
Quality Gate этого docs-only package.

## 4. Rollback

До начала Фабрикант audit rollback — revert этого docs-only commit. После принятого audit история
решений не переписывается: выполняется новое docs-only решение. Rollback не снимает blocker с
`b2b_center`, не активирует providers и не удаляет P6/P7 evidence.

## 5. Локальная валидация

- focused identity/factory/catalog contour: `34 passed in 13.35s`;
- full suite: `2467 passed, 2 warnings in 240.18s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Pytest использовал workflow `QT_QPA_PLATFORM=offscreen` и fresh command-scoped `--basetemp`.
Warnings — неизменные `openpyxl` notices; repository files/tests/thresholds/dependencies не
менялись.

## 6. Publication acceptance

Ожидаются PR-head и exact merge-SHA Windows Quality Gate. После exact success отдельный Фабрикант
access-audit worktree создаётся от принятого merge commit.
