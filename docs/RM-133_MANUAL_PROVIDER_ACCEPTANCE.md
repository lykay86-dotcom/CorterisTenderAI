# RM-133 — acceptance ручной регистрации тендерной площадки

Дата локальной feature acceptance: 17 июля 2026 года.

## 1. Идентичность пакета

- Baseline: `76687a50fe679bfcecc8cc48796fa4fcfae2bba6`.
- Ветка: `feat/rm-133-manual-provider-registration`.
- Audit commit: `31e1456` (`docs(rm-133): audit manual provider registration boundaries`).
- Expected-red commit: `d3f8906` (`test(rm-133): define manual provider registration contract`).
- Implementation commit: `3931d7b` (`feat(rm-133): add safe manual provider registration`).
- Feature PR, PR CI, merge SHA и exact merge-SHA CI заполняются после публикации feature branch.

## 2. Изменённые owners и границы

- `app.tenders.collector.manual_provider_registration` — pure immutable registration-only model,
  validation, typed command/result/conflict и execution error; storage/network/Qt/keyring отсутствуют.
- `ProviderEnablementRepository` остаётся единственным non-secret settings owner и хранит manual
  registrations в том же `collector_provider_settings.json`.
- `ProviderSettingsSnapshot` проецирует built-in и manual state; manual effective enablement всегда
  false независимо от JSON/environment.
- Static `canonical_provider_definitions()` и alias table не изменены; один resolved catalog добавляет
  manual read models с `TenderSource.CUSTOM` и нулевыми runtime capabilities.
- `CollectorProviderManager` остаётся единственным application façade и получил typed register/update
  commands; credential, health, verification и legacy stores не вызываются.
- Existing `TenderProviderManagerDialog` и controller path получили add/edit form; второе окно
  управления источниками не создавалось.
- `CollectorRunSession`, unified/controller/scheduler entry points и existing factory сохраняют один
  Collector chain и блокируют manual ID до network runtime.

## 3. Schema v3 и rollback evidence

Previous current schema v2 не имела места для stable manual ID, display/homepage/endpoint metadata,
lifecycle и timestamps. Current schema v3 сохраняет v2 поля `providers`, `configuration`,
`updated_at` и добавляет один deterministic `manual_registrations` mapping по stable ID.

Каждая registration содержит только:

- normalized display name;
- normalized homepage URL;
- optional inert endpoint URL metadata;
- `lifecycle_state=protocol_required`;
- aware UTC `created_at` и `updated_at`.

Derived `origin=manual`, `enabled=false`, registration-only и отсутствующие protocol/factory/
credential/health capabilities не повышаются persisted flag. Hand-edited
`providers[manual_id]=true` остаётся нерunnable.

Valid v2 читается in memory без rewrite. Первая explicit mutation создаёт byte-exact sibling
`.v2-<timestamp>.bak`, затем atomic replace v3; повторные mutations не создают лишний backup.
Existing split-v1 sources сохраняют прежние byte-exact backups и materialize directly to v3.
Corrupt/future bytes блокируют mutation; injected replace failure сохраняет original и удаляет temp.
Duplicate/validation/Cancel оставляют bytes неизменными. SQLite, `commercial_provider_settings.json`
и `user_settings.json` не меняются.

## 4. Stable identity и collision policy

Application command создаёт ID один раз в принятом project convention:
`manual_<uuid4().hex>`. Parser допускает только prefix `manual_` и 32 lowercase hex. UI не принимает
ID, rename сохраняет ID и `created_at`, persistence round-trip не пересоздаёт identity.

Repository lock покрывает reload, complete-catalog validation и atomic write. Отклоняются:

- duplicate manual ID;
- collision с canonical built-in/alias namespace;
- normalized NFKC/casefold display-name collision между manual registrations;
- manual display-name collision с built-in catalog;
- normalized endpoint identity collision, включая case/default-port/trailing-slash variants;
- ambiguous current catalog.

Concurrent duplicate create даёт ровно один `CREATED` и один typed `DUPLICATE`; silent merge,
overwrite и partial write отсутствуют. Homepage не является unique key, потому что один официальный
сайт может представлять несколько самостоятельных площадок.

## 5. Validation и privacy

Display name проходит NFKC, trim/space collapse, casefold comparison, bounded length и rejection
control/NUL/CR/LF/bidi characters. Homepage обязателен; endpoint optional. URL parser допускает
только HTTP(S), нормализует scheme/IDNA host/default port/trailing slash и запрещает user-info,
query, fragment, whitespace/control/CRLF, malformed percent и unsafe schemes.

