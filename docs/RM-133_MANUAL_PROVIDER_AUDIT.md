# RM-133 — аудит ручной регистрации тендерной площадки

Дата аудита: 17 июля 2026 года.
Baseline: `76687a50fe679bfcecc8cc48796fa4fcfae2bba6`.
Ветка: `feat/rm-133-manual-provider-registration`.
Worktree: `C:\CorterisTenderAI_1_5_1\.worktrees\rm-133-manual-provider-registration`.

## 1. Entry gate

Gate пройден до любых изменений application-кода:

- RM-132 закрыт отдельным docs-only PR #71; `origin/main` указывает на его merge SHA
  `76687a50fe679bfcecc8cc48796fa4fcfae2bba6`;
- feature PR #70 RM-132 слит как `1ae9c36605043e35333dffc60a6077c16fbd19f4`;
- exact feature merge-SHA Quality Gate run `29567132554` успешен на Windows Python 3.12/3.13;
- final post-closeout run `29568347122` успешен на точном baseline; оба matrix job прошли все
  workflow steps и полный pytest `1707 passed, 2 warnings`;
- `docs/STATUS.md` и `docs/ROADMAP.md` назначают RM-133 единственным `IN PROGRESS`, RM-134–RM-200
  остаются `PLANNED`;
- local/remote branch и worktree RM-133 до начала отсутствовали; feature branch создан прямо от
  проверенного `origin/main`;
- основной checkout намеренно не обновлялся: пользовательские untracked `.agents/` и
  `skills-lock.json` сохранены без изменений;
- полностью прочитаны canonical roadmap/DoD/history, RM-126 requirements/audit, RM-131 audit/plan,
  RM-132 audit/plan/acceptance, текущие `pyproject.toml`, Windows workflow и handoff RM-133.

## 2. Baseline evidence

Среда: Windows, Python 3.12.7, `PYTHONUTF8=1`, `QT_QPA_PLATFORM=offscreen`, repository-local ignored
basetemp. Live network, DNS и host keyring не использовались.

- provider/settings/catalog/factory/session/scheduler/UI/legacy/RM-131/RM-132 contour:
  `75 passed, 2 warnings in 12.48s`;
- full pytest: `1707 passed, 2 warnings in 78.64s (0:01:18)`;
- два существующих openpyxl warnings относятся к legacy workbook extension и совпадают с RM-132
  acceptance; failures отсутствуют.

## 3. Текущие владельцы и construction sites

| Concern | Канонический владелец | Подтверждённое состояние | Решение RM-133 |
|---|---|---|---|
| Built-in identity | `provider_definitions.py` + `ProviderDescriptor` | 10 async/Collector descriptors, 3 explicit aliases | сохранить неизменными; добавить resolved projection |
| Non-secret persistence | `ProviderEnablementRepository` | один `collector_provider_settings.json`, schema v2 | расширить in place до v3 |
| Effective snapshot | `ProviderSettingsSnapshot` | built-in settings + runtime-only commercial env overrides | добавить immutable manual registrations/catalog projection |
| Application façade | `CollectorProviderManager` | один manager для UI, Collector и scheduler | добавить typed register/update commands |
| UI | `TenderProviderManagerDialog` + existing controller | один manager dialog | добавить action/form внутри этого path |
| Execution | `CollectorRunSession` → existing factory/engine | factory знает только built-in adapters | добавить pre-runtime registration-only guard |
| Credentials | `ProviderCredentialService` over `app.security.secrets` | canonical allowlist, no readback | не вызывать и не расширять |
| Legacy manual entries | `UserSettingsStore.platforms` + `ManualConnectorTester` | отдельный compatibility store/tester | не импортировать, не переписывать, не считать provider |

Production construction остаётся единичным: `TenderSearchUiController` создаёт один manager и одну
session, передавая session snapshot factory manager. Второй catalog/repository/file/manager/factory
не требуется.

## 4. Catalog и identity findings

`canonical_provider_definitions()` возвращает только built-in descriptors и валидирует уникальность
ID и `TenderSource`. Алиасы `sber_a`, `rts_tender`, `roseltorg` разрешаются только к трём существующим
commercial IDs. `TenderSource.CUSTOM` уже существует, но ни один production Collector descriptor его
не использует.

Решение:

- static built-in catalog и его ordering не меняются;
- resolved catalog строится из static built-ins и registrations одного settings snapshot;
- manual registrations используют `TenderSource.CUSTOM`, поэтому source uniqueness применяется к
  built-ins, а manual uniqueness — по stable ID/name/endpoint, не по enum `CUSTOM`;
- origin, registration-only lifecycle и runnable/credential/health/factory capabilities остаются
  явными в resolved read model; наличие `ProviderDescriptor` не означает наличие adapter;
