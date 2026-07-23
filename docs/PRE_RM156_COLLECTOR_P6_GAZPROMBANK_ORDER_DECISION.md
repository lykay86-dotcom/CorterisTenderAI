# PRE-RM-156 Collector P6 — docs-only решение о переходе к ЭТП ГПБ

Дата: 23 июля 2026 года.

Статус: `ACCEPTED`.

## 1. Основание

Седьмой P6 source `rts_tender` прошёл отдельный official read-only access audit и принят как
честный внешний blocker:

- PR #141 head `00c0e6900e8d3390f8858d1fbdf9193695684ccf`;
- PR-head Quality Gate `29975868619`: jobs `89107358104` (Python 3.12) и `89107358117`
  (Python 3.13) успешны;
- merge commit `3944dbd0ec35bc358d5149a9cf005b27884b6570`;
- exact merge-SHA Quality Gate `29976202290`: jobs `89108357449` (Python 3.12) и
  `89108357536` (Python 3.13) успешны, включая dependency audit.

`rts_tender` остаётся `BLOCKED_EXTERNAL`. Официальные main и `robots.txt` возвращали ordinary
read-only client Anti-DDoS challenge/503; bypass не выполнялся. Section-specific public human
cards существуют, но machine API/feed, automation/data-reuse permission, exact coverage,
schema/version, pagination/completeness, rate/retry, timezone/currency/exact-money, raw retention
contract и approved fixtures не опубликованы. Common B2B-РТС ownership не доказывает shared
identity/protocol; adapter, fixtures и live verification не созданы.

Предыдущие P6 sources `zakaz_rf`, `roseltorg`, `rad`, `tek_torg`, `ets_nep` и `sber_a` также
сохраняют принятые blocker/identity verdicts и не удаляются из очереди. Раздел P6 канонического ТЗ
ставит `gazprombank` на позицию 8 и запрещает guessed endpoints ради соблюдения порядка. Этот
package сохраняет исходный порядок и создаёт только следующий audit gate.

## 2. Решение

1. Не удалять, не переименовывать и не считать завершёнными implementations `zakaz_rf`,
   `roseltorg`, `rad`, `tek_torg`, `ets_nep`, `sber_a` и `rts_tender`.
2. Сохранить их в позициях 1–7 P6 с принятыми blocker/identity verdicts и возвращаться к каждому
   только после соответствующего external unblock отдельным package от актуального exact baseline.
3. Назначить `gazprombank` (ЭТП ГПБ, позиция 8 P6) следующим **access-audit target**.
4. Не объявлять этим решением доступность API/feed, data-use permission, readiness, fixtures или
   working adapter ЭТП ГПБ. Такие факты устанавливаются только следующим отдельным official
   read-only access/legal/contract audit package.
5. Не переходить к P7 sources параллельно.

Нумерация P6 и RM-001–RM-200 не меняется. RM-156 остаётся единственным активным каноническим RM,
а production-модель контрагента, RM-157 и RM-158 остаются приостановлены до Collector closeout.

## 3. Scope boundary

Этот package меняет только документацию. Он не выполняет ЭТП ГПБ network research и не меняет:

- application/test code или dependency inventory;
- provider identity/catalog/settings/readiness;
- endpoints, hostname allowlist, credentials или keyring;
- fixtures, raw artifacts, checkpoints, DB/schema/migrations;
- score, recommendation или critical stop-factor priority.

Отдельный ЭТП ГПБ access-audit worktree создаётся только после merge и успешного exact merge-SHA
Quality Gate этого docs-only package.

## 4. Rollback

До начала ЭТП ГПБ audit rollback — revert этого docs-only commit. После принятого audit история
решений не переписывается: выполняется новое docs-only решение. Rollback не снимает blocker
verdicts с предыдущих sources, не активирует provider и не удаляет P5/P6 evidence.

## 5. Локальная валидация

Точный docs-only working tree проверен на Python 3.12 командами из текущего `pyproject.toml` и
active GitHub Actions workflow:

- focused identity/factory/catalog contour: `34 passed in 18.96s`;
- full suite: `2467 passed, 2 warnings in 236.06s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Pytest использует workflow `QT_QPA_PLATFORM=offscreen` и fresh command-scoped `--basetemp`.
Repository files/tests/thresholds не меняются. Warnings — неизменные `openpyxl` notices;
dependencies не менялись.

## 6. Publication acceptance

- PR #142 head `8ad58579c5d9a54aec076741f891f95d06579c41`;
- PR-head Quality Gate `29976999580`: jobs `89110806182` (Python 3.12) и `89110806185`
  (Python 3.13) успешны;
- merge commit `cb94e62df7cc7a815693e586b559184868d52e5a`;
- exact merge-SHA Quality Gate `29977374982`: jobs `89111932002` (Python 3.12) и
  `89111932016` (Python 3.13) успешны, включая dependency audit.

Только после exact success создан отдельный ЭТП ГПБ access-audit worktree.