URL metadata не открывается и не проходит DNS. Loopback/private/link-local values допустимы только
как inert metadata. Endpoint скрыт из repr, generic public payload, status/error/log/support/export и
manager details; raw invalid input не повторяется в error. Form/command/model не содержат protocol,
credentials, headers, cookies, parser, request method/body, TLS flags, hooks, import paths или code.

## 6. Registration-only execution proof

Manual catalog entry имеет `PROTOCOL_REQUIRED`, `enabled=False`, `runnable=False`,
`factory_available=False`, `protocol_configured=False`, `credential_available=False` и
`health_check_available=False`. UI checkbox, credentials/configuration/check actions disabled.

Guards подтверждены для:

- manager enable/check commands;
- unified resolver;
- saved-profile/controller and scheduler callback path;
- hand-edited JSON enablement;
- `CollectorRunSession` before `runtime_factory()`;
- async factory with disabled sources included.

Factory возвращает только прежние 10 static built-in IDs и не импортирует manual metadata. Explicit
run возвращает bounded `ManualProviderExecutionError`/`PROTOCOL_REQUIRED`; runtime, HTTP/RSS/FTP,
DNS, filesystem endpoint read, subprocess, shell, dynamic import/eval и credential service не
вызываются.

## 7. UI и legacy handoff

Existing manager содержит action `Добавить площадку вручную` и presentation-only add/edit form с
названием, homepage и optional endpoint metadata. Save локально gated и повторно валидируется
manager command; accepted button блокируется от double submit. Успешная команда обновляет те же
manager/unified/Collector/scheduler read models. Manual row показывает
`Требуется выбор протокола`.

Edit сохраняет internal ID. Physical delete/archive исключён: безопасная referential policy для
profile/scheduler IDs требует отдельного lifecycle design; silent cascade запрещён.

Legacy `PlatformConnection`, `UserSettingsStore`, `ManualConnectorTester`, compatibility notices,
canonical-manager action и disabled credential widget сохранены. Auto/explicit import отсутствует;
legacy bytes и unknown keyring entries не читаются, не копируются и не удаляются.

## 8. Expected-red и local acceptance

Перед production changes семь новых modules дали accepted collection failure:
`7 errors in 3.34s`, все только из-за отсутствующего
`app.tenders.collector.manual_provider_registration`. Ruff для expected-red files прошёл; network,
DNS, keyring и unrelated assertions не запускались.

Environment feature acceptance: Windows, Python 3.12.7, `PYTHONUTF8=1`,
`QT_QPA_PLATFORM=offscreen`, repository-local ignored basetemp.

| Check | Exact result |
|---|---|
| Focused seven RM-133 modules | `51 passed in 4.31s` |
| RM-130/RM-131/RM-132 + provider/UI/factory/session/scheduler/legacy contour | `160 passed, 2 warnings in 12.65s` |
| Full pytest | `1758 passed, 2 warnings in 66.57s (0:01:06)` |
| Repository secret scan | `Repository secret scan passed.` |
| Ruff check | `All checks passed!` |
| Ruff format check | `578 files already formatted` |
| Mypy required contour | `Success: no issues found in 20 source files` |
| Offline credential isolation smoke | `2 passed in 4.14s` |
| Database/schema smoke | `5 passed in 2.84s` |
| Public API import smoke | `DashboardController` |
| Headless composition smoke | `1 passed in 0.19s` |
| Release/build smoke | `6 passed in 3.09s` |
| Dependency audit | `No known vulnerabilities found`; editable project skipped |
| Diff/status | `git diff --check` success; tracked worktree clean before evidence update |

Два warnings focused/neighbor/full contour исходят от openpyxl при чтении existing workbook
extensions и совпадают с RM-132 baseline; failures они не скрывают. Первый sandboxed dependency audit
не достиг PyPI из-за `WinError 10013` и недоступного global cache. Exact audit с approved network и
repository-local cache прошёл без code/dependency changes.

## 9. Scope и rollback

RM-133 не выбирает protocol, не создаёт executable adapter, не проверяет connection/health, не
управляет credentials и не выполняет live provider I/O. Search normalization/dedup/ranking,
scheduler semantics, DB schemas, decision score/recommendation, critical stop-factor priority и AI
semantics не изменены.

Application rollback — scoped revert RM-133 feature commit. Data rollback — восстановление
byte-exact v2/split-v1 backup. Service/account names keyring, legacy files и SQLite не менялись.

**LOCAL FEATURE ACCEPTANCE PASSED.** RM-133 остаётся `IN PROGRESS` до feature PR merge, успешного
exact merge-SHA Windows Quality Gate 3.12/3.13 и отдельного merged docs-only closeout. RM-134 не
активируется этим документом.
