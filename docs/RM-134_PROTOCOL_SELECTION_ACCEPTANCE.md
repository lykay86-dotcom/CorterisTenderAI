# RM-134 — acceptance evidence выбора протокола

Дата локальной приёмки: 17 июля 2026 года
Audit baseline: `38be7babdd0532ef88a1fbeff0acaed75737ea24`
Ветка: `feat/rm-134-provider-protocol-selection`
Статус: feature acceptance passed; docs-only closeout prepared.

## 1. Audit-first evidence

До application-кода созданы:

- `docs/RM-134_PROTOCOL_SELECTION_AUDIT.md`;
- `docs/RM-134_IMPLEMENTATION_PLAN.md`.

Entry gate подтвердил RM-134 как единственный `IN PROGRESS`, отсутствие открытых PR и
успешный exact RM-133 Quality Gate run `29574218692` на baseline
`38be7babdd0532ef88a1fbeff0acaed75737ea24`.

## 2. Expected red

После добавления первых RM-134 acceptance tests и до production implementation выполнено:

```text
python -m pytest -q
  tests/test_rm134_manual_provider_protocol.py
  tests/test_rm134_manual_provider_protocol_schema.py
```

Результат: ожидаемый red — `2 errors during collection`; обе ошибки:
`ModuleNotFoundError: No module named 'app.tenders.collector.manual_provider_protocol'`.

Причина соответствует тестируемому отсутствующему RM-134 contract, а не baseline defect.

## 3. Реализованный contract

- Closed families: API, RSS, FTP, FTPS.
- Code-defined immutable policies: разрешённые schemes, payload formats, authentication
  requirements, TLS policy, default ports и user-facing warnings.
- Typed immutable draft/selection/result; endpoint исключён из repr/public payload.
- Strict syntactic endpoint validation без DNS/network I/O.
- Lifecycle:
  - `protocol_required` до выбора;
  - `adapter_required` после выбора.
- Canonical provider settings schema v4 с in-memory v3 migration и однократным byte-exact
  `.v3-*.bak` при первой mutation.
- Compare-and-replace по точному timezone-aware `updated_at`; stale edit не выполняет write.
- Manager commands: policies/current/readiness, save/change/clear и typed safe failures.
- Canonical dialog/controller wiring с controlled family-dependent inputs и подтверждением
  clear operation.
- Catalog/UI показывают: «Протокол выбран — требуется создание адаптера».

## 4. Сохранённые fail-closed границы

После выбора протокола manual provider по-прежнему имеет:

- `enabled=False`;
- `registration_only=True`;
- `runnable=False`;
- `factory_available=False`;
- `credential_available=False`;
- `health_check_available=False`.

Acceptance tests подтверждают остановку до:

- runtime factory;
- health checker;
- unified search execution;
- enablement;
- adapter construction.

Manual endpoint не передаётся в factory, credentials, diagnostics или public settings
payload. Legacy `PlatformConnection`, legacy settings и `ManualConnectorTester` не
импортируются canonical implementation и не вызываются dialog/save operation.

## 5. Security matrix

Проверены отказ и отсутствие unsafe persistence для:

- HTTP downgrade для API/RSS;
- FTP downgrade для FTPS;
- userinfo, query, fragment и malformed percent encoding;
- localhost, loopback, private, link-local и ambiguous numeric hosts;
- unsupported ports;
- family-incompatible payload/auth combinations;
- FTP traversal, backslash и wildcard/shell-like path values;
- secret-like endpoint paths;
- unknown executable-looking schema fields;
- corrupt/future settings и stale revision.

Ни одно error/result/status message не содержит rejected endpoint или secret sentinel.

## 6. Финальные локальные результаты

### Focused RM-134

```text
38 passed in 4.12s
```

### Neighbor regression contour

RM-131/RM-132/RM-133, provider settings/control/factory, dialogs, scheduler и unified search:

```text
169 passed, 2 warnings in 14.66s
```

### Full pytest

Финальный прогон после всех application-изменений:

```text
1796 passed, 2 warnings in 69.63s (0:01:09)
```

Warnings — существующие openpyxl extension warnings в
`test_rm132_legacy_credentials_handoff.py`.

### Workflow-equivalent gates

- repository secret scan: `Repository secret scan passed.`
- Ruff check: `All checks passed!`
- Ruff format check: `583 files already formatted`
- mypy: `Success: no issues found in 20 source files`
- offline credential isolation smoke: `2 passed in 6.29s`
- legacy DB/schema smoke: `5 passed in 4.18s`
- public API import: `DashboardController`
- headless composition smoke: `1 passed in 0.35s`
- release/build smoke: `6 passed in 5.11s`
- pip-audit: editable package skipped; `No known vulnerabilities found`
- `git diff --check`: passed.

## 7. GitHub evidence

- Feature PR: #74, `feat(rm-134): add safe provider protocol selection`.
- Feature head: `9162beb2e3e046b343d33c8d95aced25c2e66d05`.
- Merge commit: `7ef0378315f9ef76046a651d1211f3da191b7719`.
- PR Quality Gate run `29577913214`:
  - Python 3.12: `1796 passed, 2 warnings in 113.76s`;
  - Python 3.13: `1796 passed, 2 warnings in 87.91s`;
  - all required steps passed.
- Exact merge-SHA Quality Gate run `29578571237` на `7ef0378`:
  - Python 3.12 rerun: `1796 passed, 2 warnings in 84.87s`;
  - Python 3.13: `1796 passed, 2 warnings in 124.47s`;
  - final run conclusion and both matrix jobs: `success`.

Первый exact Python 3.12 attempt завершился native Windows heap abort `0xc0000374`
примерно на 52% pytest без test assertion. Тот же SHA уже проходил PR Python 3.12,
exact Python 3.13 и два локальных full runs. Failed-only rerun выполнен без code/doc
изменений и завершился успешно; evidence сохранено в том же run `29578571237`.

## 8. Definition of Done status

Локальные scope, tests, security, quality и documentation requirements выполнены.
Deterministic decision logic не менялась. RM-135 adapter work не начиналась.

Feature commit/PR, подтверждённый merge и exact merge-SHA Quality Gate выполнены.
Canonical status/roadmap/history обновлены этим отдельным docs-only closeout. После его
merge остаётся проверить exact docs merge-SHA gate до начала application-кода RM-135.
