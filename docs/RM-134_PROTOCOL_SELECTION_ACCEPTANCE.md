# RM-134 — acceptance evidence выбора протокола

Дата локальной приёмки: 17 июля 2026 года
Audit baseline: `38be7babdd0532ef88a1fbeff0acaed75737ea24`
Ветка: `feat/rm-134-provider-protocol-selection`
Статус: local acceptance passed; feature PR/merge evidence pending.

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

## 7. Definition of Done status

Локальные scope, tests, security, quality и documentation requirements выполнены.
Deterministic decision logic не менялась. RM-135 adapter work не начиналась.

Для полного closeout ещё обязательны:

1. feature commit/PR;
2. successful PR Quality Gate на Python 3.12/3.13;
3. merge в `main` только после явного подтверждения;
4. successful exact merge-SHA Quality Gate;
5. docs-only closeout с canonical status/roadmap/history update и последующим exact gate.
