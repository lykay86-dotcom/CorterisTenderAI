# RM-135 — acceptance evidence безопасного конструктора адаптера

Дата локальной приёмки: 17 июля 2026 года  
Baseline: `9008f8caee02c09221ab9e2e7da1c130420d0689`  
Ветка: `feat/rm-135-safe-custom-adapter-builder`  
Статус: feature acceptance, merge и exact merge-SHA Quality Gate passed.

## 1. Audit-first и expected-red evidence

До application-кода отдельным commit `b0f1048` зафиксированы
`RM-135_CUSTOM_ADAPTER_AUDIT.md` и `RM-135_IMPLEMENTATION_PLAN.md`. Audit подтвердил, что
canonical settings schema v4, provider manager, async factory и Collector admission guards можно
расширить без второго store/catalog/factory/Collector и без live egress.

Expected-red commit `e7b9121` добавил семь focused test modules. До production implementation:

```text
7 errors during collection in 4.57s
```

Шесть ошибок были вызваны отсутствующим `app.tenders.collector.manual_adapter`, одна — отсутствующим
`ManualAdapterWizardDialog`. Baseline defects, runtime/network assertions и credential calls не
наблюдались.

## 2. Реализованный contract

- `ManualAdapterSpec` v1 и frozen typed submodels: source, exact record selector, canonical field
  mappings, allowlisted transforms и hard resource limits.
- Deterministic canonical serialization и SHA-256 semantic fingerprint; timestamps, revision и
  secret values не участвуют в fingerprint.
- Strict persisted decoder отклоняет unknown fields, bool-as-int, tampered fingerprint, protocol,
  provider ID и lifecycle mismatch.
- Provider settings schema v5; v4 загружается как `MIGRATED_V4` без guessing и без mutation.
  Первая explicit mutation создаёт один byte-exact `.v4-*.bak`, затем выполняет atomic replace.
- Monotonic revisions сохраняются через clear; semantic no-op не пишет файл; stale writer rejected;
  rollback публикует предыдущую semantic spec как новую auditable revision. History bounded to 5.
- Pure offline preview для JSON, XML, RSS, namespaced Atom и CSV. Selector/mapping DSL ограничен
  exact segments и canonical target enum; preview имеет hard bytes/depth/record/field/string caps.
- Mapping provenance содержит target, source path, allowlisted transforms, status и exact spec
  revision. Decimal и aware datetime не угадываются и не получают fabricated defaults.
- Static code-owned compiler dispatch для API/RSS/FTP/FTPS возвращает typed
  `AdapterCompileResult`; каждый compile создаёт scoped `AsyncTenderProvider` instance и не вызывает
  transport/credential resolver.
- Existing async factory только делегирует explicit manual build compiler. Ordinary composition не
  перечисляет manual providers и не кэширует runtime instance.
- Existing `CollectorProviderManager` предоставляет typed read/compile/preview/save/clear/rollback
  commands. Wizard preview вызывается через manager command.
- Canonical provider manager/controller содержит restricted adapter wizard с явной надписью
  `Offline sample — подключение не проверено` и success text
  `Адаптер настроен. Требуется проверка подключения.`

## 3. Lifecycle и admission evidence

После успешного save/compile manual registration имеет только:

```text
lifecycle = connection_test_required
adapter_compiled = true
connection_verified = false
enabled = false
runnable = false
health_check_available = false
```

Runtime object сохраняет stable provider ID, spec revision и fingerprint, но `search`, `get_tender`,
`list_documents` и `check_health` проверяют cancellation и завершаются typed
`connection_test_required`. Manual provider по-прежнему блокируется settings snapshot, profiles,
scheduler, unified search и run session до создания network runtime.

Ни save, load, compile, preview, UI open/cancel, startup, factory или catalog projection не выполняют
DNS, network, TLS handshake, filesystem sample read, credential resolution или background task.

## 4. Security matrix

Проверены:

- отсутствие dynamic import, entry points, eval/exec/compile, pickle/marshal, shell/subprocess;
- отсутствие legacy `ManualConnectorTester`, keyring и credential load в adapter domain;
- GET-only API source, отсутствие arbitrary headers/body/cookies/FTP commands и mutation methods;
- rejection wildcard, traversal, JSONPath/XPath functions и executable-looking mapping paths;
- XML DTD/entity/XInclude rejection до parse; namespaced Atom обрабатывается по local-name;
- bounded sample, nesting, records, preview rows, mappings, transforms и string values;
- unknown schema fields, future/corrupt schema, invalid revision/history/fingerprint fail closed;
- raw XML sentinel не попадает в result repr/diagnostic; endpoint/spec/sample/secret не попадают в
  public payload или compiler dependency repr;