- ambiguous/colliding resolved catalog блокируется до runtime creation.

## 5. Stable manual identity

В проекте широко используется `uuid4().hex` для immutable application identities. Для строкового
provider catalog принимается отдельный namespace `manual_<uuid4().hex>`:

- ID создаётся один раз application command и затем сохраняется verbatim;
- UI не принимает и не редактирует ID;
- rename/update сохраняет ID и `created_at`;
- parser принимает только canonical `manual_` + 32 lowercase hex;
- built-in IDs и aliases запрещены независимо от генератора;
- round-trip и migration не пересоздают identity;
- concurrent duplicate creates сериализуются repository lock: один commit, второй typed conflict.

Генерация random ID не используется для duplicate detection. Конфликт определяется до записи по
нормализованному имени и, если задан, endpoint identity.

## 6. Input и duplicate policy

Display name нормализуется NFKC, внешние/повторные пробелы схлопываются, comparison key использует
casefold. Пустые, oversized, control/NUL/CR/LF и bidi-control значения отклоняются. Сохраняется
безопасное нормализованное пользовательское написание; HTML строится только с escaping.

Homepage обязателен, endpoint metadata опционален. Оба поля:

- допускают только `http`/`https`;
- запрещают user-info, query, fragment, control characters, CRLF, любое whitespace smuggling,
  malformed percent encoding и unsafe schemes;
- нормализуют scheme/IDNA host/default port/trailing slash без DNS или открытия URL;
- не определяют protocol/adapter/runnable state;
- private/loopback/link-local адрес допустим только как inert metadata и никогда не проверяется в
  RM-133; endpoint не включается в public payload, status/log/error/support/export.

Typed conflict возвращается при normalized display-name collision, normalized non-empty endpoint
collision, manual ID collision, built-in/alias collision или неоднозначном catalog. Silent merge и
overwrite запрещены. Homepage сам по себе не является уникальным ключом: один официальный сайт может
представлять несколько юридически разных площадок.

## 7. Schema audit и migration decision

Current `collector_provider_settings.json` schema v2 содержит только:

- aware `updated_at`;
- `providers: {id: bool}`;
- commercial `configuration: {access_confirmed, api_base_url}`.

Schema v2 не может сохранить stable manual ID, display/homepage/endpoint metadata, lifecycle и
created/updated timestamps без неаудированной перегрузки commercial configuration. Поэтому RM-133
требует следующую versioned schema **v3** в том же файле и том же repository.

Новый top-level `manual_registrations` — детерминированный mapping по stable provider ID. Значение
содержит только `display_name`, `homepage_url`, optional `endpoint_url`,
`lifecycle_state=protocol_required`, aware UTC `created_at` и `updated_at`. Origin/manual,
`enabled=False`, отсутствующие protocol/factory/credential/health capabilities являются derived
invariants и не могут быть повышены JSON-флагом.

Migration contract:

1. missing остаётся typed missing без записи;
2. valid v2 читается in memory как migrated previous schema;
3. первая explicit mutation создаёт byte-exact v2 backup и atomic v3 replace;
4. повторные mutations не создают лишний backup;
5. current v3 round-trips deterministic ordering;
6. corrupt/future bytes сохраняются и mutation блокируется;
7. replace failure сохраняет original и удаляет temp;
8. conflict/validation/Cancel не меняют файл;
9. legacy `commercial_provider_settings.json` и `user_settings.json` не меняются;
10. SQLite schema и данные не меняются.

Existing split-v1 → current migration сохраняется: first mutation может сразу материализовать v3,
с byte-exact backups существующих v1 sources. Current v2 получает собственный sibling
`.v2-<timestamp>.bak`.

## 8. Lifecycle и execution boundary

Единственное состояние RM-133 — `PROTOCOL_REQUIRED` (registration-only). Manual entry всегда имеет:

- effective `enabled=False` и non-editable enablement;
- `runnable=False`, `factory_available=False`, `protocol_configured=False`;
- `credential_available=False`, `health_check_available=False`;
- status `Требуется выбор протокола`;
- нулевые search/details/documents/authentication/public API capabilities.

Guards нужны на нескольких существующих seams:

- settings snapshot принудительно оставляет manual registrations disabled даже при
  `providers[manual_id]=true` или environment value;
- manager resolution различает known registration-only и runnable IDs;
- unified resolver проверяет explicit runnable capability, а не только checkbox;
- UI/scheduler controller не создаёт worker для registration-only selection;
- `CollectorRunSession.run()` валидирует selection до `runtime_factory()`;
- factory создаёт adapters только для static built-ins и никогда для manual metadata;
- direct execution возвращает bounded `PROTOCOL_REQUIRED` без endpoint/traceback.

