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
успешен на Python 3.12/3.13. P2 strict expected-red tests-only package слит PR #123 merge commit
`83899900fd2913eefd0ad04398e266f4a6b64437`; exact merge-SHA Quality Gate run `29929323692`
успешен на Python 3.12/3.13. P3 shared foundation слит PR #124 merge commit
`cfc473e8a11c6c2c7bc201bbac45aa38404d7cc2`; PR-head run `29939287327` и exact merge-SHA run
`29939811499` успешны на Python 3.12/3.13. Первый P4 package — EIS reference adapter — слит PR
#125 merge commit `300385108082746ac8818dad19104f57618366a9`; PR-head run `29943116366` и exact
merge-SHA run `29943599187` успешны на Python 3.12/3.13. Второй P4 package — `mos_supplier`
reference adapter — слит PR #126 merge commit `b4704480010a363e02ad80fe579d5c836cd04509`;
PR-head run `29946701032` и exact merge-SHA run `29947263908` успешны на Python 3.12/3.13,
включая dependency audit. Один документированный authenticated API response, shared atomic
accepted-page/checkpoint/artifact path, raw search/detail/document/rejected evidence и fail-closed
redaction приняты. Full suite `2458 passed`, exact-data 10k/resource gate зелёный. EIS и Mos
Supplier честно остаются `IMPLEMENTED_OFFLINE` до отдельно разрешённой live verification;
серверная пагинация Mos не заявлена и не угадана. Production-код модели контрагента, RM-157 и
RM-158 не начинаются до
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

P5 identity/catalog package реализован и полностью проверен локально: exact 13 canonical IDs,
settings schema 7, Collector DB schema 16, audited alias/read-model compatibility и inert catalog
projections. Full suite: `2467 passed, 2 warnings`; Ruff/format (`804 files`), mypy, secret,
offline/migration/composition/build/RM-155 gates успешны. Следующее действие — опубликовать
выделенную P5 ветку и получить успешные PR-head и exact merge-SHA Quality Gate на Python
3.12/3.13, включая dependency audit. До этого P5 не принят; P6, production RM-156, RM-157 и RM-158
не начинать.
