# PRE-RM-156 Collector P9 — stabilization implementation

Дата: 23 июля 2026 года.

Статус: `ACCEPTED`; feature опубликован и принят exact merge-SHA Quality Gate. Collector
prerequisite закрывается отдельным canonical docs-only package.

## 1. Entry gate

- Accepted audit merge: `8aa152f09043b3798040fb41482153a66269a35d`.
- Audit commits: tests `1a588f6`, docs `3f9ae22`.
- PR #154 head `3f9ae22b86e04f25963f9c179b51b90b02818215`.
- PR-head run `29999339166` успешен: jobs `89180529149` (3.12),
  `89180529224` (3.13).
- Exact run `29999808833` успешен: jobs `89182019589` (3.12),
  `89182019632` (3.13), включая full suite и dependency audit.

## 2. Implemented gaps

### Offline all-provider diagnostic

`scripts/check_pre_rm156_collector_offline.py`:

- строит exact ordered projection 13 canonical built-ins через existing catalog и async factory;
- создаёт hermetic async factory runtime с rejecting `MockTransport`;
- не читает keyring/environment credentials и фиксирует `network_calls=0`;
- парсит approved EIS и Mos Supplier fixtures existing parsers;
- публикует fixture SHA-256, item count и accepted contract/parser versions;
- выдаёт bounded deterministic matrix, в которой ни один provider не назван `WORKING` без live
  evidence;
- в temporary directory выполняет реальный schema 15→16 migration, verified backup, explicit
  restore и проверку сохранности sentinel/source;
- выводит JSON в stdout и optional atomic file.

Readiness evidence берётся из уже принятых P4/P6/P7 документов. Runtime readiness owner, provider
catalog, factory, settings, credentials, DB schema и fixtures не дублируются.

### Health error boundary

Unexpected exception вокруг provider `check_health()` больше не попадает raw в public/persisted
health message. `CollectorProviderManager` сохраняет fixed:
`Проверка источника завершилась внутренней ошибкой.` Existing provider/transport classification
остаётся без изменений; token, private URL и exception type/text не сохраняются.

## 3. Test-first result

- Accepted audit expected-red: `6 xfailed in 8.66s`.
- Первый implementation run: `2 failed, 4 passed`; restore transaction не была committed до
  readback, поэтому aggregate drill честно оставался false.
- После minimal commit fix: исходные шесть contracts `6 passed`; CLI/outside-project regression
  добавил седьмой green test.
- Final P9 target: `7 passed in 9.63s`.
- Broad provider/catalog/P3/P4/engine/HTTP/cancellation/verification/schema/backup contour:
  `76 passed in 19.25s`.
- Full suite: `2481 passed, 2 warnings in 197.63s`; warnings — прежние `openpyxl` notices.

## 4. Performance and resource evidence

Неизменённый `python -m scripts.benchmark_pre_rm156_collector_p3`:

- exact raw/merged: `10,000 / 5,000`;
- samples: `5`;
- p50: `7,231.752 ms`;
- nearest-rank p95: `7,296.169 ms`;
- P1 delta: `-9.8835%`;
- RSS delta: `52,252,672 bytes`;
- 25 cycles: tasks `1→1`, threads `1→1`, open-handle growth `0`, temp files `0`;
- cancellation: `17.487 ms`;
- performance и resource gates: passed.

Прямой `python scripts/benchmark_pre_rm156_collector_p3.py` не является supported invocation и
не добавляет project root; он завершился `ModuleNotFoundError: tests` до измерений. Канонический
module invocation выше прошёл. Benchmark code, fixture и thresholds не менялись.

## 5. Quality and security gates

- Ruff: `All checks passed`; format: `806 files already formatted`.
- mypy: `Success: no issues found in 20 source files`.
- repository secret scan, RM-155 compatibility и `git diff --check`: passed.
- offline credential isolation: `2 passed`;
- migration/schema smoke: `5 passed`;
- bootstrap smoke: `1 passed`;
- build/frozen smoke: `9 passed`;
- public `DashboardController` import: passed.
- Local `pip-audit --skip-editable` не смог обратиться к PyPI из sandbox. Required escalation
  отклонена privacy reviewer из-за передачи dependency inventory публичному service; обход не
  выполнялся. Dependency files не менялись. PR-head и exact Windows jobs обязаны выполнить audit.

## 6. Operations, support and rollback

Runbook: `docs/COLLECTOR_OPERATIONS.md`. Provider files в `docs/providers/` фиксируют identity,
access basis, fixture/live status и disable/rollback для всех 13 built-ins.

Rollback feature package:

1. Revert diagnostic script/tests and fixed health-message commit.
2. Schema downgrade, DB/data rewrite и credential/settings deletion не выполнять.
3. Existing provider manager остаётся emergency disable owner.
4. Offline drill работает только в temporary directory; rollback не удаляет production backup,
   artifacts, checkpoints, history или RM-107 decisions.

## 7. Remaining publication and closeout gate

- Commits: tests `c15ab0f`, implementation `cdca6de`, docs `f9d7785`.
- PR #155 head `f9d77857102588750432264186df4b0b268f2788`.
- PR-head run `30001707776` успешен: jobs `89188165195` (3.12),
  `89188165230` (3.13), dependency audit successful.
- Merge `7101396f24885144807f0f60c72b798e48c7861a`.
- Fresh exact run `30002186102`: attempt 1 Python 3.12 получил native Windows
  `access violation`; unchanged-SHA attempt 2 успешен.
- Final jobs `89191332161` (3.12) и `89191333148` (3.13) успешны, включая dependency audit.

После exact success создан отдельный canonical Collector closeout. Production RM-156 не
начинается до merge/exact closeout.