- repository secret scan passed; legacy records/tester/credential store не изменялись.

Live SSRF/DNS-rebinding, redirect revalidation, TLS handshake и safe FTP/FTPS transport намеренно не
реализованы: любой live method заблокирован до RM-136.

## 5. Локальные результаты

Среда: Windows, Python 3.12.7, Qt offscreen, repository-local ignored basetemp.

### Focused RM-135

```text
27 passed in 3.65s
```

### Neighbor RM-131–RM-135 и provider owners

```text
205 passed, 2 warnings in 13.66s
```

### Final full pytest

```text
1823 passed, 2 warnings in 64.15s (0:01:04)
```

Оба warnings — существующие openpyxl extension warnings из RM-132 legacy fixture.

### Workflow-equivalent gate

- repository secret scan: `Repository secret scan passed.`
- Ruff check: `All checks passed!`
- Ruff format: `592 files already formatted`
- required mypy: `Success: no issues found in 20 source files`
- extended mypy changed contour: `Success: no issues found in 6 source files`
- offline credential isolation smoke: `2 passed in 5.97s`
- database/schema smoke: `5 passed in 4.23s`
- public import smoke: `DashboardController`
- headless composition smoke: `1 passed in 0.38s`
- release/build smoke: `6 passed in 4.89s`
- dependency audit: editable package skipped; `No known vulnerabilities found`
- `git diff --check`: passed.

## 6. Version and migration evidence

| Boundary | RM-135 state |
|---|---|
| Provider settings | schema v5; v4 in-memory migration + byte-exact backup |
| Manual adapter spec | `MANUAL_ADAPTER_SPEC_VERSION = 1` |
| Async provider API | existing implicit stable `AsyncTenderProvider` contract |
| Collector SQLite | unchanged schema v14 |
| Collector architecture | unchanged v1 |
| UnifiedTender/normalizer/dedup | unchanged |

SQLite, business scoring, recommendation, critical stop-factor priority, AI orchestration and built-in
provider behavior не изменялись.

## 7. Rollback и known limitations

- Code rollback: revert RM-135 feature commits; no database/keyring/network side effects require
  compensation.
- Data rollback: preserve current v5 for inspection and restore the byte-exact `.v4-*.bak` created on
  first mutation. Unknown/future content remains fail closed.
- Application rollback: manager rollback creates a new monotonic revision; clear keeps protocol and
  bounded history, never deletes credentials.
- Offline preview accepts pasted bounded sample only; no live/local-file fetch and no production
  tender creation.
- Credential input/storage and connection verification are not added. RM-136 must audit SSRF/DNS,
  redirects, TLS and FTP/FTPS transport before any live method can be admitted.

## 8. GitHub evidence

- Feature head: `4358c5d64380205b87b4b2a70ec1e97df983df74`.
- Feature PR #76 (`feat(rm-135): add safe custom adapter builder`) слит в `main` merge commit
  `306b20977b6c23956488dc471da63af17f197e25`.
- PR Quality Gate run `29584304208` успешен:
  - Python 3.12: `1823 passed, 2 warnings in 59.52s`;
  - Python 3.13: `1823 passed, 2 warnings in 88.40s`;
  - secret scan, Ruff, format, mypy, smokes и dependency audit прошли на обеих версиях.
- Exact merge-SHA run `29586643112` успешен:
  - Python 3.12 failed-only rerun: `1823 passed, 2 warnings in 86.41s`;
  - Python 3.13: `1823 passed, 2 warnings in 88.19s`;
  - final run conclusion и обе matrix job: `success`.

Первый exact Python 3.12 attempt завершился native Windows `access violation` примерно на 51%
pytest без test assertion или Python traceback в application-коде. Тот же SHA уже прошёл PR
Python 3.12, exact Python 3.13 и два локальных full runs. Failed-only rerun выполнен без code/doc
изменений и завершился успешно; evidence сохранено в run `29586643112`.

## 9. Definition of Done status

Local scope, security, migration, factory, UI, regression and documentation requirements passed.
Feature commits `b4f9ba6`/`faca072`, PR merge и exact merge-SHA gate завершены. Этот отдельный
docs-only closeout обновляет canonical status/roadmap/history, переводит RM-135 в `DONE` и назначает
RM-136 единственным `IN PROGRESS`. RM-137+ остаются `PLANNED`.
