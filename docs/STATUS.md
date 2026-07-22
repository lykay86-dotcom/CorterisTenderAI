# Текущее состояние CorterisTenderAI

Обновлено: 22 июля 2026 года.

## Активный этап

**RM-156 — модель контрагента (production-реализация приостановлена)**

Статус: `IN PROGRESS`

RM-155 завершён feature PR #118 на head
`c741ba6a39750436fa34ffc2237bd1c264466745`, merge commit
`63a85b4cff5e2de5b53e4fad6dcfb091371200bf` и успешным exact merge-SHA Windows Quality Gate
run `29845412052`. Этот отдельный docs-only closeout переводит RM-155 в `DONE`, закрывает
`UI-141-017` и завершает последовательность полного редизайна RM-141–RM-155. RM-156 —
единственный активный этап; RM-157–RM-200 остаются `PLANNED` и не выполняются параллельно.

Решением владельца от 22 июля 2026 года до production-реализации модели контрагента выполняется
обязательный Collector prerequisite по многоплощадочному сбору. Это prerequisite RM-156, а не
новый или параллельный RM: RM-156 остаётся единственным каноническим `IN PROGRESS`, а
RM-157–RM-200 остаются `PLANNED`. Полный scope и package gates зафиксированы в
[`PRE_RM156_TENDER_COLLECTOR_ALL_PLATFORMS_TZ.md`](PRE_RM156_TENDER_COLLECTOR_ALL_PLATFORMS_TZ.md).

Docs-only P0 слит PR #121 merge commit
`c20bed32492dc80b48748c79a87da73107533ddd`; exact merge-SHA Quality Gate run `29922814088`
успешен. Docs-only P1 слит PR #122 merge commit
`6593fb2518d724c9bdde3ea46c9de84ff63b1b03`; exact merge-SHA Quality Gate run `29926327653`
успешен на Python 3.12/3.13. P2 strict expected-red tests-only package подготовлен отдельной
веткой до application changes. Production-код модели контрагента, RM-157 и RM-158 не начинаются до
отдельного Collector closeout. Closeout должен вернуть RM-156 в production work; только затем
продолжается модель контрагента и последующие RM в исходной нумерации.

## Завершённый этап

**RM-155 — завершение редизайна**

Статус: `DONE`

Подтверждение:

- audit-first пакет классифицировал 32 compatibility candidates: 9 `REMOVE`, 2 `MIGRATE`,
  21 `KEEP`, 0 `DEPRECATE`, 0 `BLOCKED`, с consumer/history/runtime/settings/frozen/public
  evidence, owner и rollback для каждого;
- удалены только obsolete `app.ui.main_window`, два same-object page alias, их bootstrap fallback
  и неиспользуемый search shim; сохранена одна production composition без duplicate owner;
- J01–J16 и cross-stage RM-142–RM-154 guards прошли; RM-107 deterministic decision и абсолютный
  приоритет critical stop-factor не изменены;
- локально: полный pytest `2411 passed, 2 warnings in 207.24s`, neighboring contour `840 passed`,
  Ruff/format (`794 files`), mypy, secret/offline/migration/composition/build/dependency gates
  успешны;
- fresh RM-153 performance p95 и 25-cycle resource budgets прошли; controlled same-host A/B не
  обнаружил shutdown regression;
- RM-152 native evidence остаётся truthful: `0 PASS`, `4 BLOCKED`, `29 NOT_EXECUTED`;
- actual one-file EXE SHA-256
  `044B35A3D8D73132A603073FBB0F8456010950B19CB5696C2EFBB8D7BC41F7A0` прошёл все девять
  isolated frozen self-test checks;
- feature PR #118 слит merge commit `63a85b4cff5e2de5b53e4fad6dcfb091371200bf`;
- PR-head Quality Gate `29832379070` и exact merge-SHA push-run `29845412052` успешны на Python
  3.12/3.13; Python 3.12 strict visual comparison имеет `14/14 PASS`;
- DB/schema/migration, dependencies, persisted settings/data и provider/network/AI/keyring/domain
  paths не изменены; rollback — revert feature merge без downgrade данных.

## Ранее завершённый этап

**RM-154 — визуальное тестирование**

Статус: `DONE`

- Canonical strict RGB catalog содержит 14 representative dark/light cases с zero tolerance и
  renderer fingerprint `f1cd92373456028fd9360b3a032ef9b8d5784dc90d00abad4080d404db0dba56`.
- Feature PR #116 слит merge commit `40f0e327d0d485b93e93f39bab1d838e584b8914`.
- Exact merge-SHA Quality Gate run `29823579968` успешен на Python 3.12/3.13 и strict visual
  comparison `14/14 PASS`.

## Текущее действие

Проверить и слить отдельный P2 strict expected-red tests-only package. После его merge и успешного
exact merge-SHA Quality Gate начать отдельный P3 shared page/artifact/checkpoint foundation.
Не смешивать P3 с provider identity/adapters и не начинать production-реализацию модели
контрагента, RM-157 или RM-158 до отдельного Collector closeout.
