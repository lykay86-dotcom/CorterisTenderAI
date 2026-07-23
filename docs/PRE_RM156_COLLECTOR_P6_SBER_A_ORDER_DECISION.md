# PRE-RM-156 Collector P6 — docs-only решение о переходе к Сбербанк-АСТ

Дата: 23 июля 2026 года.

Статус: `ACCEPTED`.

## 1. Основание

Пятый P6 source `ets_nep` прошёл отдельный official read-only access audit. Последующий
identity/section package принял безопасную границу с canonical `fabrikant`:

- один operator АО «ЭТС» и migration `etp-ets.ru` → `44.fabrikant.ru` подтверждены;
- `ets_nep` и `fabrikant` сохранены disabled section-scoped placeholders без guessed alias или
  persisted-ID rewrite;
- future implementation имеет одного operator owner; section-specific views требуют audited
  protocol/schema/authorization evidence;
- `ets_nep` остаётся `BLOCKED_EXTERNAL`, `fabrikant` не получает readiness claim.

Identity decision принят PR #137:

- head `e3550871a95f0c103ee7f6e2799ccc120c1d2ba4`;
- PR-head Quality Gate `29971869854`: jobs `89095401781` (Python 3.12) и `89095401782`
  (Python 3.13) успешны;
- merge commit `cd39b8e82d2ce208aa4498462c545f0fab894044`;
- exact merge-SHA Quality Gate `29972112388`: jobs `89096127682` (Python 3.12) и
  `89096127713` (Python 3.13) успешны, включая dependency audit.

Предыдущие P6 sources `zakaz_rf`, `roseltorg`, `rad` и `tek_torg` также остаются
`BLOCKED_EXTERNAL`. Ни один из них не удаляется из очереди и не считается реализованным. Раздел
P6 канонического ТЗ ставит `sber_a` на позицию 6 и запрещает guessed endpoints ради соблюдения
очереди. Этот package сохраняет исходный порядок и создаёт только следующий audit gate.

## 2. Решение

1. Не удалять, не переименовывать и не считать завершёнными implementations `zakaz_rf`,
   `roseltorg`, `rad`, `tek_torg` и `ets_nep`.
2. Сохранить их в позициях 1–5 P6 с принятыми blocker/identity verdicts и возвращаться к каждому
   только после соответствующего external unblock отдельным package от актуального exact baseline.
3. Назначить `sber_a` (Сбербанк-АСТ, позиция 6 P6) следующим **access-audit target**.
4. Не объявлять этим решением доступность API/feed, data-use permission, readiness, fixtures или
   working adapter Сбербанк-АСТ. Такие факты устанавливаются только следующим отдельным official
   read-only access/legal/contract audit package.
5. Не переходить к `rts_tender`, `gazprombank` или P7 sources параллельно.

Нумерация P6 и RM-001–RM-200 не меняется. RM-156 остаётся единственным активным каноническим RM,
а production-модель контрагента, RM-157 и RM-158 остаются приостановлены до Collector closeout.

## 3. Scope boundary

Этот package меняет только документацию. Он не выполняет Сбербанк-АСТ network research и не
меняет:

- application/test code или dependency inventory;
- provider identity/catalog/settings/readiness;
- endpoints, hostname allowlist, credentials или keyring;
- fixtures, raw artifacts, checkpoints, DB/schema/migrations;
- score, recommendation или critical stop-factor priority.

Отдельный Сбербанк-АСТ access-audit worktree создаётся только после merge и успешного exact
merge-SHA Quality Gate этого docs-only package.

## 4. Rollback

До начала Сбербанк-АСТ audit rollback — revert этого docs-only commit. После принятого audit
история решений не переписывается: выполняется новое docs-only решение. Rollback не снимает
blocker verdicts с предыдущих sources, не активирует provider и не удаляет P5/P6 evidence.

## 5. Локальная валидация

Точный docs-only working tree проверен на Python 3.12 командами из текущего `pyproject.toml` и
active GitHub Actions workflow:

- focused identity/factory/catalog contour: `33 passed in 11.63s`;
- full suite: `2467 passed, 2 warnings in 242.06s`;
- Ruff: `All checks passed`; format: `804 files already formatted`;
- mypy: `Success: no issues found in 20 source files`;
- repository secret scan и `git diff --check`: passed.

Pytest использовал `QT_QPA_PLATFORM=offscreen`, как active Quality Gate, и fresh command-scoped
`--basetemp` из-за ранее диагностированного ACL дефекта старого global pytest temp root. Repository
files/tests/thresholds не менялись. Warnings — неизменные `openpyxl` notices; dependencies не
менялись. PR-head и exact merge-SHA Windows Quality Gate обязательны до принятия решения.

## 6. Publication acceptance

- PR #138 head `1ddc2d726a6279ffb94023c89d6d90fc82e2347d`;
- PR-head Quality Gate `29972908601`: jobs `89098549848` (Python 3.12) и `89098549930`
  (Python 3.13) успешны;
- merge commit `7d1e728a99c384acd72d3b7b13ab274378fe7d47`;
- exact merge-SHA Quality Gate `29973164497`: jobs `89099325527` (Python 3.12) и
  `89099325555` (Python 3.13) успешны, включая dependency audit.

Только после exact success создан отдельный Сбербанк-АСТ access-audit worktree.
