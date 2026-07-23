# PRE-RM-156 Collector — docs-only решение границы P6/P7

Дата: 23 июля 2026 года.

Статус: `LOCALLY VALIDATED`; publication и exact merge-SHA Quality Gate ожидаются.

## 1. Основание

Восьмой source P6 `gazprombank` прошёл отдельный official read-only access audit:

- PR #143 head `8dcfbf6469747fc3e8644761693cc85a076d1b39`;
- PR-head Quality Gate `29978156861`: jobs `89114212457` (Python 3.12) и `89114212487`
  (Python 3.13) успешны;
- merge commit `102aff662f3cd068c13c095cb6470912cc0bfc60`;
- exact merge-SHA Quality Gate `29978439856`: jobs `89115056696` (Python 3.12) и
  `89115056687` (Python 3.13) успешны, включая dependency audit.

`gazprombank` остаётся `BLOCKED_EXTERNAL / PUBLISHED_FEED_UNAVAILABLE`: explicit RSS permission
intent опубликован, но официальный endpoint отвечает final `404`; schema/version, exact coverage,
pagination/completeness, rate/retry, money/timezone, retention и fixtures не подтверждены. Код и
fixtures не созданы.

Каноническое ТЗ ставит `gazprombank` восьмым в P6 и начинает P7 с `b2b_center`. Старый supporting
implementation plan ошибочно опускал `gazprombank` в P6 и повторял первым в P7. По repository
instructions каноническое ТЗ/ROADMAP определяет scope; этот package синхронизирует supporting plan
без изменения identity, порядка канонического ТЗ или уже принятой истории.

## 2. Решение

1. Зафиксировать завершение последовательного **access-audit pass** P6 по позициям 1–8. Это не
   объявляет blocked sources implemented/working и не закрывает весь Collector prerequisite.
2. Исправить implementation plan: добавить `gazprombank` восьмым в P6; P7 оставить в каноническом
   порядке `b2b_center`, `fabrikant`, `otc`, затем commercial sections федеральных операторов
   только внутри их existing owner.
3. Сохранить все принятые P6 blocker/identity verdicts и возвращаться к source implementation
   только после его external unblock и нового package от актуального exact baseline.
4. Назначить `b2b_center` следующим **P7 access-audit target** без API/feed, permission, readiness,
   fixture или working-adapter claim.
5. Не начинать `fabrikant`, `otc`, commercial section implementation, P8/P9 или RM-156 production
   параллельно.

Отдельный B2B-Center audit worktree создаётся только после merge и успешного exact merge-SHA
Quality Gate этого решения.

## 3. Scope boundary

Package меняет только документацию и не выполняет B2B-Center network research. Не меняются:

- application/test code, dependencies или thresholds;
- provider identities, catalogs, settings/readiness или credential descriptors;
- endpoints, host allowlists, secrets/keyring;
- fixtures, raw artifacts, checkpoints, DB/schema/migrations;
- RM-107 score, recommendation или critical stop-factor priority.

P6 не объявляется feature-complete: восемь source slots имеют auditable verdicts, но external
blockers сохраняются. P7 начинается только как следующий access audit, не как implementation.

## 4. Rollback

До начала B2B-Center audit rollback — revert этого docs-only commit. После следующего принятого
audit история решений не переписывается: выполняется новый docs-only amendment. Rollback не
снимает blocker verdicts, не повторяет `gazprombank` в P7 и не активирует providers.

## 5. Локальная валидация

- focused identity/factory/catalog contour: `34 passed in 14.09s`;
- full suite: `2467 passed, 2 warnings in 252.05s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Pytest использовал active workflow `QT_QPA_PLATFORM=offscreen` и fresh command-scoped
`--basetemp`. Warnings — неизменные `openpyxl` notices; dependencies/tests/thresholds не менялись.
PR-head и exact merge-SHA Windows Quality Gate обязательны до принятия решения.
