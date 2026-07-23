# PRE-RM-156 Collector P6 — docs-only решение о переходе к ETS/НЭП

Дата: 23 июля 2026 года.

Статус: `DECIDED LOCALLY`; publication и exact merge-SHA Quality Gate ожидаются.

## 1. Основание

Четвёртый P6 source `tek_torg` прошёл отдельный official read-only access audit и принят как
честный внешний blocker:

- PR #134 head `44e2975237899b6672681323f8a36d457fd55825`;
- PR-head Quality Gate `29967886571`: jobs `89083246018` (Python 3.12) и `89083245976`
  (Python 3.13) успешны;
- merge commit `30f6fb1c318d4c0ddc9b10d1dace6cb429c93e8f`;
- exact merge-SHA Quality Gate `29968220150`: jobs `89084249165` (Python 3.12) и
  `89084249132` (Python 3.13) успешны, включая dependency audit.

`tek_torg` остаётся `BLOCKED_EXTERNAL`. Официальный public SOAP procedure export существует,
но contract не публикует обязательные rate/retry limits, maximum page and snapshot consistency,
schema/version policy, exact timezone/currency/money semantics или raw response/document
retention and reuse permission. Approved fixtures не сохранены; adapter и live verification не
созданы.

Предыдущие P6 sources `zakaz_rf`, `roseltorg` и `rad` также остаются `BLOCKED_EXTERNAL` и не
удаляются из очереди. Раздел P6 канонического ТЗ разрешает изменить фактический порядок только
docs-only решением по доступности официальных контрактов и запрещает guessed endpoints ради
исходной очереди. Этот package реализует именно такое последовательное решение.

## 2. Решение

1. Не удалять, не переименовывать и не считать завершёнными implementations `zakaz_rf`,
   `roseltorg`, `rad` и `tek_torg`.
2. Сохранить их в позициях 1–4 P6 со статусом `BLOCKED_EXTERNAL` и возвращаться к каждому только
   после соответствующего external unblock отдельным package от актуального exact baseline.
3. Назначить `ets_nep` (Национальная электронная площадка, позиция 5 P6) следующим
   **access-audit target**.
4. Не объявлять этим решением доступность API/feed, data-use permission, readiness, fixtures или
   working adapter ETS/НЭП. Такие факты устанавливаются только следующим отдельным official
   read-only access/legal/contract audit package.
5. Не переходить к `sber_a` и последующим sources параллельно.

Нумерация P6 и RM-001–RM-200 не меняется. RM-156 остаётся единственным активным каноническим RM,
а production-модель контрагента, RM-157 и RM-158 остаются приостановлены до Collector closeout.

## 3. Scope boundary

Этот package меняет только документацию. Он не выполняет ETS/НЭП network research и не меняет:

- application/test code или dependency inventory;
- provider identity/catalog/settings/readiness;
- endpoints, hostname allowlist, credentials или keyring;
- fixtures, raw artifacts, checkpoints, DB/schema/migrations;
- score, recommendation или critical stop-factor priority.

Отдельный ETS/НЭП access-audit worktree создаётся только после merge и успешного exact merge-SHA
Quality Gate этого docs-only package.

## 4. Rollback

До начала ETS/НЭП audit rollback — revert этого docs-only commit. После принятого ETS/НЭП audit
история решений не переписывается: выполняется новое docs-only решение. Rollback не снимает
`BLOCKED_EXTERNAL` с предыдущих sources, не активирует provider и не удаляет P5/P6 evidence.

## 5. Локальная валидация

Точный docs-only working tree проверен на Python 3.12 командами из текущего `pyproject.toml` и
active GitHub Actions workflow:

- focused identity/factory/catalog contour: `33 passed in 10.49s`;
- final full suite: `2467 passed, 2 warnings in 231.45s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Первый full-suite attempt завершился нативным Windows `0xc0000374` внутри
`test_background_error_keeps_previous_data`, без pytest assertion и без Python exception. По
debugging stop-line точный тест прошёл отдельно (`1 passed`), весь файл затем прошёл четыре раза
подряд (`20 passed` суммарно), а final full suite прошёл полностью. Сбой классифицирован как
невоспроизводимый intermittent Windows/Qt test-harness failure; application/tests не менялись и
gate не ослаблялся.

Все pytest commands использовали fresh command-scoped `--basetemp` из-за ранее диагностированного
ACL дефекта старого global pytest temp root. Warnings — неизменные `openpyxl` notices;
dependencies не менялись. PR-head и exact merge-SHA Windows Quality Gate остаются обязательными
до принятия решения.
