# PRE-RM-156 Collector P7 — docs-only решение о переходе к OTC

Дата: 23 июля 2026 года.

Статус: `LOCALLY VALIDATED`; publication и exact merge-SHA Quality Gate ожидаются.

## 1. Основание

Второй P7 source `fabrikant` прошёл отдельный official read-only access audit и принят как честный
внешний blocker:

- PR #147 head `403ec44abee9d0497485ac130b50dc3199351347`;
- PR-head Quality Gate `29984554174`: jobs `89133465443` (Python 3.12) и `89133465378`
  (Python 3.13) успешны;
- merge commit `bf2a44bea889b34689f63495013becae24d050fb`;
- exact merge-SHA Quality Gate `29984821509`: jobs `89134271091` (Python 3.12) и
  `89134271135` (Python 3.13) успешны, включая dependency audit.

`fabrikant` остаётся `BLOCKED_EXTERNAL / PUBLISHED_API_SCOPE_MISMATCH`. Опубликованный SOAP/XML API
предназначен для SRM-систем заказчика и работы с его собственными процедурами; source-wide tender
discovery/search contract отсутствует. Organizer API не подменяет Collector adapter. Discovery
permission, coverage, pagination/completeness, rate/retry, timezone/exact-money, retention/reuse и
approved fixtures не подтверждены. DEMO form/login, human registry scraping, adapter, fixtures и
live verification не использовались.

Каноническое ТЗ и implementation plan ставят `otc` третьим source P7 и запрещают guessed endpoints
ради соблюдения порядка. Этот package сохраняет порядок и создаёт только следующий audit gate;
ранее принятые P6 blockers, B2B-Center и Фабрикант verdicts неизменны.

## 2. Решение

1. Сохранить `b2b_center` и `fabrikant` в позициях 1–2 P7 с принятыми blocker verdicts.
2. Назначить `otc` (OTC, позиция 3 P7) следующим **access-audit target**.
3. Не объявлять этим решением доступность API/feed, data-use permission, provider readiness,
   fixtures или working adapter OTC. Эти факты устанавливаются только следующим отдельным official
   read-only access/legal/contract audit package.
4. Не начинать commercial sections федеральных операторов, P8/P9 или production RM-156
   параллельно.

Нумерация P7 и RM-001–RM-200 не меняется. RM-156 остаётся единственным активным каноническим RM;
production-модель контрагента, RM-157 и RM-158 остаются приостановлены до Collector closeout.

## 3. Scope boundary

Этот package меняет только документацию. Он не выполняет network research OTC и не меняет:

- application/test code или dependency inventory;
- provider identity/catalog/settings/readiness;
- endpoints, hostname allowlist, credentials или keyring;
- fixtures, raw artifacts, checkpoints, DB/schema/migrations;
- RM-107 score, recommendation или critical stop-factor priority.

Отдельный OTC access-audit worktree создаётся только после merge и успешного exact merge-SHA
Quality Gate этого docs-only package.

## 4. Rollback

До начала OTC audit rollback — revert этого docs-only commit. После принятого audit история решений
не переписывается: выполняется новое docs-only решение. Rollback не снимает blockers, не активирует
providers и не удаляет P6/P7 evidence.

## 5. Локальная валидация

- Focused identity/factory/catalog contour: `34 passed in 18.79s`.
- Первый full-suite прогон: `1 failed, 2466 passed, 2 warnings in 279.36s`; единственный
  `test_page_shutdown_stops_sources_and_guards_pending_callbacks` поймал timing-race callback
  `health` после shutdown. Production/test code package не меняет.
- Тот же lifecycle test прошёл `10/10` раз в отдельных fresh pytest processes. Повторный full-suite
  прогон с новым basetemp: `2467 passed, 2 warnings in 249.64s`.
- Ruff: `All checks passed`; format: `804 files already formatted`; mypy:
  `Success: no issues found in 20 source files`; repository secret scan и `git diff --check`
  успешны.

Pytest использовал workflow `QT_QPA_PLATFORM=offscreen` и fresh command-scoped `--basetemp`.
Warnings — неизменные `openpyxl` notices; repository files/tests/thresholds/dependencies не
менялись.

## 6. Publication acceptance

Ожидаются PR-head и exact merge-SHA Windows Quality Gate. После exact success отдельный OTC
access-audit worktree создаётся от принятого merge commit.