Это сохраняет RM-134 (protocol), RM-135 (adapter) и RM-136 (connection test) отдельными packages.

## 9. Existing UI decision

`TenderProviderManagerDialog` остаётся единственным окном источников. В него добавляются action
«Добавить площадку вручную» и presentation-only dialog с тремя non-secret полями: название,
официальный сайт и optional endpoint metadata. Protocol selector, credential, test connection,
headers/parser/hooks отсутствуют.

Manual row отображается в общей таблице disabled со статусом «Требуется выбор протокола».
Enable/configure credentials/check actions недоступны. Edit name/homepage/endpoint нужен для
целостного UX и выполняется той же typed manager command; stable ID не меняется.

Physical delete/archive остаётся вне RM-133: безопасная политика ссылочной целостности profile и
scheduler IDs относится к дальнейшему lifecycle design. Silent cascade недопустим; built-ins тем
более не удаляются.

## 10. Legacy handoff

Legacy `PlatformConnection` содержит mutable display-name identity, protocol, endpoint, username,
enabled и notes; `UserSettingsStore` пишет отдельный unversioned `user_settings.json`, а explicit
`ManualConnectorTester` выполняет API/RSS/FTP/FTPS test. Этот contract не совместим с canonical
registration lifecycle.

Автоматический или explicit import не нужен Definition of Done RM-133 и остаётся вне scope. Existing
compatibility/credential notices, canonical-manager button, disabled legacy secret field и manual
tester сохраняются. Открытие/регистрация/редактирование canonical manual entry не читает и не пишет
legacy store/keyring и не использует legacy test как health/verified evidence.

## 11. Security and privacy findings

Manual metadata не передаётся в import/eval/dynamic factory, HTTP/RSS/FTP, DNS, filesystem,
subprocess, shell, scheduler action hooks или credential service. Command results содержат только
provider ID, status/category, lifecycle, fixed safe message и aware timestamp. Raw input, endpoint,
exception и mutable objects отсутствуют.

Existing diagnostic support bundle не включает provider settings file. Crash/support redactors не
являются основным guard: validation errors и persistence failures не должны логировать/форматировать
raw input изначально. Manual endpoint исключается из generic snapshot `public_payload()` и UI status.

## 12. Expected-red boundary

До production changes добавляются семь модулей:

- `test_rm133_manual_provider_model.py`;
- `test_rm133_manual_provider_schema.py`;
- `test_rm133_manual_provider_catalog.py`;
- `test_rm133_manual_provider_composition.py`;
- `test_rm133_manual_provider_dialog.py`;
- `test_rm133_manual_provider_security.py`;
- `test_rm133_legacy_platform_handoff.py`.

Expected red принимается только для отсутствующих typed manual model/schema/catalog/manager/UI/
execution guards. Baseline owners не должны давать unrelated failures.

## 13. Risks and guards

| Risk | Required guard |
|---|---|
| v2 data loss | byte-exact first-mutation backup, atomic replace, rollback injection |
| mutable/display identity | application-generated manual UUID namespace and immutable ID |
| duplicate race | same repository lock covers reload, conflict check and replace |
| enabled JSON tampering | derived disabled/runnable false plus pre-runtime guard |
| alias retarget | manual IDs never enter alias table; whole-catalog collision validation |
| endpoint secret leak | reject user-info/query/fragment and never echo raw value |
| accidental adapter/network | factory/runtime/DNS tripwires and explicit lifecycle error |
| second source of truth | only existing repository/path/manager/dialog |
| legacy corruption | before/after byte equality; no import/delete/keyring access |
| delete retargets stale refs | removal deliberately excluded from RM-133 |

## 14. Non-scope and stop rules

Non-scope: protocol choice, executable adapter, health/connection test, credentials, parser/request
configuration, scraping/API contract, live network/DNS, scheduler/profile migration, SQLite migration,
normalization/dedup/ranking, decision/score/critical-stop/AI changes, dependencies and RM-134+.

Stop if implementation requires a second settings file/repository/catalog/manager/factory/engine,
arbitrary keyring identity, dynamic code/import, automatic legacy migration, network at
startup/save/load, DB migration, silent delete cascade or decision semantics change.

## 15. Audit decision

**ACCEPTED FOR DOCS-ONLY AUDIT COMMIT.** RM-133 can be implemented by adding a pure immutable manual
registration contract, upgrading the existing provider settings repository to schema v3, projecting
registrations through the existing manager/dialog and enforcing registration-only state before
runtime creation. No second owner, network behavior, credential path, SQLite migration or RM-134+
functionality is required.
